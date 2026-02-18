"""Tests for contradiction detection."""

from __future__ import annotations

import pytest

from memorymesh import MemoryMesh
from memorymesh.contradiction import ConflictMode, _word_overlap, find_contradictions
from memorymesh.memory import Memory
from memorymesh.store import MemoryStore


@pytest.fixture
def tmp_mesh(tmp_path):
    """Create a temporary MemoryMesh with project + global stores."""
    proj_db = str(tmp_path / "project" / "memories.db")
    glob_db = str(tmp_path / "global" / "global.db")
    mesh = MemoryMesh(path=proj_db, global_path=glob_db, embedding="none")
    yield mesh
    mesh.close()


@pytest.fixture
def tmp_store(tmp_path):
    """Create a temporary MemoryStore."""
    db_path = str(tmp_path / "test.db")
    store = MemoryStore(path=db_path)
    yield store
    store.close()


class TestWordOverlap:
    def test_identical_texts(self):
        assert _word_overlap("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert _word_overlap("hello world", "foo bar") == 0.0

    def test_partial_overlap(self):
        result = _word_overlap("the cat sat", "the dog sat")
        assert 0.0 < result < 1.0

    def test_empty_text_a(self):
        assert _word_overlap("", "hello") == 0.0

    def test_empty_text_b(self):
        assert _word_overlap("hello", "") == 0.0

    def test_both_empty(self):
        assert _word_overlap("", "") == 0.0

    def test_case_insensitive(self):
        assert _word_overlap("Hello World", "hello world") == 1.0

    def test_subset_overlap(self):
        """A subset of words gives partial overlap, not 1.0."""
        result = _word_overlap("a b c d", "a b")
        assert 0.0 < result < 1.0
        # Jaccard: intersection=2, union=4 -> 0.5
        assert result == pytest.approx(0.5)


class TestFindContradictions:
    def test_no_existing_memories(self, tmp_store):
        result = find_contradictions("test text", None, tmp_store)
        assert result == []

    def test_similar_text_detected(self, tmp_store):
        mem = Memory(text="The server runs on port 3000")
        tmp_store.save(mem)

        # Very similar text should be detected (keyword mode)
        result = find_contradictions(
            "The server runs on port 4000",
            None,
            tmp_store,
            threshold=0.5,  # lower threshold for keyword mode
        )
        assert len(result) > 0

    def test_unrelated_text_not_detected(self, tmp_store):
        mem = Memory(text="The server runs on port 3000")
        tmp_store.save(mem)

        result = find_contradictions(
            "I prefer dark mode for my editor",
            None,
            tmp_store,
        )
        assert len(result) == 0

    def test_max_candidates_respected(self, tmp_store):
        for i in range(10):
            mem = Memory(text=f"Server configuration item {i} port setting")
            tmp_store.save(mem)

        result = find_contradictions(
            "Server configuration port setting",
            None,
            tmp_store,
            threshold=0.3,
            max_candidates=3,
        )
        assert len(result) <= 3

    def test_results_sorted_by_similarity_descending(self, tmp_store):
        # Store texts with varying overlap
        mem1 = Memory(text="alpha beta gamma delta")
        mem2 = Memory(text="alpha beta gamma delta epsilon zeta")
        tmp_store.save(mem1)
        tmp_store.save(mem2)

        result = find_contradictions(
            "alpha beta gamma delta",
            None,
            tmp_store,
            threshold=0.3,
        )
        if len(result) >= 2:
            assert result[0][1] >= result[1][1]

    def test_threshold_filtering(self, tmp_store):
        mem = Memory(text="the cat sat on the mat")
        tmp_store.save(mem)

        # High threshold should filter out loosely related text
        result = find_contradictions(
            "the dog sat on the rug",
            None,
            tmp_store,
            threshold=0.9,
        )
        assert len(result) == 0

    def test_exact_duplicate_found(self, tmp_store):
        mem = Memory(text="The database host is localhost")
        tmp_store.save(mem)

        result = find_contradictions(
            "The database host is localhost",
            None,
            tmp_store,
            threshold=0.75,
        )
        assert len(result) == 1
        assert result[0][1] == pytest.approx(1.0)


class TestConflictMode:
    def test_keep_both_mode(self, tmp_mesh):
        tmp_mesh.remember("Server runs on port 3000")
        mid = tmp_mesh.remember(
            "Server runs on port 4000",
            on_conflict="keep_both",
        )
        assert mid != ""
        assert tmp_mesh.count() == 2

    def test_skip_mode_exact_duplicate(self, tmp_mesh):
        tmp_mesh.remember("The database host is localhost")
        initial_count = tmp_mesh.count()

        mid = tmp_mesh.remember(
            "The database host is localhost",
            on_conflict="skip",
        )
        # With exact text, high word overlap triggers contradiction -> skip
        assert mid == ""
        assert tmp_mesh.count() == initial_count

    def test_update_mode_exact_duplicate(self, tmp_mesh):
        mid1 = tmp_mesh.remember("The database host is localhost")
        initial_count = tmp_mesh.count()

        mid2 = tmp_mesh.remember(
            "The database host is localhost",
            on_conflict="update",
        )
        # Should have replaced the old one
        assert mid2 != ""
        assert mid2 != mid1
        # Count should stay the same (replaced, not added)
        assert tmp_mesh.count() == initial_count

    def test_default_is_keep_both(self, tmp_mesh):
        """Default on_conflict should be keep_both."""
        tmp_mesh.remember("test memory one")
        tmp_mesh.remember("test memory one")  # duplicate, default mode
        assert tmp_mesh.count() == 2

    def test_invalid_conflict_mode_falls_back(self, tmp_mesh):
        """Invalid on_conflict value should fall back to keep_both."""
        mid = tmp_mesh.remember("test memory", on_conflict="invalid_mode")
        assert mid != ""

    def test_contradiction_flagged_in_metadata(self, tmp_mesh):
        mid1 = tmp_mesh.remember("The database host is localhost")
        mid2 = tmp_mesh.remember(
            "The database host is localhost",
            on_conflict="keep_both",
        )
        assert mid2 != ""
        mem = tmp_mesh.get(mid2)
        assert mem is not None
        assert "contradicts" in mem.metadata
        assert mid1 in mem.metadata["contradicts"]

    def test_update_stores_replaced_id(self, tmp_mesh):
        mid1 = tmp_mesh.remember("The database host is localhost")
        mid2 = tmp_mesh.remember(
            "The database host is localhost",
            on_conflict="update",
        )
        assert mid2 != ""
        mem = tmp_mesh.get(mid2)
        assert mem is not None
        assert mem.metadata.get("replaced_memory_id") == mid1

    def test_enum_values(self):
        assert ConflictMode.KEEP_BOTH.value == "keep_both"
        assert ConflictMode.UPDATE.value == "update"
        assert ConflictMode.SKIP.value == "skip"

    def test_conflict_mode_from_string(self):
        assert ConflictMode("keep_both") == ConflictMode.KEEP_BOTH
        assert ConflictMode("update") == ConflictMode.UPDATE
        assert ConflictMode("skip") == ConflictMode.SKIP

    def test_skip_mode_no_contradiction(self, tmp_mesh):
        """Skip mode should still store when no contradiction exists."""
        mid = tmp_mesh.remember(
            "A completely unique memory",
            on_conflict="skip",
        )
        assert mid != ""
        assert tmp_mesh.count() == 1

    def test_update_mode_no_contradiction(self, tmp_mesh):
        """Update mode should store normally when no contradiction exists."""
        mid = tmp_mesh.remember(
            "A completely unique memory",
            on_conflict="update",
        )
        assert mid != ""
        assert tmp_mesh.count() == 1
        mem = tmp_mesh.get(mid)
        assert mem is not None
        assert "replaced_memory_id" not in mem.metadata

    def test_no_contradicts_key_when_none_found(self, tmp_mesh):
        """No contradicts key should be set when no contradictions found."""
        mid = tmp_mesh.remember("Unique memory content xyz")
        mem = tmp_mesh.get(mid)
        assert mem is not None
        assert "contradicts" not in mem.metadata
