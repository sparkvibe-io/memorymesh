"""Tests for episodic memory (session tracking).

Covers saving memories with session_id, retrieving by session, listing
sessions, migration from v1 to v2 schema, and backward compatibility.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from memorymesh.memory import Memory
from memorymesh.migrations import LATEST_VERSION, ensure_schema, get_schema_version
from memorymesh.store import MemoryStore

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

# The v1 schema (no session_id column).
_V1_CREATE_TABLE = """
    CREATE TABLE memories (
        id             TEXT PRIMARY KEY,
        text           TEXT    NOT NULL,
        metadata_json  TEXT    NOT NULL DEFAULT '{}',
        embedding_blob BLOB,
        created_at     TEXT    NOT NULL,
        updated_at     TEXT    NOT NULL,
        access_count   INTEGER NOT NULL DEFAULT 0,
        importance     REAL    NOT NULL DEFAULT 0.5,
        decay_rate     REAL    NOT NULL DEFAULT 0.01
    );
"""

_V1_INDEXES = [
    "CREATE INDEX idx_memories_importance ON memories (importance DESC);",
    "CREATE INDEX idx_memories_updated_at ON memories (updated_at DESC);",
]


def _create_v1_database(path: str) -> None:
    """Create a database with the v1 schema (no session_id)."""
    conn = sqlite3.connect(path)
    conn.execute(_V1_CREATE_TABLE)
    for idx in _V1_INDEXES:
        conn.execute(idx)
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()


def _insert_raw_memory(path: str, memory_id: str, text: str) -> None:
    """Insert a memory row via raw SQL into an existing v1 database."""
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(path)
    conn.execute(
        """
        INSERT INTO memories (id, text, metadata_json, created_at, updated_at,
                              access_count, importance, decay_rate)
        VALUES (?, ?, '{}', ?, ?, 0, 0.5, 0.01)
        """,
        (memory_id, text, now, now),
    )
    conn.commit()
    conn.close()


def _get_column_names(path: str, table: str = "memories") -> list[str]:
    """Return column names for a table."""
    conn = sqlite3.connect(path)
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    conn.close()
    return cols


# ------------------------------------------------------------------
# Migration tests (v1 -> v2)
# ------------------------------------------------------------------


class TestMigrationV1ToV2:
    """Tests for migrating from schema v1 to v2."""

    def test_migration_adds_session_id_column(self, tmp_path: object) -> None:
        """Migration v2 adds the session_id column to the memories table."""
        db_path = str(tmp_path / "v1.db")  # type: ignore[operator]
        _create_v1_database(db_path)

        conn = sqlite3.connect(db_path)
        assert get_schema_version(conn) == 1

        version = ensure_schema(conn)
        conn.close()

        assert version == LATEST_VERSION
        assert version >= 2

        cols = _get_column_names(db_path)
        assert "session_id" in cols

    def test_migration_creates_session_index(self, tmp_path: object) -> None:
        """Migration v2 creates the session_id index."""
        db_path = str(tmp_path / "v1_idx.db")  # type: ignore[operator]
        _create_v1_database(db_path)

        conn = sqlite3.connect(db_path)
        ensure_schema(conn)
        conn.close()

        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_memories_session_id'"
        )
        assert cur.fetchone() is not None
        conn.close()

    def test_migration_preserves_existing_data(self, tmp_path: object) -> None:
        """Existing memories survive the v1->v2 migration with NULL session_id."""
        db_path = str(tmp_path / "v1_data.db")  # type: ignore[operator]
        _create_v1_database(db_path)
        _insert_raw_memory(db_path, "old-mem", "Old memory")

        store = MemoryStore(path=db_path)
        assert store.schema_version == LATEST_VERSION

        mem = store.get("old-mem")
        assert mem is not None
        assert mem.text == "Old memory"
        assert mem.session_id is None
        store.close()

    def test_fresh_db_has_session_id(self, tmp_path: object) -> None:
        """A fresh database includes the session_id column from _FULL_SCHEMA."""
        db_path = str(tmp_path / "fresh.db")  # type: ignore[operator]
        conn = sqlite3.connect(db_path)
        ensure_schema(conn)
        conn.close()

        cols = _get_column_names(db_path)
        assert "session_id" in cols


# ------------------------------------------------------------------
# Store-level tests
# ------------------------------------------------------------------


class TestStoreSaveAndRetrieve:
    """Tests for saving and retrieving memories with session_id at the store level."""

    def test_save_with_session_id(self, tmp_path: object) -> None:
        """A memory saved with a session_id retains it on retrieval."""
        store = MemoryStore(path=str(tmp_path / "sess.db"))  # type: ignore[operator]
        mem = Memory(text="Session memory", session_id="sess-001")
        store.save(mem)

        retrieved = store.get(mem.id)
        assert retrieved is not None
        assert retrieved.session_id == "sess-001"
        store.close()

    def test_save_without_session_id(self, tmp_path: object) -> None:
        """A memory saved without session_id has NULL session_id."""
        store = MemoryStore(path=str(tmp_path / "no_sess.db"))  # type: ignore[operator]
        mem = Memory(text="No session")
        store.save(mem)

        retrieved = store.get(mem.id)
        assert retrieved is not None
        assert retrieved.session_id is None
        store.close()

    def test_get_by_session(self, tmp_path: object) -> None:
        """get_by_session returns only memories with the specified session_id."""
        store = MemoryStore(path=str(tmp_path / "by_sess.db"))  # type: ignore[operator]
        store.save(Memory(text="A1", session_id="alpha"))
        store.save(Memory(text="A2", session_id="alpha"))
        store.save(Memory(text="B1", session_id="beta"))
        store.save(Memory(text="No session"))

        alpha_mems = store.get_by_session("alpha")
        assert len(alpha_mems) == 2
        assert all(m.session_id == "alpha" for m in alpha_mems)

        beta_mems = store.get_by_session("beta")
        assert len(beta_mems) == 1
        assert beta_mems[0].text == "B1"

        none_mems = store.get_by_session("nonexistent")
        assert len(none_mems) == 0
        store.close()

    def test_get_by_session_ordered_by_created_at(self, tmp_path: object) -> None:
        """get_by_session returns memories in creation order."""
        store = MemoryStore(path=str(tmp_path / "order.db"))  # type: ignore[operator]
        m1 = Memory(text="First", session_id="sess")
        m2 = Memory(text="Second", session_id="sess")
        m3 = Memory(text="Third", session_id="sess")
        store.save(m1)
        store.save(m2)
        store.save(m3)

        mems = store.get_by_session("sess")
        texts = [m.text for m in mems]
        assert texts == ["First", "Second", "Third"]
        store.close()

    def test_list_sessions(self, tmp_path: object) -> None:
        """list_sessions returns distinct sessions with counts and timestamps."""
        store = MemoryStore(path=str(tmp_path / "list_sess.db"))  # type: ignore[operator]
        store.save(Memory(text="A1", session_id="alpha"))
        store.save(Memory(text="A2", session_id="alpha"))
        store.save(Memory(text="B1", session_id="beta"))
        store.save(Memory(text="No session"))

        sessions = store.list_sessions()
        assert len(sessions) == 2

        session_ids = {s["session_id"] for s in sessions}
        assert session_ids == {"alpha", "beta"}

        alpha_info = next(s for s in sessions if s["session_id"] == "alpha")
        assert alpha_info["count"] == 2
        assert alpha_info["first_at"] is not None
        assert alpha_info["last_at"] is not None
        store.close()

    def test_list_sessions_excludes_null(self, tmp_path: object) -> None:
        """list_sessions does not include memories with NULL session_id."""
        store = MemoryStore(path=str(tmp_path / "null_sess.db"))  # type: ignore[operator]
        store.save(Memory(text="No session 1"))
        store.save(Memory(text="No session 2"))

        sessions = store.list_sessions()
        assert len(sessions) == 0
        store.close()

    def test_list_sessions_limit(self, tmp_path: object) -> None:
        """list_sessions respects the limit parameter."""
        store = MemoryStore(path=str(tmp_path / "limit_sess.db"))  # type: ignore[operator]
        for i in range(10):
            store.save(Memory(text=f"Mem {i}", session_id=f"sess-{i:02d}"))

        sessions = store.list_sessions(limit=3)
        assert len(sessions) == 3
        store.close()


# ------------------------------------------------------------------
# Core-level tests
# ------------------------------------------------------------------


class TestCoreRememberWithSession:
    """Tests for MemoryMesh.remember() with session_id."""

    def test_remember_with_session(self, tmp_path: object) -> None:
        """remember() stores session_id and it's retrievable via get()."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "core_sess.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, embedding="none") as mesh:
            mid = mesh.remember(
                "Design decision: use SQLite",
                scope="project",
                session_id="conv-42",
            )

            mem = mesh.get(mid)
            assert mem is not None
            assert mem.session_id == "conv-42"

    def test_remember_without_session(self, tmp_path: object) -> None:
        """remember() without session_id defaults to None."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "core_no_sess.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, embedding="none") as mesh:
            mid = mesh.remember("No session here", scope="project")

            mem = mesh.get(mid)
            assert mem is not None
            assert mem.session_id is None


class TestCoreRecallWithSession:
    """Tests for MemoryMesh.recall() with session_id boosting."""

    def test_recall_boosts_same_session(self, tmp_path: object) -> None:
        """recall() with session_id boosts same-session memories in ranking."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "recall_sess.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, embedding="none") as mesh:
            # Create two memories with same text but different sessions.
            mesh.remember(
                "SQLite design decision",
                scope="project",
                session_id="sess-A",
                importance=0.5,
            )
            mesh.remember(
                "SQLite design decision",
                scope="project",
                session_id="sess-B",
                importance=0.5,
            )

            # Recall with sess-A should boost sess-A memory.
            results = mesh.recall(
                "SQLite design",
                k=5,
                session_id="sess-A",
            )
            assert len(results) == 2
            # The first result should be from sess-A due to the boost.
            assert results[0].session_id == "sess-A"

    def test_recall_without_session_still_works(self, tmp_path: object) -> None:
        """recall() without session_id returns results normally."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "recall_no_sess.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, embedding="none") as mesh:
            mesh.remember("Important fact", scope="project", session_id="sess-1")
            mesh.remember("Another fact", scope="project")

            results = mesh.recall("fact", k=5)
            assert len(results) == 2


class TestCoreGetSession:
    """Tests for MemoryMesh.get_session()."""

    def test_get_session_returns_session_memories(self, tmp_path: object) -> None:
        """get_session() returns all memories for a given session."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "get_sess.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, embedding="none") as mesh:
            mesh.remember("Msg 1", scope="project", session_id="conv-1")
            mesh.remember("Msg 2", scope="project", session_id="conv-1")
            mesh.remember("Other", scope="project", session_id="conv-2")

            session = mesh.get_session("conv-1")
            assert len(session) == 2
            assert all(m.session_id == "conv-1" for m in session)

    def test_get_session_empty(self, tmp_path: object) -> None:
        """get_session() returns empty list for unknown session."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "get_sess_empty.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, embedding="none") as mesh:
            mesh.remember("Something", scope="project", session_id="known")
            assert mesh.get_session("unknown") == []

    def test_get_session_across_scopes(self, tmp_path: object) -> None:
        """get_session() merges results from project and global stores."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "get_sess_scopes.db")  # type: ignore[operator]
        global_path = str(tmp_path / "global_sess.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, global_path=global_path, embedding="none") as mesh:
            mesh.remember("Project note", scope="project", session_id="shared")
            mesh.remember("Global pref", scope="global", session_id="shared")

            all_session = mesh.get_session("shared")
            assert len(all_session) == 2

            project_only = mesh.get_session("shared", scope="project")
            assert len(project_only) == 1
            assert project_only[0].scope == "project"

            global_only = mesh.get_session("shared", scope="global")
            assert len(global_only) == 1
            assert global_only[0].scope == "global"


class TestCoreListSessions:
    """Tests for MemoryMesh.list_sessions()."""

    def test_list_sessions(self, tmp_path: object) -> None:
        """list_sessions() returns session summaries."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "list_sess.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, embedding="none") as mesh:
            mesh.remember("A", scope="project", session_id="s1")
            mesh.remember("B", scope="project", session_id="s1")
            mesh.remember("C", scope="project", session_id="s2")

            sessions = mesh.list_sessions()
            assert len(sessions) == 2

            s_ids = {s["session_id"] for s in sessions}
            assert s_ids == {"s1", "s2"}

    def test_list_sessions_empty(self, tmp_path: object) -> None:
        """list_sessions() returns empty list when no sessions exist."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "empty_sess.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, embedding="none") as mesh:
            mesh.remember("No session", scope="project")
            assert mesh.list_sessions() == []

    def test_list_sessions_with_scope(self, tmp_path: object) -> None:
        """list_sessions() filters by scope."""
        from memorymesh import MemoryMesh

        db_path = str(tmp_path / "scope_sess.db")  # type: ignore[operator]
        global_path = str(tmp_path / "global_scope_sess.db")  # type: ignore[operator]
        with MemoryMesh(path=db_path, global_path=global_path, embedding="none") as mesh:
            mesh.remember("P", scope="project", session_id="proj-sess")
            mesh.remember("G", scope="global", session_id="glob-sess")

            proj_sessions = mesh.list_sessions(scope="project")
            assert len(proj_sessions) == 1
            assert proj_sessions[0]["session_id"] == "proj-sess"

            glob_sessions = mesh.list_sessions(scope="global")
            assert len(glob_sessions) == 1
            assert glob_sessions[0]["session_id"] == "glob-sess"

            all_sessions = mesh.list_sessions()
            assert len(all_sessions) == 2


