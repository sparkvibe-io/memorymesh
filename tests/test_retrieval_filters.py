"""Tests for retrieval filters in recall() and store.search_filtered()."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from datetime import datetime, timezone

import pytest

from memorymesh.core import MemoryMesh
from memorymesh.memory import Memory
from memorymesh.store import MemoryStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test databases."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def store(tmp_dir: str) -> Generator[MemoryStore, None, None]:
    """Create a MemoryStore with test data."""
    db_path = os.path.join(tmp_dir, "test.db")
    s = MemoryStore(path=db_path)

    # Save test memories with different categories and importance
    memories = [
        Memory(
            text="User prefers dark mode",
            metadata={"category": "preference"},
            importance=0.8,
            decay_rate=0.01,
        ),
        Memory(
            text="Always use type hints",
            metadata={"category": "guardrail"},
            importance=0.9,
            decay_rate=0.01,
        ),
        Memory(
            text="SQLite is the storage backend",
            metadata={"category": "decision"},
            importance=0.7,
            decay_rate=0.01,
        ),
        Memory(
            text="Fixed off-by-one error in pagination",
            metadata={"category": "mistake"},
            importance=0.6,
            decay_rate=0.01,
        ),
        Memory(
            text="Low importance note",
            metadata={"category": "context"},
            importance=0.2,
            decay_rate=0.01,
        ),
    ]

    for m in memories:
        s.save(m)

    yield s
    s.close()


@pytest.fixture
def mesh(tmp_dir: str) -> Generator[MemoryMesh, None, None]:
    """Create a MemoryMesh with test data."""
    db_path = os.path.join(tmp_dir, "project.db")
    global_path = os.path.join(tmp_dir, "global.db")
    m = MemoryMesh(path=db_path, global_path=global_path, embedding="none")

    # Add project memories
    m.remember("User prefers dark mode", category="preference", importance=0.8)
    m.remember("Always use type hints", category="guardrail", importance=0.9)
    m.remember("SQLite is the storage backend", category="decision", importance=0.7)
    m.remember("Fixed off-by-one error", category="mistake", importance=0.6)
    m.remember("Low importance context", category="context", importance=0.2)

    yield m
    m.close()


# ---------------------------------------------------------------------------
# Store-level search_filtered tests
# ---------------------------------------------------------------------------


class TestStoreSearchFiltered:
    """Tests for MemoryStore.search_filtered()."""

    def test_filter_by_category(self, store: MemoryStore) -> None:
        results = store.search_filtered(category="preference")
        assert len(results) == 1
        assert results[0].text == "User prefers dark mode"

    def test_filter_by_category_no_match(self, store: MemoryStore) -> None:
        results = store.search_filtered(category="personality")
        assert len(results) == 0

    def test_filter_by_min_importance(self, store: MemoryStore) -> None:
        results = store.search_filtered(min_importance=0.7)
        assert len(results) == 3
        for r in results:
            assert r.importance >= 0.7

    def test_filter_by_high_min_importance(self, store: MemoryStore) -> None:
        results = store.search_filtered(min_importance=0.85)
        assert len(results) == 1
        assert results[0].text == "Always use type hints"

    def test_filter_by_time_range(self, store: MemoryStore) -> None:
        # All memories were just created, use a wide range
        now = datetime.now(timezone.utc).isoformat()
        results = store.search_filtered(time_range=("2020-01-01T00:00:00", now))
        assert len(results) == 5

    def test_filter_by_time_range_empty(self, store: MemoryStore) -> None:
        results = store.search_filtered(time_range=("2000-01-01T00:00:00", "2000-01-02T00:00:00"))
        assert len(results) == 0

    def test_filter_by_metadata(self, store: MemoryStore) -> None:
        results = store.search_filtered(metadata_filter={"category": "guardrail"})
        assert len(results) == 1
        assert results[0].text == "Always use type hints"

    def test_combined_filters(self, store: MemoryStore) -> None:
        results = store.search_filtered(
            category="decision",
            min_importance=0.5,
        )
        assert len(results) == 1
        assert results[0].text == "SQLite is the storage backend"

    def test_no_filters_returns_all(self, store: MemoryStore) -> None:
        results = store.search_filtered()
        assert len(results) == 5

    def test_filter_respects_limit(self, store: MemoryStore) -> None:
        results = store.search_filtered(limit=2)
        assert len(results) == 2

    def test_filter_ordered_by_importance(self, store: MemoryStore) -> None:
        results = store.search_filtered()
        importances = [r.importance for r in results]
        assert importances == sorted(importances, reverse=True)


# ---------------------------------------------------------------------------
# Core recall() filter integration tests
# ---------------------------------------------------------------------------


class TestRecallFilters:
    """Tests for recall() with filter parameters."""

    def test_recall_category_filter(self, mesh: MemoryMesh) -> None:
        results = mesh.recall(query="dark", category="preference")
        assert len(results) >= 1
        for r in results:
            assert r.metadata.get("category") == "preference"

    def test_recall_min_importance_filter(self, mesh: MemoryMesh) -> None:
        results = mesh.recall(query="mode", min_importance=0.7, k=20)
        # All results should originally have importance >= 0.7 (from SQL filter).
        # Time decay may reduce importance slightly, so use a small epsilon.
        for r in results:
            assert r.importance >= 0.7 - 0.01

    def test_recall_time_range_filter(self, mesh: MemoryMesh) -> None:
        now = datetime.now(timezone.utc).isoformat()
        results = mesh.recall(
            query="type",
            time_range=("2020-01-01T00:00:00", now),
            k=20,
        )
        assert len(results) >= 1

    def test_recall_time_range_empty(self, mesh: MemoryMesh) -> None:
        results = mesh.recall(
            query="type",
            time_range=("2000-01-01T00:00:00", "2000-01-02T00:00:00"),
        )
        assert len(results) == 0

    def test_recall_metadata_filter(self, mesh: MemoryMesh) -> None:
        results = mesh.recall(
            query="hints",
            metadata_filter={"category": "guardrail"},
            k=20,
        )
        for r in results:
            assert r.metadata.get("category") == "guardrail"

    def test_recall_combined_filters(self, mesh: MemoryMesh) -> None:
        results = mesh.recall(
            query="backend",
            category="decision",
            min_importance=0.5,
        )
        for r in results:
            assert r.metadata.get("category") == "decision"
            assert r.importance >= 0.5

    def test_recall_no_filters_works_normally(self, mesh: MemoryMesh) -> None:
        # Without filters, recall should still work with keyword matching
        results = mesh.recall(query="dark mode", k=5)
        assert len(results) >= 1

    def test_recall_filter_empty_result(self, mesh: MemoryMesh) -> None:
        results = mesh.recall(query="anything", category="personality")
        assert len(results) == 0

    def test_recall_filter_min_importance_zero(self, mesh: MemoryMesh) -> None:
        results = mesh.recall(query="context", min_importance=0.0, k=20)
        assert len(results) >= 1
