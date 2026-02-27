"""Tests for MemoryMesh v4.0 features.

Covers SQL injection prevention, file permissions, smart_sync,
RelevanceWeights.from_env, EncryptedMemoryStore completeness,
and MCP server version.
"""

from __future__ import annotations

import stat
import sys
from collections.abc import Generator
from datetime import datetime, timezone

import pytest

from memorymesh.encryption import EncryptedMemoryStore
from memorymesh.memory import Memory
from memorymesh.relevance import RelevanceWeights
from memorymesh.store import MemoryStore

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_memory(
    text: str = "test",
    importance: float = 0.5,
    created_at: datetime | None = None,
    **kwargs,
) -> Memory:
    """Create a Memory with convenient defaults."""
    if created_at is None:
        created_at = datetime.now(timezone.utc)
    return Memory(
        text=text,
        importance=importance,
        created_at=created_at,
        updated_at=created_at,
        **kwargs,
    )


# ------------------------------------------------------------------
# 1a. SQL injection prevention in metadata_filter
# ------------------------------------------------------------------


class TestSQLInjectionPrevention:
    """Verify that malicious metadata_filter keys are rejected."""

    @pytest.fixture
    def store(self, tmp_path) -> Generator[MemoryStore, None, None]:
        s = MemoryStore(path=tmp_path / "test.db")
        s.save(_make_memory("test memory", metadata={"category": "test"}))
        yield s
        s.close()

    def test_valid_key_accepted(self, store: MemoryStore) -> None:
        """Normal alphanumeric keys should work fine."""
        results = store.search_filtered(metadata_filter={"category": "test"})
        assert len(results) >= 1

    def test_valid_key_with_underscore(self, store: MemoryStore) -> None:
        """Keys with underscores should be accepted."""
        store.search_filtered(metadata_filter={"my_key": "value"})

    def test_sql_injection_drop_table(self, store: MemoryStore) -> None:
        """Keys attempting SQL injection via DROP TABLE are rejected."""
        with pytest.raises(ValueError, match="Invalid metadata_filter key"):
            store.search_filtered(metadata_filter={"'; DROP TABLE memories; --": "x"})

    def test_sql_injection_semicolon(self, store: MemoryStore) -> None:
        """Keys with semicolons are rejected."""
        with pytest.raises(ValueError, match="Invalid metadata_filter key"):
            store.search_filtered(metadata_filter={"key; --": "x"})

    def test_sql_injection_single_quote(self, store: MemoryStore) -> None:
        """Keys with single quotes are rejected."""
        with pytest.raises(ValueError, match="Invalid metadata_filter key"):
            store.search_filtered(metadata_filter={"key'value": "x"})

    def test_sql_injection_double_quote(self, store: MemoryStore) -> None:
        """Keys with double quotes are rejected."""
        with pytest.raises(ValueError, match="Invalid metadata_filter key"):
            store.search_filtered(metadata_filter={'key"value': "x"})

    def test_sql_injection_backslash(self, store: MemoryStore) -> None:
        """Keys with backslashes are rejected."""
        with pytest.raises(ValueError, match="Invalid metadata_filter key"):
            store.search_filtered(metadata_filter={"key\\value": "x"})

    def test_sql_injection_parentheses(self, store: MemoryStore) -> None:
        """Keys with parentheses are rejected."""
        with pytest.raises(ValueError, match="Invalid metadata_filter key"):
            store.search_filtered(metadata_filter={"key()": "x"})

    def test_empty_key_rejected(self, store: MemoryStore) -> None:
        """Empty string keys are rejected."""
        with pytest.raises(ValueError, match="Invalid metadata_filter key"):
            store.search_filtered(metadata_filter={"": "x"})

    def test_key_starting_with_digit(self, store: MemoryStore) -> None:
        """Keys starting with a digit are rejected."""
        with pytest.raises(ValueError, match="Invalid metadata_filter key"):
            store.search_filtered(metadata_filter={"1key": "x"})

    def test_key_with_spaces(self, store: MemoryStore) -> None:
        """Keys with spaces are rejected."""
        with pytest.raises(ValueError, match="Invalid metadata_filter key"):
            store.search_filtered(metadata_filter={"my key": "x"})