# ------------------------------------------------------------------
# Memory dataclass tests
# ------------------------------------------------------------------


class TestMemoryDataclass:
    """Tests for the Memory dataclass with session_id."""

    def test_memory_session_id_default(self) -> None:
        """Memory.session_id defaults to None."""
        mem = Memory(text="Hello")
        assert mem.session_id is None

    def test_memory_session_id_set(self) -> None:
        """Memory.session_id can be set explicitly."""
        mem = Memory(text="Hello", session_id="s1")
        assert mem.session_id == "s1"

    def test_memory_to_dict_includes_session_id(self) -> None:
        """to_dict() includes session_id."""
        mem = Memory(text="Hello", session_id="s1")
        d = mem.to_dict()
        assert d["session_id"] == "s1"

    def test_memory_to_dict_session_id_none(self) -> None:
        """to_dict() includes session_id=None when not set."""
        mem = Memory(text="Hello")
        d = mem.to_dict()
        assert d["session_id"] is None

    def test_memory_from_dict_with_session_id(self) -> None:
        """from_dict() reconstructs session_id."""
        mem = Memory(text="Hello", session_id="s1")
        d = mem.to_dict()
        restored = Memory.from_dict(d)
        assert restored.session_id == "s1"

    def test_memory_from_dict_without_session_id(self) -> None:
        """from_dict() defaults session_id to None for old data."""
        d: dict[str, Any] = {
            "text": "Old memory",
            "id": "abc123",
            "created_at": "2025-01-01T00:00:00+00:00",
            "updated_at": "2025-01-01T00:00:00+00:00",
        }
        mem = Memory.from_dict(d)
        assert mem.session_id is None

    def test_memory_json_roundtrip(self) -> None:
        """JSON serialisation round-trips session_id."""
        mem = Memory(text="Test", session_id="json-sess")
        restored = Memory.from_json(mem.to_json())
        assert restored.session_id == "json-sess"
