"""Tests for the MemoryStore SQLite backend.

Covers CRUD operations, listing with pagination, counting, clearing, and
basic thread safety.  All tests use temporary directories so they never
touch the user's real database.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from memorymesh.memory import Memory
from memorymesh.store import MemoryStore

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_memory(text: str = "test memory", **kwargs) -> Memory:
    """Create a Memory instance with sensible defaults for testing."""
    return Memory(text=text, **kwargs)


# ------------------------------------------------------------------
# Store creation
# ------------------------------------------------------------------


def test_create_store(tmp_path):
    """MemoryStore creates the SQLite file and schema on initialization."""
    db_path = tmp_path / "test.db"
    store = MemoryStore(path=db_path)
    assert db_path.exists()
    # Should be able to count rows (table exists).
    assert store.count() == 0
    store.close()


# ------------------------------------------------------------------
# Save and get
# ------------------------------------------------------------------


def test_save_and_get(tmp_path):
    """Saving a memory and retrieving it by ID returns an equivalent object."""
    store = MemoryStore(path=tmp_path / "test.db")
    mem = _make_memory("Remember this important fact")
    store.save(mem)

    retrieved = store.get(mem.id)
    assert retrieved is not None
    assert retrieved.id == mem.id
    assert retrieved.text == mem.text
    assert retrieved.importance == mem.importance
    assert retrieved.metadata == mem.metadata
    store.close()


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------


def test_delete(tmp_path):
    """Deleting a memory removes it from the store."""
    store = MemoryStore(path=tmp_path / "test.db")
    mem = _make_memory("Gone soon")
    store.save(mem)
    assert store.get(mem.id) is not None

    deleted = store.delete(mem.id)
    assert deleted is True
    assert store.get(mem.id) is None
    store.close()


def test_delete_nonexistent(tmp_path):
    """Deleting a non-existent ID returns False."""
    store = MemoryStore(path=tmp_path / "test.db")
    assert store.delete("no_such_id") is False
    store.close()


# ------------------------------------------------------------------
# list_all with pagination
# ------------------------------------------------------------------


def test_list_all(tmp_path):
    """list_all supports limit and offset for pagination."""
    store = MemoryStore(path=tmp_path / "test.db")
    for i in range(10):
        store.save(_make_memory(f"Memory {i}"))

    # Default returns up to 100, we have 10.
    all_mems = store.list_all()
    assert len(all_mems) == 10

    # Limit.
    page = store.list_all(limit=3)
    assert len(page) == 3

    # Offset.
    page = store.list_all(limit=5, offset=8)
    assert len(page) == 2  # Only 2 remaining after offset=8 of 10.

    store.close()


# ------------------------------------------------------------------
# Count
# ------------------------------------------------------------------


def test_count(tmp_path):
    """count() accurately reflects the number of stored memories."""
    store = MemoryStore(path=tmp_path / "test.db")
    assert store.count() == 0

    store.save(_make_memory("One"))
    assert store.count() == 1

    store.save(_make_memory("Two"))
    store.save(_make_memory("Three"))
    assert store.count() == 3

    store.close()


# ------------------------------------------------------------------
# Clear
# ------------------------------------------------------------------


def test_clear(tmp_path):
    """clear() removes all memories and returns the deleted count."""
    store = MemoryStore(path=tmp_path / "test.db")
    for i in range(5):
        store.save(_make_memory(f"Memory {i}"))
    assert store.count() == 5

    deleted = store.clear()
    assert deleted == 5
    assert store.count() == 0
    store.close()


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------


def test_thread_safety(tmp_path):
    """Multiple threads can save memories concurrently without errors."""
    store = MemoryStore(path=tmp_path / "test.db")
    num_threads = 8
    memories_per_thread = 10

    def _save_batch(thread_id: int) -> int:
        """Save a batch of memories and return the count saved."""
        for i in range(memories_per_thread):
            mem = _make_memory(f"Thread {thread_id} - memory {i}")
            store.save(mem)
        return memories_per_thread

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(_save_batch, t) for t in range(num_threads)]
        results = [f.result() for f in as_completed(futures)]

    assert sum(results) == num_threads * memories_per_thread
    assert store.count() == num_threads * memories_per_thread
    store.close()
