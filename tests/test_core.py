"""Tests for the main MemoryMesh class.

Covers initialization, remember/recall/forget lifecycle, metadata handling,
counting, listing, and the search() alias.  All tests use ``embedding="none"``
so they run without any ML dependencies.
"""

from __future__ import annotations

from memorymesh import MemoryMesh

# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------


def test_init_default(tmp_path, monkeypatch):
    """MemoryMesh initializes with sensible defaults when no arguments given."""
    # Redirect the default storage directory so we don't touch the real home dir.
    monkeypatch.setenv("MEMORYMESH_DIR", str(tmp_path))
    mesh = MemoryMesh(
        embedding="none", path=str(tmp_path / "default.db"), global_path=str(tmp_path / "global.db")
    )
    assert mesh is not None
    assert mesh.count() == 0


def test_init_custom_path(tmp_path):
    """MemoryMesh creates a database at the specified path."""
    db_path = tmp_path / "custom" / "test.db"
    mesh = MemoryMesh(path=str(db_path), embedding="none", global_path=str(tmp_path / "global.db"))
    assert mesh is not None
    # The database file should exist on disk after initialization.
    assert db_path.exists()


# ------------------------------------------------------------------
# remember()
# ------------------------------------------------------------------


def test_remember_returns_id(tmp_path):
    """remember() returns a string that looks like a hex UUID."""
    mesh = MemoryMesh(
        path=str(tmp_path / "mem.db"), embedding="none", global_path=str(tmp_path / "global.db")
    )
    mem_id = mesh.remember("Hello, world!")
    assert isinstance(mem_id, str)
    assert len(mem_id) > 0
    # Should be a valid hex string (UUID4 hex is 32 chars).
    int(mem_id, 16)


def test_remember_and_recall(tmp_path):
    """Remembering text and then recalling with a related query returns it."""
    mesh = MemoryMesh(
        path=str(tmp_path / "mem.db"), embedding="none", global_path=str(tmp_path / "global.db")
    )
    mesh.remember("User prefers Python and dark mode")
    mesh.remember("User likes hiking on weekends")

    results = mesh.recall("Python")
    assert len(results) >= 1
    texts = [m.text for m in results]
    assert any("Python" in t for t in texts)


def test_remember_with_metadata(tmp_path):
    """Metadata passed to remember() is preserved and returned on recall."""
    mesh = MemoryMesh(
        path=str(tmp_path / "mem.db"), embedding="none", global_path=str(tmp_path / "global.db")
    )
    meta = {"source": "chat", "session_id": "abc-123"}
    mem_id = mesh.remember("Important meeting tomorrow", metadata=meta)

    results = mesh.recall("meeting")
    assert len(results) >= 1
    matched = [m for m in results if m.id == mem_id]
    assert len(matched) == 1
    assert matched[0].metadata["source"] == "chat"
    assert matched[0].metadata["session_id"] == "abc-123"


# ------------------------------------------------------------------
# forget()
# ------------------------------------------------------------------


def test_forget(tmp_path):
    """Forgetting a memory by ID removes it from recall results."""
    mesh = MemoryMesh(
        path=str(tmp_path / "mem.db"), embedding="none", global_path=str(tmp_path / "global.db")
    )
    mem_id = mesh.remember("Temporary note")

    assert mesh.count() == 1
    result = mesh.forget(mem_id)
    assert result is True
    assert mesh.count() == 0

    results = mesh.recall("Temporary note")
    assert len(results) == 0


def test_forget_nonexistent(tmp_path):
    """Forgetting a non-existent ID returns False."""
    mesh = MemoryMesh(
        path=str(tmp_path / "mem.db"), embedding="none", global_path=str(tmp_path / "global.db")
    )
    result = mesh.forget("does_not_exist_000000000000")
    assert result is False


def test_forget_all(tmp_path):
    """forget_all() clears every stored memory."""
    mesh = MemoryMesh(
        path=str(tmp_path / "mem.db"), embedding="none", global_path=str(tmp_path / "global.db")
    )
    mesh.remember("Memory one")
    mesh.remember("Memory two")
    mesh.remember("Memory three")
    assert mesh.count() == 3

    mesh.forget_all()
    assert mesh.count() == 0


# ------------------------------------------------------------------
# count() and list()
# ------------------------------------------------------------------


def test_count(tmp_path):
    """count() reflects the number of stored memories."""
    mesh = MemoryMesh(
        path=str(tmp_path / "mem.db"), embedding="none", global_path=str(tmp_path / "global.db")
    )
    assert mesh.count() == 0

    mesh.remember("First")
    assert mesh.count() == 1

    mesh.remember("Second")
    mesh.remember("Third")
    assert mesh.count() == 3


def test_list(tmp_path):
    """list() supports limit and offset for pagination."""
    mesh = MemoryMesh(
        path=str(tmp_path / "mem.db"), embedding="none", global_path=str(tmp_path / "global.db")
    )
    for i in range(5):
        mesh.remember(f"Memory number {i}")

    # Default list should return all.
    all_mems = mesh.list()
    assert len(all_mems) == 5

    # Limit to 2.
    page = mesh.list(limit=2)
    assert len(page) == 2

    # Offset skips the first 3.
    page = mesh.list(limit=10, offset=3)
    assert len(page) == 2


# ------------------------------------------------------------------
# search() alias
# ------------------------------------------------------------------


def test_search_alias(tmp_path):
    """search() works the same as recall()."""
    mesh = MemoryMesh(
        path=str(tmp_path / "mem.db"), embedding="none", global_path=str(tmp_path / "global.db")
    )
    mesh.remember("Dogs are great pets")

    recall_results = mesh.recall("pets")
    search_results = mesh.search("pets")

    # Both should return the same memory (or at least the same set).
    recall_texts = {m.text for m in recall_results}
    search_texts = {m.text for m in search_results}
    assert recall_texts == search_texts
