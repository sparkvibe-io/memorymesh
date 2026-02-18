"""Tests for the memory review system."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

from memorymesh import MemoryMesh
from memorymesh.memory import GLOBAL_SCOPE, PROJECT_SCOPE, Memory
from memorymesh.review import (
    ReviewIssue,
    ReviewResult,
    _detect_low_quality,
    _detect_near_duplicate,
    _detect_scope_mismatch,
    _detect_stale,
    _detect_too_verbose,
    _detect_uncategorized,
    review_memories,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_memory(
    text: str = "Test memory",
    scope: str = PROJECT_SCOPE,
    metadata: dict | None = None,
    importance: float = 0.5,
    updated_at: datetime | None = None,
) -> Memory:
    """Create a Memory for testing."""
    mem = Memory(
        text=text,
        scope=scope,
        metadata=metadata or {},
        importance=importance,
    )
    if updated_at is not None:
        mem.updated_at = updated_at
    return mem


def _make_mesh() -> MemoryMesh:
    """Create a temporary MemoryMesh for testing."""
    tmp = tempfile.mkdtemp()
    project_db = os.path.join(tmp, "project.db")
    global_db = os.path.join(tmp, "global.db")
    return MemoryMesh(path=project_db, global_path=global_db, embedding="none")


# ---------------------------------------------------------------------------
# Scope mismatch tests
# ---------------------------------------------------------------------------


class TestScopeMismatch:
    def test_global_with_filepath(self) -> None:
        """Global memory with file path like 'src/memorymesh/core.py' is flagged."""
        mem = _make_memory(
            text="Implementation in src/memorymesh/core.py is complete",
            scope=GLOBAL_SCOPE,
        )
        issues = _detect_scope_mismatch([mem])
        assert len(issues) == 1
        assert issues[0].issue_type == "scope_mismatch"
        assert issues[0].severity == "high"
        assert issues[0].memory_id == mem.id

    def test_project_with_global_keywords(self) -> None:
        """Project memory with 'user prefers' is flagged."""
        mem = _make_memory(
            text="The user prefers dark mode across all sessions",
            scope=PROJECT_SCOPE,
        )
        issues = _detect_scope_mismatch([mem])
        assert len(issues) == 1
        assert issues[0].issue_type == "scope_mismatch"
        assert issues[0].severity == "high"

    def test_no_scope_mismatch(self) -> None:
        """Clean memory passes without issues."""
        mem_proj = _make_memory(text="Architecture uses SQLite backend", scope=PROJECT_SCOPE)
        mem_glob = _make_memory(text="User is based in India", scope=GLOBAL_SCOPE)
        issues = _detect_scope_mismatch([mem_proj, mem_glob])
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Verbosity tests
# ---------------------------------------------------------------------------


class TestVerbosity:
    def test_too_verbose_global(self) -> None:
        """Global memory > 200 chars is flagged."""
        mem = _make_memory(text="x" * 201, scope=GLOBAL_SCOPE)
        issues = _detect_too_verbose([mem])
        assert len(issues) == 1
        assert issues[0].issue_type == "too_verbose"
        assert issues[0].severity == "medium"

    def test_too_verbose_project(self) -> None:
        """Project memory > 500 chars is flagged."""
        mem = _make_memory(text="y" * 501, scope=PROJECT_SCOPE)
        issues = _detect_too_verbose([mem])
        assert len(issues) == 1
        assert issues[0].issue_type == "too_verbose"

    def test_not_too_verbose(self) -> None:
        """Memories under the limit pass."""
        mem_glob = _make_memory(text="Short global memory", scope=GLOBAL_SCOPE)
        mem_proj = _make_memory(text="Short project memory", scope=PROJECT_SCOPE)
        issues = _detect_too_verbose([mem_glob, mem_proj])
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Uncategorized tests
# ---------------------------------------------------------------------------


class TestUncategorized:
    def test_uncategorized(self) -> None:
        """Memory without category in metadata is flagged."""
        mem = _make_memory(text="Some memory", metadata={})
        issues = _detect_uncategorized([mem])
        assert len(issues) == 1
        assert issues[0].issue_type == "uncategorized"
        assert issues[0].severity == "low"
        assert issues[0].auto_fixable is True

    def test_categorized_passes(self) -> None:
        """Memory with category in metadata passes."""
        mem = _make_memory(text="Some memory", metadata={"category": "decision"})
        issues = _detect_uncategorized([mem])
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Stale tests
# ---------------------------------------------------------------------------


class TestStale:
    def test_stale_memory(self) -> None:
        """Old + low importance memory is flagged as stale."""
        old_date = datetime.now(timezone.utc) - timedelta(days=45)
        mem = _make_memory(text="Old stuff", importance=0.3, updated_at=old_date)
        issues = _detect_stale([mem])
        assert len(issues) == 1
        assert issues[0].issue_type == "stale"
        assert issues[0].severity == "low"

    def test_fresh_memory_passes(self) -> None:
        """Recent memory is not stale."""
        mem = _make_memory(text="Fresh stuff", importance=0.3)
        issues = _detect_stale([mem])
        assert len(issues) == 0

    def test_old_but_important_passes(self) -> None:
        """Old memory with high importance is not flagged."""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        mem = _make_memory(text="Important old stuff", importance=0.8, updated_at=old_date)
        issues = _detect_stale([mem])
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Near-duplicate tests
# ---------------------------------------------------------------------------


class TestNearDuplicate:
    def test_near_duplicate(self) -> None:
        """Two similar memories are detected as near-duplicates."""
        mem1 = _make_memory(text="The architecture uses SQLite for storage backend")
        mem2 = _make_memory(text="The architecture uses SQLite for storage backend layer")
        issues = _detect_near_duplicate([mem1, mem2])
        assert len(issues) == 1
        assert issues[0].issue_type == "near_duplicate"
        assert issues[0].severity == "medium"

    def test_different_memories_pass(self) -> None:
        """Dissimilar memories are not flagged."""
        mem1 = _make_memory(text="The architecture uses SQLite for storage")
        mem2 = _make_memory(text="User prefers dark mode in all applications")
        issues = _detect_near_duplicate([mem1, mem2])
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Low quality tests
# ---------------------------------------------------------------------------


class TestLowQuality:
    def test_low_quality(self) -> None:
        """Very short, vague memory is flagged as low quality."""
        mem = _make_memory(text="ok")
        issues = _detect_low_quality([mem])
        assert len(issues) == 1
        assert issues[0].issue_type == "low_quality"
        assert issues[0].severity == "low"

    def test_high_quality_passes(self) -> None:
        """Detailed memory with specifics passes quality check."""
        mem = _make_memory(
            text="Critical security vulnerability found in auth module v2.3.1, "
            "fix deployed via src/auth/handler.py. Root cause was missing JWT validation."
        )
        issues = _detect_low_quality([mem])
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Quality score tests
# ---------------------------------------------------------------------------


class TestQualityScore:
    def test_quality_score_perfect(self) -> None:
        """No issues means score of 100."""
        mesh = _make_mesh()
        result = review_memories(mesh)
        assert result.quality_score == 100
        assert result.issues == []
        mesh.close()

    def test_quality_score_degraded(self) -> None:
        """Issues reduce the quality score."""
        mesh = _make_mesh()
        # Add some problematic memories.
        mesh.remember(text="x" * 201, scope="global")  # too_verbose (medium)
        mesh.remember(text="ok", scope="project")  # low_quality (low) + uncategorized (low)
        result = review_memories(mesh)
        assert result.quality_score < 100
        assert len(result.issues) > 0
        mesh.close()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestReviewMemories:
    def test_review_specific_scope(self) -> None:
        """Only reviews the requested scope."""
        mesh = _make_mesh()
        mesh.remember(text="Project memory about architecture", scope="project")
        mesh.remember(text="Global memory about user", scope="global")

        project_result = review_memories(mesh, scope="project")
        assert project_result.scanned_scope == "project"
        # All reviewed memories should come from project store only.
        # total_reviewed should be 1 (the project memory).
        assert project_result.total_reviewed == 1

        global_result = review_memories(mesh, scope="global")
        assert global_result.scanned_scope == "global"
        assert global_result.total_reviewed == 1

        mesh.close()

    def test_review_specific_detectors(self) -> None:
        """Only runs named detectors when specified."""
        mesh = _make_mesh()
        # This memory would trigger uncategorized but NOT if we only run "stale".
        mesh.remember(text="Some decision about database design", scope="project")

        result = review_memories(mesh, detectors=["stale"])
        # No stale issues expected (memory is fresh).
        stale_issues = [i for i in result.issues if i.issue_type == "stale"]
        assert len(stale_issues) == 0
        # No uncategorized issues should appear since we didn't run that detector.
        uncat_issues = [i for i in result.issues if i.issue_type == "uncategorized"]
        assert len(uncat_issues) == 0

        mesh.close()

    def test_review_result_structure(self) -> None:
        """ReviewResult has all required fields."""
        result = ReviewResult()
        assert hasattr(result, "issues")
        assert hasattr(result, "quality_score")
        assert hasattr(result, "total_reviewed")
        assert hasattr(result, "scanned_scope")
        assert isinstance(result.issues, list)
        assert isinstance(result.quality_score, int)
        assert isinstance(result.total_reviewed, int)
        assert isinstance(result.scanned_scope, str)

    def test_review_issue_structure(self) -> None:
        """ReviewIssue has all required fields."""
        issue = ReviewIssue(
            memory_id="abc123",
            issue_type="scope_mismatch",
            severity="high",
            description="Test description",
            suggestion="Test suggestion",
            auto_fixable=False,
        )
        assert issue.memory_id == "abc123"
        assert issue.issue_type == "scope_mismatch"
        assert issue.severity == "high"
        assert issue.description == "Test description"
        assert issue.suggestion == "Test suggestion"
        assert issue.auto_fixable is False
