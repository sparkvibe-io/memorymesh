"""Tests for the memory compaction module."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from memorymesh import CompactionResult, MemoryMesh
from memorymesh.compaction import (
    find_duplicates,
    find_near_duplicates,
    jaccard_similarity,
    merge_memories,
    text_similarity,
)
from memorymesh.memory import Memory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_mesh(tmp_path):
    """Create a MemoryMesh with project + global stores in a temp dir."""
    project_db = os.path.join(str(tmp_path), "project", "memories.db")
    global_db = os.path.join(str(tmp_path), "global", "global.db")
    mesh = MemoryMesh(path=project_db, global_path=global_db, embedding="none")
    yield mesh
    mesh.close()


# ---------------------------------------------------------------------------
# jaccard_similarity
# ---------------------------------------------------------------------------


class TestJaccardSimilarity:
    def test_identical_texts(self):
        assert jaccard_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert jaccard_similarity("hello world", "foo bar baz") == 0.0

    def test_partial_overlap(self):
        sim = jaccard_similarity("the cat sat on the mat", "the dog sat on the rug")
        # Overlap: {the, sat, on} = 3, Union: {the, cat, sat, on, mat, dog, rug} = 7
        assert abs(sim - 3 / 7) < 0.01

    def test_empty_texts(self):
        assert jaccard_similarity("", "") == 0.0

    def test_case_insensitive(self):
        assert jaccard_similarity("Hello World", "hello world") == 1.0


# ---------------------------------------------------------------------------
# text_similarity
# ---------------------------------------------------------------------------


class TestTextSimilarity:
    def test_substring_containment(self):
        # One text is contained in the other.
        assert text_similarity("hello", "hello world") == 1.0
        assert text_similarity("hello world", "hello") == 1.0

    def test_exact_match(self):
        assert text_similarity("foo bar", "foo bar") == 1.0

    def test_different_texts(self):
        sim = text_similarity("apples and oranges", "cats and dogs")
        # Only "and" overlaps.
        assert sim < 0.5

    def test_whitespace_stripped_containment(self):
        assert text_similarity("  hello  ", "hello") == 1.0


# ---------------------------------------------------------------------------
# find_duplicates
# ---------------------------------------------------------------------------


class TestFindDuplicates:
    def test_exact_duplicates(self):
        m1 = Memory(text="The user prefers dark mode.", importance=0.8)
        m2 = Memory(text="The user prefers dark mode.", importance=0.5)
        pairs = find_duplicates([m1, m2])
        assert len(pairs) == 1
        primary, secondary = pairs[0]
        # Higher importance wins.
        assert primary.id == m1.id
        assert secondary.id == m2.id

    def test_near_duplicate_text(self):
        m1 = Memory(text="The user prefers dark mode")
        m2 = Memory(text="The user prefers dark mode in the editor")
        # m1 is a substring of m2 → similarity = 1.0
        pairs = find_duplicates([m1, m2], threshold=0.85)
        assert len(pairs) == 1

    def test_no_duplicates(self):
        m1 = Memory(text="Python is a programming language.")
        m2 = Memory(text="The weather is sunny today.")
        pairs = find_duplicates([m1, m2], threshold=0.85)
        assert len(pairs) == 0

    def test_threshold_tuning(self):
        m1 = Memory(text="Python programming language features.")
        m2 = Memory(text="Python programming language benefits.")
        # Overlap: {python, programming, language} = 3
        # Union: {python, programming, language, features., benefits.} = 5
        # Jaccard = 3/5 = 0.6
        pairs_high = find_duplicates([m1, m2], threshold=0.85)
        assert len(pairs_high) == 0
        pairs_low = find_duplicates([m1, m2], threshold=0.5)
        assert len(pairs_low) == 1

    def test_multiple_pairs(self):
        m1 = Memory(text="dark mode preference")
        m2 = Memory(text="dark mode preference")
        m3 = Memory(text="light mode preference")
        m4 = Memory(text="light mode preference")
        pairs = find_duplicates([m1, m2, m3, m4])
        assert len(pairs) == 2

    def test_secondary_not_reused(self):
        """Once a memory is marked as secondary, it shouldn't be paired again."""
        m1 = Memory(text="hello world foo bar")
        m2 = Memory(text="hello world foo bar")
        m3 = Memory(text="hello world foo bar")
        pairs = find_duplicates([m1, m2, m3])
        # m2 or m3 becomes secondary of m1. The remaining one may also pair,
        # but the one already secondary should not pair again.
        secondary_ids = [s.id for _, s in pairs]
        assert len(secondary_ids) == len(set(secondary_ids))


