"""Tests for the schema migration system.

Covers fresh installs, pre-migration (v0) database upgrades, idempotency,
data preservation, the schema_version property, and future version handling.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from memorymesh.memory import Memory
from memorymesh.migrations import (
    _FULL_SCHEMA,
    LATEST_VERSION,
    ensure_schema,
    get_schema_version,
)
from memorymesh.store import MemoryStore

if TYPE_CHECKING:
    import pytest


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

# The v0.1.0 schema as raw DDL (no user_version set).
_V0_CREATE_TABLE = """
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

_V0_CREATE_INDEX_IMPORTANCE = """
    CREATE INDEX idx_memories_importance ON memories (importance DESC);
"""

_V0_CREATE_INDEX_UPDATED = """
    CREATE INDEX idx_memories_updated_at ON memories (updated_at DESC);
"""


def _create_v0_database(path: str) -> None:
    """Create a database with the v0.1.0 schema (no user_version set)."""
    conn = sqlite3.connect(path)
    conn.execute(_V0_CREATE_TABLE)
    conn.execute(_V0_CREATE_INDEX_IMPORTANCE)
    conn.execute(_V0_CREATE_INDEX_UPDATED)
    conn.commit()
    conn.close()


def _insert_raw_memory(path: str, memory_id: str, text: str) -> None:
    """Insert a memory row via raw SQL into an existing database."""
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


# ------------------------------------------------------------------
# Fresh install tests
# ------------------------------------------------------------------


class TestFreshInstall:
    """Tests for creating a brand new database."""

    def test_fresh_install_creates_schema(self, tmp_path: object) -> None:
        """New DB gets the latest schema and correct version."""
        db_path = str(tmp_path / "fresh.db")  # type: ignore[operator]
        conn = sqlite3.connect(db_path)
        version = ensure_schema(conn)
        conn.close()

        assert version == LATEST_VERSION

        # Verify table and indexes exist
        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
        )
        assert cur.fetchone() is not None

        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_memories_%'"
        )
        indexes = {row[0] for row in cur.fetchall()}
        assert "idx_memories_importance" in indexes
        assert "idx_memories_updated_at" in indexes
        conn.close()

    def test_fresh_install_crud_works(self, tmp_path: object) -> None:
        """Basic save/get works on a fresh database."""
        store = MemoryStore(path=str(tmp_path / "crud.db"))  # type: ignore[operator]
        mem = Memory(text="Hello from migrations test")
        store.save(mem)

        retrieved = store.get(mem.id)
        assert retrieved is not None
        assert retrieved.text == "Hello from migrations test"
        store.close()

    def test_fresh_install_idempotent(self, tmp_path: object) -> None:
        """Closing and reopening a fresh DB preserves version and data."""
        db_path = str(tmp_path / "idempotent.db")  # type: ignore[operator]

        # First open -- creates schema
        store = MemoryStore(path=db_path)
        mem = Memory(text="Persisted across reopens")
        store.save(mem)
        store.close()

        # Second open -- should detect existing schema, not recreate
        store2 = MemoryStore(path=db_path)
        assert store2.schema_version == LATEST_VERSION
        assert store2.get(mem.id) is not None
        assert store2.get(mem.id).text == "Persisted across reopens"
        store2.close()


# ------------------------------------------------------------------
# Pre-migration (v0) database upgrade tests
# ------------------------------------------------------------------


class TestExistingV0Database:
    """Tests for upgrading a pre-migration database."""

    def test_existing_v0_stamped(self, tmp_path: object) -> None:
        """Pre-migration DB gets stamped to v1 without errors."""
        db_path = str(tmp_path / "v0.db")  # type: ignore[operator]
        _create_v0_database(db_path)

        conn = sqlite3.connect(db_path)
        assert get_schema_version(conn) == 0

        version = ensure_schema(conn)
        assert version == LATEST_VERSION
        assert get_schema_version(conn) == LATEST_VERSION
        conn.close()

    def test_existing_v0_data_preserved(self, tmp_path: object) -> None:
        """Memories inserted before migration survive the upgrade."""
        db_path = str(tmp_path / "v0_data.db")  # type: ignore[operator]
        _create_v0_database(db_path)
        _insert_raw_memory(db_path, "mem-001", "Important decision")
        _insert_raw_memory(db_path, "mem-002", "Architecture note")

        # Run migration
        conn = sqlite3.connect(db_path)
        ensure_schema(conn)
        conn.close()

        # Verify data via MemoryStore
        store = MemoryStore(path=db_path)
        assert store.count() == 2
        mem1 = store.get("mem-001")
        assert mem1 is not None
        assert mem1.text == "Important decision"
        mem2 = store.get("mem-002")
        assert mem2 is not None
        assert mem2.text == "Architecture note"
        store.close()

    def test_existing_v0_reopen_idempotent(self, tmp_path: object) -> None:
        """Upgraded DB stays at correct version on reopen."""
        db_path = str(tmp_path / "v0_reopen.db")  # type: ignore[operator]
        _create_v0_database(db_path)
        _insert_raw_memory(db_path, "mem-persist", "Should survive")

        # First open via MemoryStore triggers migration
        store = MemoryStore(path=db_path)
        v1 = store.schema_version
        store.close()

        # Second open should not re-migrate
        store2 = MemoryStore(path=db_path)
        assert store2.schema_version == v1
        assert store2.get("mem-persist") is not None
        store2.close()


# ------------------------------------------------------------------
# Schema version property
# ------------------------------------------------------------------


class TestSchemaVersionProperty:
    """Tests for the store.schema_version property."""

    def test_schema_version_property(self, tmp_path: object) -> None:
        """store.schema_version returns the correct value."""
        store = MemoryStore(path=str(tmp_path / "version.db"))  # type: ignore[operator]
        assert store.schema_version == LATEST_VERSION
        store.close()


# ------------------------------------------------------------------
# Migration skipping and edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases in the migration system."""

    def test_migration_skipped_when_current(self, tmp_path: object) -> None:
        """No migration runs if the database is already at the latest version."""
        db_path = str(tmp_path / "current.db")  # type: ignore[operator]

        # Create and migrate
        conn = sqlite3.connect(db_path)
        v1 = ensure_schema(conn)
        assert v1 == LATEST_VERSION

        # Call again -- should be a no-op returning the same version
        v2 = ensure_schema(conn)
        assert v2 == LATEST_VERSION
        conn.close()

    def test_future_version_warning(self, tmp_path: object, caplog: pytest.LogCaptureFixture) -> None:
        """user_version > LATEST_VERSION logs a warning and does not error."""
        db_path = str(tmp_path / "future.db")  # type: ignore[operator]
        conn = sqlite3.connect(db_path)

        # Create schema and set a future version
        for stmt in _FULL_SCHEMA:
            conn.execute(stmt)
        future_version = LATEST_VERSION + 10
        conn.execute(f"PRAGMA user_version = {future_version}")
        conn.commit()

        with caplog.at_level(logging.WARNING, logger="memorymesh.migrations"):
            version = ensure_schema(conn)

        assert version == future_version
        assert "newer than the library supports" in caplog.text
        conn.close()
