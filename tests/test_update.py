"""Tests for the update API: store.update_fields() and core.update()."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from memorymesh import MemoryMesh
from memorymesh.embeddings import EmbeddingProvider
from memorymesh.store import _UNSET, MemoryStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_dir():
    """Provide a temporary directory for test databases."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture()
def mesh(tmp_dir: str) -> Generator[MemoryMesh, None, None]:
    """Create a MemoryMesh with both project and global stores using NoopEmbedding."""
    m = MemoryMesh(
        path=os.path.join(tmp_dir, "project", "memories.db"),
        global_path=os.path.join(tmp_dir, "global", "global.db"),
        embedding="none",
    )
    yield m
    m.close()


@pytest.fixture()
def store(tmp_dir: str) -> Generator[MemoryStore, None, None]:
    """Create a standalone MemoryStore for low-level tests."""
    s = MemoryStore(path=os.path.join(tmp_dir, "store", "test.db"))
    yield s
    s.close()


# ---------------------------------------------------------------------------
# store.update_fields tests
# ---------------------------------------------------------------------------


class TestStoreUpdateFields:
    """Tests for MemoryStore.update_fields()."""

    def test_update_text(self, mesh: MemoryMesh) -> None:
        """Updating text via store.update_fields changes the text."""
        mid = mesh.remember("original text", scope="project")
        store = mesh._project_store
        assert store is not None
        result = store.update_fields(mid, text="updated text")
        assert result is True
        mem = store.get(mid)
        assert mem is not None
        assert mem.text == "updated text"

    def test_update_fields_not_found(self, store: MemoryStore) -> None:
        """update_fields returns False for a nonexistent memory ID."""
        result = store.update_fields("nonexistent-id", text="new text")
        assert result is False

    def test_update_importance_via_store(self, mesh: MemoryMesh) -> None:
        """Updating importance via store.update_fields changes the value."""
        mid = mesh.remember("some text", importance=0.5, scope="project")
        store = mesh._project_store
        assert store is not None
        store.update_fields(mid, importance=0.9)
        mem = store.get(mid)
        assert mem is not None
        assert abs(mem.importance - 0.9) < 0.01

    def test_update_metadata_via_store(self, mesh: MemoryMesh) -> None:
        """Updating metadata via store.update_fields replaces metadata."""
        mid = mesh.remember("some text", metadata={"a": 1}, scope="project")
        store = mesh._project_store
        assert store is not None
        store.update_fields(mid, metadata={"b": 2})
        mem = store.get(mid)
        assert mem is not None
        assert mem.metadata == {"b": 2}

    def test_update_refreshes_updated_at(self, mesh: MemoryMesh) -> None:
        """update_fields always refreshes the updated_at timestamp."""
        mid = mesh.remember("some text", scope="project")
        store = mesh._project_store
        assert store is not None
        mem_before = store.get(mid)
        assert mem_before is not None
        store.update_fields(mid, importance=0.8)
        mem_after = store.get(mid)
        assert mem_after is not None
        assert mem_after.updated_at >= mem_before.updated_at

    def test_unset_sentinel_is_distinct(self) -> None:
        """The _UNSET sentinel is a unique object, not None."""
        assert _UNSET is not None
        assert _UNSET != None  # noqa: E711


# ---------------------------------------------------------------------------
# core.update tests
# ---------------------------------------------------------------------------