# ---------------------------------------------------------------------------
# find_near_duplicates (embedding-based)
# ---------------------------------------------------------------------------


class TestFindNearDuplicates:
    def test_with_identical_embeddings(self):
        m1 = Memory(text="A", embedding=[1.0, 0.0, 0.0])
        m2 = Memory(text="B", embedding=[1.0, 0.0, 0.0])
        pairs = find_near_duplicates([m1, m2], threshold=0.9)
        assert len(pairs) == 1

    def test_with_different_embeddings(self):
        m1 = Memory(text="A", embedding=[1.0, 0.0, 0.0])
        m2 = Memory(text="B", embedding=[0.0, 1.0, 0.0])
        pairs = find_near_duplicates([m1, m2], threshold=0.9)
        assert len(pairs) == 0

    def test_skips_memories_without_embeddings(self):
        m1 = Memory(text="A", embedding=[1.0, 0.0])
        m2 = Memory(text="B", embedding=None)
        pairs = find_near_duplicates([m1, m2], threshold=0.9)
        assert len(pairs) == 0

    def test_with_embeddings_fn(self):
        m1 = Memory(text="A", embedding=None)
        m2 = Memory(text="B", embedding=None)

        def fake_embed(text):
            return [1.0, 0.0]

        pairs = find_near_duplicates([m1, m2], embeddings_fn=fake_embed, threshold=0.9)
        assert len(pairs) == 1

    def test_embeddings_fn_failure_skips(self):
        m1 = Memory(text="A", embedding=None)
        m2 = Memory(text="B", embedding=[1.0, 0.0])

        def bad_embed(text):
            raise RuntimeError("embedding failed")

        # Should not crash; m1 is skipped.
        pairs = find_near_duplicates([m1, m2], embeddings_fn=bad_embed, threshold=0.9)
        assert len(pairs) == 0


# ---------------------------------------------------------------------------
# merge_memories
# ---------------------------------------------------------------------------


