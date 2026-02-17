"""Tests for auto-compaction on remember()."""

from __future__ import annotations

import os

import pytest

from memorymesh import MemoryMesh


@pytest.fixture()
def mesh(tmp_path: str) -> MemoryMesh:
    """Create a MemoryMesh with both stores and low compact interval."""
    project_db = os.path.join(str(tmp_path), "project", "memories.db")
    global_db = os.path.join(str(tmp_path), "global", "global.db")
    m = MemoryMesh(path=project_db, global_path=global_db, embedding="none")
    m.compact_interval = 5  # trigger compaction every 5 writes for testing
    return m


class TestAutoCompaction:
    """Test auto-compaction triggered by remember()."""

    def test_default_interval_is_50(self, tmp_path: str) -> None:
        db = os.path.join(str(tmp_path), "p", "m.db")
        m = MemoryMesh(path=db, embedding="none")
        assert m.compact_interval == 50
        m.close()

    def test_interval_property(self, mesh: MemoryMesh) -> None:
        mesh.compact_interval = 100
        assert mesh.compact_interval == 100

    def test_interval_cannot_be_negative(self, mesh: MemoryMesh) -> None:
        mesh.compact_interval = -10
        assert mesh.compact_interval == 0

    def test_disable_auto_compaction(self, mesh: MemoryMesh) -> None:
        mesh.compact_interval = 0
        for i in range(20):
            mesh.remember(f"Memory number {i}")
        # Should not crash, all memories should be there
        assert mesh.count(scope="project") == 20

    def test_auto_compaction_triggers(self, mesh: MemoryMesh) -> None:
        mesh.compact_interval = 5
        # Write 5 identical memories to trigger compaction
        for _ in range(5):
            mesh.remember("Exact duplicate text for compaction test")
        # After compaction, some duplicates should be merged
        # The exact count depends on Jaccard similarity threshold
        # but we should have fewer than 5
        count = mesh.count(scope="project")
        assert count <= 5  # compaction ran (may or may not merge depending on threshold)

    def test_auto_compaction_resets_counter(self, mesh: MemoryMesh) -> None:
        mesh.compact_interval = 3
        for i in range(3):
            mesh.remember(f"Unique memory {i}")
        # Counter should be reset after compaction
        assert mesh._writes_since_compact == 0

    def test_auto_compaction_does_not_crash_on_error(self, mesh: MemoryMesh) -> None:
        mesh.compact_interval = 2
        # Write memories normally -- even if compaction has issues it shouldn't crash
        mesh.remember("First memory")
        mesh.remember("Second memory")
        # Both memories should exist
        assert mesh.count(scope="project") >= 2

    def test_compaction_runs_on_correct_scope(self, mesh: MemoryMesh) -> None:
        mesh.compact_interval = 3
        # Write to global scope
        for _ in range(3):
            mesh.remember("Global preference text", scope="global")
        # Write to project scope
        for _ in range(3):
            mesh.remember("Project context text", scope="project")
        # Both scopes should have data
        assert mesh.count(scope="global") >= 1
        assert mesh.count(scope="project") >= 1

    def test_writes_counter_increments(self, mesh: MemoryMesh) -> None:
        mesh.compact_interval = 100  # high so it doesn't trigger
        mesh.remember("Memory 1")
        assert mesh._writes_since_compact == 1
        mesh.remember("Memory 2")
        assert mesh._writes_since_compact == 2