class TestCoreUpdate:
    """Tests for MemoryMesh.update()."""

    def test_update_text(self, mesh: MemoryMesh) -> None:
        """Updating text via core.update changes the stored text."""
        mid = mesh.remember("original", scope="project")
        updated = mesh.update(mid, text="changed")
        assert updated is not None
        assert updated.text == "changed"
        # Verify persistence.
        fetched = mesh.get(mid)
        assert fetched is not None
        assert fetched.text == "changed"

    def test_update_importance(self, mesh: MemoryMesh) -> None:
        """Updating importance via core.update changes the value."""
        mid = mesh.remember("test", importance=0.3, scope="project")
        updated = mesh.update(mid, importance=0.95)
        assert updated is not None
        assert abs(updated.importance - 0.95) < 0.01

    def test_update_metadata(self, mesh: MemoryMesh) -> None:
        """Updating metadata via core.update replaces the metadata dict."""
        mid = mesh.remember("test", metadata={"old": True}, scope="project")
        updated = mesh.update(mid, metadata={"new": True})
        assert updated is not None
        assert updated.metadata == {"new": True}

    def test_update_decay_rate(self, mesh: MemoryMesh) -> None:
        """Updating decay_rate via core.update changes the value."""
        mid = mesh.remember("test", decay_rate=0.01, scope="project")
        updated = mesh.update(mid, decay_rate=0.05)
        assert updated is not None
        assert abs(updated.decay_rate - 0.05) < 0.001

    def test_update_multiple_fields(self, mesh: MemoryMesh) -> None:
        """Multiple fields can be updated in a single call."""
        mid = mesh.remember("old text", importance=0.3, scope="project")
        updated = mesh.update(mid, text="new text", importance=0.8)
        assert updated is not None
        assert updated.text == "new text"
        assert abs(updated.importance - 0.8) < 0.01

    def test_update_not_found(self, mesh: MemoryMesh) -> None:
        """update() returns None for a nonexistent memory ID."""
        result = mesh.update("nonexistent-id", text="hello")
        assert result is None

    def test_update_scope_migration_project_to_global(self, mesh: MemoryMesh) -> None:
        """Moving a memory from project to global scope works correctly."""
        mid = mesh.remember("migrate me", scope="project")
        # Verify it's in project scope.
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "project"

        updated = mesh.update(mid, scope="global")
        assert updated is not None
        assert updated.scope == "global"
        assert updated.text == "migrate me"

        # Verify it's gone from project store.
        assert mesh._project_store is not None
        assert mesh._project_store.get(mid) is None
        # Verify it's in global store.
        assert mesh._global_store.get(mid) is not None

    def test_update_scope_migration_global_to_project(self, mesh: MemoryMesh) -> None:
        """Moving a memory from global to project scope works correctly."""
        mid = mesh.remember("migrate back", scope="global")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "global"

        updated = mesh.update(mid, scope="project")
        assert updated is not None
        assert updated.scope == "project"

        # Verify it's gone from global store.
        assert mesh._global_store.get(mid) is None
        # Verify it's in project store.
        assert mesh._project_store is not None
        assert mesh._project_store.get(mid) is not None

    def test_update_scope_migration_with_field_changes(self, mesh: MemoryMesh) -> None:
        """Scope migration can also update fields simultaneously."""
        mid = mesh.remember("original text", importance=0.3, scope="project")
        updated = mesh.update(mid, text="new text", importance=0.9, scope="global")
        assert updated is not None
        assert updated.scope == "global"
        assert updated.text == "new text"
        assert abs(updated.importance - 0.9) < 0.01

    def test_update_text_recomputes_embedding(self, tmp_dir: str) -> None:
        """When text changes, the embedding should be recomputed."""
        mock_embedder = MagicMock(spec=EmbeddingProvider)
        mock_embedder.embed.return_value = [0.1, 0.2, 0.3]

        m = MemoryMesh(
            path=os.path.join(tmp_dir, "emb_project", "memories.db"),
            global_path=os.path.join(tmp_dir, "emb_global", "global.db"),
            embedding=mock_embedder,
        )
        try:
            mid = m.remember("first text", scope="project")
            initial_call_count = mock_embedder.embed.call_count

            m.update(mid, text="second text")
            # embed should have been called again for the new text.
            assert mock_embedder.embed.call_count > initial_call_count
        finally:
            m.close()

    def test_update_preserves_created_at(self, mesh: MemoryMesh) -> None:
        """Updating a memory should not change its created_at timestamp."""
        mid = mesh.remember("test", scope="project")
        original = mesh.get(mid)
        assert original is not None

        updated = mesh.update(mid, text="changed")
        assert updated is not None
        assert updated.created_at == original.created_at

    def test_update_same_scope_no_migration(self, mesh: MemoryMesh) -> None:
        """Passing scope equal to current scope does an in-place update."""
        mid = mesh.remember("test", scope="project")
        updated = mesh.update(mid, text="changed", scope="project")
        assert updated is not None
        assert updated.text == "changed"
        assert updated.scope == "project"
        # Should still be in project store.
        assert mesh._project_store is not None
        assert mesh._project_store.get(mid) is not None