class TestMergeMemories:
    def test_keeps_primary_id(self):
        m1 = Memory(text="Primary text.", importance=0.8)
        m2 = Memory(text="Secondary text.", importance=0.5)
        merged = merge_memories(m1, m2)
        assert merged.id == m1.id

    def test_keeps_higher_importance(self):
        m1 = Memory(text="A", importance=0.3)
        m2 = Memory(text="B", importance=0.9)
        merged = merge_memories(m1, m2)
        assert merged.importance == 0.9

    def test_sums_access_counts(self):
        m1 = Memory(text="A", access_count=5)
        m2 = Memory(text="B", access_count=3)
        merged = merge_memories(m1, m2)
        assert merged.access_count == 8

    def test_keeps_older_created_at(self):
        old = datetime(2025, 1, 1, tzinfo=timezone.utc)
        new = datetime(2026, 1, 1, tzinfo=timezone.utc)
        m1 = Memory(text="A", created_at=new)
        m2 = Memory(text="B", created_at=old)
        merged = merge_memories(m1, m2)
        assert merged.created_at == old

    def test_keeps_newer_updated_at(self):
        old = datetime(2025, 1, 1, tzinfo=timezone.utc)
        new = datetime(2026, 1, 1, tzinfo=timezone.utc)
        m1 = Memory(text="A", updated_at=old)
        m2 = Memory(text="B", updated_at=new)
        merged = merge_memories(m1, m2)
        assert merged.updated_at == new

    def test_combines_metadata(self):
        m1 = Memory(text="A", metadata={"key1": "val1", "shared": "primary"})
        m2 = Memory(text="B", metadata={"key2": "val2", "shared": "secondary"})
        merged = merge_memories(m1, m2)
        assert merged.metadata["key1"] == "val1"
        assert merged.metadata["key2"] == "val2"
        # Primary wins on conflict.
        assert merged.metadata["shared"] == "primary"

    def test_appends_different_text(self):
        m1 = Memory(text="Python is great for scripting.")
        m2 = Memory(text="Rust is great for performance.")
        merged = merge_memories(m1, m2)
        assert "Python is great" in merged.text
        assert "Rust is great" in merged.text
        assert "---" in merged.text

    def test_no_append_for_similar_text(self):
        m1 = Memory(text="The user prefers dark mode.")
        m2 = Memory(text="the user prefers dark mode.")
        merged = merge_memories(m1, m2)
        # Texts are very similar, so secondary should NOT be appended.
        assert "---" not in merged.text
        assert merged.text == "The user prefers dark mode."

    def test_keeps_lower_decay_rate(self):
        m1 = Memory(text="A", decay_rate=0.05)
        m2 = Memory(text="B", decay_rate=0.01)
        merged = merge_memories(m1, m2)
        assert merged.decay_rate == 0.01

    def test_keeps_primary_embedding(self):
        emb = [1.0, 2.0, 3.0]
        m1 = Memory(text="A", embedding=emb)
        m2 = Memory(text="B", embedding=[4.0, 5.0, 6.0])
        merged = merge_memories(m1, m2)
        assert merged.embedding == emb


# ---------------------------------------------------------------------------
# CompactionResult
# ---------------------------------------------------------------------------


class TestCompactionResult:
    def test_default_values(self):
        r = CompactionResult()
        assert r.merged_count == 0
        assert r.deleted_ids == []
        assert r.kept_ids == []
        assert r.details == []


# ---------------------------------------------------------------------------
# compact() end-to-end
# ---------------------------------------------------------------------------