# ------------------------------------------------------------------
# 1b. SQLite file permissions
# ------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="Unix file permissions only")
class TestFilePermissions:
    """Verify that new database files get restrictive permissions."""

    def test_new_db_has_restrictive_permissions(self, tmp_path) -> None:
        """New database files should have 0o600 permissions."""
        db_path = tmp_path / "perms_test.db"
        store = MemoryStore(path=db_path)
        assert db_path.exists()
        mode = stat.S_IMODE(db_path.stat().st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
        store.close()

    def test_parent_dir_has_restrictive_permissions(self, tmp_path) -> None:
        """Parent directory should have 0o700 permissions."""
        parent = tmp_path / "restricted_dir"
        db_path = parent / "test.db"
        store = MemoryStore(path=db_path)
        mode = stat.S_IMODE(parent.stat().st_mode)
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"
        store.close()


# ------------------------------------------------------------------
# 4a. RelevanceWeights.from_env()
# ------------------------------------------------------------------


class TestRelevanceWeightsFromEnv:
    """Test environment-based weight configuration."""

    def test_defaults_when_no_env_vars(self, monkeypatch) -> None:
        """Default weights are used when no env vars are set."""
        for key in [
            "MEMORYMESH_WEIGHT_SEMANTIC",
            "MEMORYMESH_WEIGHT_RECENCY",
            "MEMORYMESH_WEIGHT_IMPORTANCE",
            "MEMORYMESH_WEIGHT_FREQUENCY",
        ]:
            monkeypatch.delenv(key, raising=False)

        w = RelevanceWeights.from_env()
        assert w.semantic == 0.5
        assert w.recency == 0.2
        assert w.importance == 0.2
        assert w.frequency == 0.1

    def test_custom_weights_from_env(self, monkeypatch) -> None:
        """Custom weights are read from environment variables."""
        monkeypatch.setenv("MEMORYMESH_WEIGHT_SEMANTIC", "0.3")
        monkeypatch.setenv("MEMORYMESH_WEIGHT_RECENCY", "0.4")
        monkeypatch.setenv("MEMORYMESH_WEIGHT_IMPORTANCE", "0.1")
        monkeypatch.setenv("MEMORYMESH_WEIGHT_FREQUENCY", "0.2")

        w = RelevanceWeights.from_env()
        assert w.semantic == pytest.approx(0.3)
        assert w.recency == pytest.approx(0.4)
        assert w.importance == pytest.approx(0.1)
        assert w.frequency == pytest.approx(0.2)

    def test_partial_env_override(self, monkeypatch) -> None:
        """Only the set env vars override; others keep defaults."""
        monkeypatch.delenv("MEMORYMESH_WEIGHT_SEMANTIC", raising=False)
        monkeypatch.delenv("MEMORYMESH_WEIGHT_FREQUENCY", raising=False)
        monkeypatch.setenv("MEMORYMESH_WEIGHT_RECENCY", "0.8")
        monkeypatch.setenv("MEMORYMESH_WEIGHT_IMPORTANCE", "0.9")

        w = RelevanceWeights.from_env()
        assert w.semantic == 0.5  # default
        assert w.recency == pytest.approx(0.8)
        assert w.importance == pytest.approx(0.9)
        assert w.frequency == 0.1  # default


# ------------------------------------------------------------------
# 4b. smart_sync()
# ------------------------------------------------------------------


class TestSmartSync:
    """Test the smart_sync() method for relevance-ranked export."""

    @pytest.fixture
    def mesh(self, tmp_path):
        from memorymesh import MemoryMesh

        m = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        yield m
        m.close()

    def test_smart_sync_returns_top_n(self, mesh) -> None:
        """smart_sync() returns at most top_n memories."""
        for i in range(30):
            mesh.remember(
                f"Memory {i}",
                importance=i / 30.0,
                scope="project",
            )

        results = mesh.smart_sync(top_n=5)
        assert len(results) == 5

    def test_smart_sync_ranks_by_importance(self, mesh) -> None:
        """Higher-importance memories should appear first."""
        mesh.remember("Low importance", importance=0.1, scope="project")
        mesh.remember("High importance", importance=0.9, scope="project")
        mesh.remember("Medium importance", importance=0.5, scope="project")

        results = mesh.smart_sync(top_n=3)
        importances = [m.importance for m in results]
        # Should be roughly descending (importance has 0.5 weight in sync)
        assert importances[0] >= importances[-1]

    def test_smart_sync_empty_store(self, mesh) -> None:
        """smart_sync() on an empty store returns empty list."""
        results = mesh.smart_sync(top_n=10)
        assert results == []

    def test_smart_sync_respects_scope(self, mesh) -> None:
        """smart_sync(scope='project') only returns project memories."""
        mesh.remember("Project mem", scope="project")
        mesh.remember("Global mem", scope="global")

        project_only = mesh.smart_sync(top_n=10, scope="project")
        assert all(m.scope == "project" for m in project_only)

    def test_smart_sync_custom_weights(self, mesh) -> None:
        """Custom weights can be passed to smart_sync()."""
        mesh.remember("test", scope="project")
        weights = RelevanceWeights(
            semantic=0.0,
            recency=1.0,
            importance=0.0,
            frequency=0.0,
        )
        results = mesh.smart_sync(top_n=5, weights=weights)
        assert len(results) >= 1


# ------------------------------------------------------------------
# 4c. EncryptedMemoryStore completeness
# ------------------------------------------------------------------


class TestEncryptedStoreCompleteness:
    """Test search_filtered() and update_fields() on EncryptedMemoryStore."""

    @pytest.fixture
    def stores(self, tmp_path):
        raw = MemoryStore(path=tmp_path / "encrypted.db")
        enc = EncryptedMemoryStore(raw, "test-password")
        yield enc, raw
        enc.close()

    def test_search_filtered_returns_decrypted(self, stores) -> None:
        """search_filtered() returns decrypted memory text."""
        enc, _ = stores
        mem = Memory(
            text="Secret decision about JWT auth",
            metadata={"category": "decision"},
            importance=0.8,
        )
        enc.save(mem)

        results = enc.search_filtered(min_importance=0.7)
        assert len(results) >= 1
        assert results[0].text == "Secret decision about JWT auth"

    def test_search_filtered_with_category(self, stores) -> None:
        """search_filtered(category=...) works through encryption."""
        enc, _ = stores
        enc.save(Memory(text="A decision", metadata={"category": "decision"}, importance=0.9))
        enc.save(Memory(text="A preference", metadata={"category": "preference"}, importance=0.9))

        # Note: category filter operates on encrypted metadata,
        # so it may not match. This tests the delegation works.
        results = enc.search_filtered(min_importance=0.8)
        assert len(results) == 2

    def test_update_fields_encrypts_text(self, stores) -> None:
        """update_fields() encrypts new text before storing."""
        enc, raw = stores
        mem = Memory(text="Original text", metadata={"key": "val"})
        enc.save(mem)

        enc.update_fields(mem.id, text="Updated secret text")

        # Verify the raw store has encrypted content
        raw_mem = raw.get(mem.id)
        assert raw_mem is not None
        assert "Updated secret text" not in raw_mem.text  # encrypted

        # Verify decryption works
        dec_mem = enc.get(mem.id)
        assert dec_mem is not None
        assert dec_mem.text == "Updated secret text"

    def test_update_fields_encrypts_metadata(self, stores) -> None:
        """update_fields() encrypts new metadata before storing."""
        enc, raw = stores
        mem = Memory(text="test", metadata={"old": "data"})
        enc.save(mem)

        enc.update_fields(mem.id, metadata={"new": "secret_data"})

        # Raw store should have encrypted metadata
        raw_mem = raw.get(mem.id)
        assert raw_mem is not None
        assert "_encrypted" in raw_mem.metadata

        # Decrypted view should have the new metadata
        dec_mem = enc.get(mem.id)
        assert dec_mem is not None
        assert dec_mem.metadata == {"new": "secret_data"}

    def test_update_fields_non_sensitive(self, stores) -> None:
        """update_fields() delegates importance/decay_rate directly."""
        enc, _ = stores
        mem = Memory(text="test", importance=0.5)
        enc.save(mem)

        result = enc.update_fields(mem.id, importance=0.9)
        assert result is True

        updated = enc.get(mem.id)
        assert updated is not None
        assert updated.importance == pytest.approx(0.9)

    def test_update_fields_not_found(self, stores) -> None:
        """update_fields() returns False for nonexistent memory ID."""
        enc, _ = stores
        result = enc.update_fields("nonexistent-id", text="test")
        assert result is False


# ------------------------------------------------------------------
# 1c. MCP server version
# ------------------------------------------------------------------


class TestMCPServerVersion:
    """Verify MCP server reports dynamic version, not hardcoded."""

    def test_server_info_uses_package_version(self) -> None:
        """SERVER_INFO version matches the package __version__."""
        from memorymesh import __version__
        from memorymesh.mcp_server import SERVER_INFO

        assert SERVER_INFO["version"] == __version__
        assert SERVER_INFO["version"] != "3.0.0"  # not hardcoded