class TestCompact:
    def test_compact_merges_duplicates(self, tmp_mesh):
        tmp_mesh.remember("The user prefers dark mode.", scope="project", importance=0.8)
        tmp_mesh.remember("The user prefers dark mode.", scope="project", importance=0.5)
        assert tmp_mesh.count(scope="project") == 2

        result = tmp_mesh.compact(scope="project", similarity_threshold=0.85)
        assert result.merged_count == 1
        assert len(result.deleted_ids) == 1
        assert len(result.kept_ids) == 1
        assert tmp_mesh.count(scope="project") == 1

        # The surviving memory should have the higher importance.
        remaining = tmp_mesh.list(scope="project")
        assert len(remaining) == 1
        assert remaining[0].importance == 0.8

    def test_compact_dry_run(self, tmp_mesh):
        tmp_mesh.remember("duplicate text here", scope="project")
        tmp_mesh.remember("duplicate text here", scope="project")
        assert tmp_mesh.count(scope="project") == 2

        result = tmp_mesh.compact(scope="project", dry_run=True)
        assert result.merged_count == 1
        # Dry run should NOT delete anything.
        assert tmp_mesh.count(scope="project") == 2

    def test_compact_empty_store(self, tmp_mesh):
        result = tmp_mesh.compact(scope="project")
        assert result.merged_count == 0
        assert result.deleted_ids == []

    def test_compact_single_memory(self, tmp_mesh):
        tmp_mesh.remember("only one memory", scope="project")
        result = tmp_mesh.compact(scope="project")
        assert result.merged_count == 0

    def test_compact_no_duplicates(self, tmp_mesh):
        tmp_mesh.remember("Python is a language.", scope="project")
        tmp_mesh.remember("The weather is nice today.", scope="project")
        result = tmp_mesh.compact(scope="project")
        assert result.merged_count == 0
        assert tmp_mesh.count(scope="project") == 2

    def test_compact_global_scope(self, tmp_mesh):
        tmp_mesh.remember("global duplicate", scope="global")
        tmp_mesh.remember("global duplicate", scope="global")
        assert tmp_mesh.count(scope="global") == 2

        result = tmp_mesh.compact(scope="global")
        assert result.merged_count == 1
        assert tmp_mesh.count(scope="global") == 1

    def test_compact_threshold_controls_sensitivity(self, tmp_mesh):
        tmp_mesh.remember("Python programming language features.", scope="project")
        tmp_mesh.remember("Python programming language benefits.", scope="project")

        # High threshold -- not similar enough.
        result_high = tmp_mesh.compact(scope="project", similarity_threshold=0.85, dry_run=True)
        assert result_high.merged_count == 0

        # Low threshold -- similar enough.
        result_low = tmp_mesh.compact(scope="project", similarity_threshold=0.5, dry_run=True)
        assert result_low.merged_count == 1

    def test_compact_result_details(self, tmp_mesh):
        tmp_mesh.remember("same text for detail test", scope="project")
        tmp_mesh.remember("same text for detail test", scope="project")

        result = tmp_mesh.compact(scope="project", dry_run=True)
        assert len(result.details) == 1
        detail = result.details[0]
        assert "primary_id" in detail
        assert "secondary_id" in detail
        assert "similarity" in detail
        assert "merged_text_preview" in detail
        assert detail["similarity"] == 1.0

    def test_compact_preserves_merged_metadata(self, tmp_mesh):
        tmp_mesh.remember(
            "same memory",
            scope="project",
            importance=0.9,
            metadata={"source": "user"},
        )
        tmp_mesh.remember(
            "same memory",
            scope="project",
            importance=0.5,
            metadata={"topic": "preferences"},
        )

        result = tmp_mesh.compact(scope="project")
        assert result.merged_count == 1

        remaining = tmp_mesh.list(scope="project")
        assert len(remaining) == 1
        mem = remaining[0]
        assert mem.importance == 0.9
        assert mem.metadata.get("source") == "user"
        assert mem.metadata.get("topic") == "preferences"

    def test_compact_invalid_scope(self, tmp_mesh):
        with pytest.raises(ValueError, match="Invalid scope"):
            tmp_mesh.compact(scope="invalid")


# ---------------------------------------------------------------------------
# CLI compact subcommand
# ---------------------------------------------------------------------------


class TestCompactCLI:
    def test_compact_cli_no_duplicates(self, tmp_mesh, capsys):
        from memorymesh.cli import main

        tmp_mesh.remember("unique memory one", scope="project")
        tmp_mesh.remember("completely different memory two", scope="project")

        project_db = tmp_mesh.project_path
        global_db = tmp_mesh.global_path
        exit_code = main(["--project-path", project_db, "--global-path", global_db, "compact"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No duplicates found" in captured.out

    def test_compact_cli_with_duplicates(self, tmp_mesh, capsys):
        from memorymesh.cli import main

        tmp_mesh.remember("duplicate memory for CLI", scope="project")
        tmp_mesh.remember("duplicate memory for CLI", scope="project")

        project_db = tmp_mesh.project_path
        global_db = tmp_mesh.global_path
        exit_code = main(["--project-path", project_db, "--global-path", global_db, "compact"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Merged 1 pair" in captured.out
        assert "Deleted 1 redundant" in captured.out

    def test_compact_cli_dry_run(self, tmp_mesh, capsys):
        from memorymesh.cli import main

        tmp_mesh.remember("dry run test memory", scope="project")
        tmp_mesh.remember("dry run test memory", scope="project")

        project_db = tmp_mesh.project_path
        global_db = tmp_mesh.global_path
        exit_code = main(
            [
                "--project-path",
                project_db,
                "--global-path",
                global_db,
                "compact",
                "--dry-run",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Would merge 1 pair" in captured.out
        assert "Dry run" in captured.out
        # Nothing actually deleted.
        assert tmp_mesh.count(scope="project") == 2
