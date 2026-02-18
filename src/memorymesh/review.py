"""Memory review system for quality auditing.

Detects scope mismatches, verbosity, uncategorized memories, staleness,
near-duplicates, and low-quality entries.  Returns actionable issues with
severity ratings and an overall quality score.

Uses **only the Python standard library** -- no external dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .auto_importance import score_importance
from .compaction import text_similarity
from .memory import GLOBAL_SCOPE, PROJECT_SCOPE, Memory
from .store import detect_project_root

if TYPE_CHECKING:
    from .core import MemoryMesh


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ReviewIssue:
    """A single quality issue found during memory review.

    Attributes:
        memory_id: The ID of the memory with the issue.
        issue_type: Category of the issue (e.g. ``"scope_mismatch"``).
        severity: ``"high"``, ``"medium"``, or ``"low"``.
        description: Human-readable description of the problem.
        suggestion: Actionable fix recommendation.
        auto_fixable: Whether the issue can be fixed without LLM intervention.
    """

    memory_id: str
    issue_type: str
    severity: str
    description: str
    suggestion: str
    auto_fixable: bool


@dataclass
class ReviewResult:
    """Aggregate result of a memory review.

    Attributes:
        issues: All detected issues.
        quality_score: Overall health score (0--100).
        total_reviewed: Number of memories that were scanned.
        scanned_scope: Which scope was reviewed (``"project"``, ``"global"``,
            or ``"all"``).
    """

    issues: list[ReviewIssue] = field(default_factory=list)
    quality_score: int = 100
    total_reviewed: int = 0
    scanned_scope: str = "all"


# ---------------------------------------------------------------------------
# Scope-mismatch indicators
# ---------------------------------------------------------------------------

# Patterns that suggest a memory is project-specific (should NOT be global).
_PROJECT_INDICATORS: list[re.Pattern[str]] = [
    re.compile(r"\bsrc/"),
    re.compile(r"\btests?/"),
    re.compile(r"\b\w+\.py\b"),
    re.compile(r"\b\w+\.ts\b"),
    re.compile(r"\b\w+\.js\b"),
    re.compile(r"\bImplementation state\b", re.IGNORECASE),
    re.compile(r"\bv\d+\.\d+\.\d+\b.*\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\bpyproject\.toml\b"),
    re.compile(r"\bpackage\.json\b"),
    re.compile(r"\bCLAUDE\.md\b"),
    re.compile(r"\bAGENTS\.md\b"),
]

# Patterns that suggest a memory is global (should NOT be project-scoped).
_GLOBAL_INDICATORS: list[re.Pattern[str]] = [
    re.compile(r"\buser prefers?\b", re.IGNORECASE),
    re.compile(r"\bacross all projects?\b", re.IGNORECASE),
    re.compile(r"\bglobal preference\b", re.IGNORECASE),
    re.compile(r"\buser['']?s? favourite?\b", re.IGNORECASE),
    re.compile(r"\balways use\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def _detect_scope_mismatch(
    memories: list[Memory],
    project_name: str | None = None,
) -> list[ReviewIssue]:
    """Detect memories stored in the wrong scope.

    Global memories containing project-specific indicators (file paths,
    version+date combos, product/project names) and project memories
    containing global-only keywords (``"user prefers"``, ``"across all
    projects"``).

    Global scope should contain only general, 50,000-foot knowledge:
    personality, technology preferences, documentation standards,
    approaches, guardrails.  Product names and product-specific content
    belong in project scope.

    Args:
        memories: Memories to scan.
        project_name: The project/product name to check for in global
            memories.  If ``None``, auto-detected from the project root
            directory name.

    Returns:
        A list of high-severity scope mismatch issues.
    """
    issues: list[ReviewIssue] = []

    # Build a dynamic pattern for the project/product name.
    extra_project_patterns: list[re.Pattern[str]] = []
    if project_name is None:
        root = detect_project_root()
        if root:
            import os

            project_name = os.path.basename(root)
    if project_name and len(project_name) >= 3:
        # Match the name case-insensitively, as a whole word.
        extra_project_patterns.append(re.compile(rf"\b{re.escape(project_name)}\b", re.IGNORECASE))

    all_project_patterns = _PROJECT_INDICATORS + extra_project_patterns

    for mem in memories:
        if mem.scope == GLOBAL_SCOPE:
            for pattern in all_project_patterns:
                if pattern.search(mem.text):
                    issues.append(
                        ReviewIssue(
                            memory_id=mem.id,
                            issue_type="scope_mismatch",
                            severity="high",
                            description=(
                                f"Global memory contains project-specific content "
                                f"(matched: {pattern.pattern!r})."
                            ),
                            suggestion=(
                                "Move to project scope with "
                                f"update_memory('{mem.id}', scope='project')."
                            ),
                            auto_fixable=False,
                        )
                    )
                    break  # one issue per memory

        elif mem.scope == PROJECT_SCOPE:
            for pattern in _GLOBAL_INDICATORS:
                if pattern.search(mem.text):
                    issues.append(
                        ReviewIssue(
                            memory_id=mem.id,
                            issue_type="scope_mismatch",
                            severity="high",
                            description=(
                                f"Project memory contains global-scope content "
                                f"(matched: {pattern.pattern!r})."
                            ),
                            suggestion=(
                                "Move to global scope with "
                                f"update_memory('{mem.id}', scope='global')."
                            ),
                            auto_fixable=False,
                        )
                    )
                    break

    return issues


def _detect_too_verbose(memories: list[Memory]) -> list[ReviewIssue]:
    """Detect memories that are too long for their scope.

    Global memories should be concise (> 200 chars flagged).
    Project memories have a higher limit (> 500 chars flagged).

    Args:
        memories: Memories to scan.

    Returns:
        A list of medium-severity verbosity issues.
    """
    issues: list[ReviewIssue] = []

    for mem in memories:
        limit = 200 if mem.scope == GLOBAL_SCOPE else 500
        if len(mem.text) > limit:
            issues.append(
                ReviewIssue(
                    memory_id=mem.id,
                    issue_type="too_verbose",
                    severity="medium",
                    description=(
                        f"Memory text is {len(mem.text)} chars (limit for {mem.scope}: {limit})."
                    ),
                    suggestion="Distill to a shorter, more focused statement.",
                    auto_fixable=False,
                )
            )

    return issues


def _detect_uncategorized(memories: list[Memory]) -> list[ReviewIssue]:
    """Detect memories without a category in metadata.

    Args:
        memories: Memories to scan.

    Returns:
        A list of low-severity uncategorized issues.
    """
    issues: list[ReviewIssue] = []

    for mem in memories:
        if "category" not in mem.metadata:
            issues.append(
                ReviewIssue(
                    memory_id=mem.id,
                    issue_type="uncategorized",
                    severity="low",
                    description="Memory has no category in metadata.",
                    suggestion="Add a category (e.g. decision, pattern, preference).",
                    auto_fixable=True,
                )
            )

    return issues


def _detect_stale(memories: list[Memory]) -> list[ReviewIssue]:
    """Detect stale memories (not accessed in 30+ days, low importance).

    Only flags memories with importance < 0.5 AND not updated in 30+ days.

    Args:
        memories: Memories to scan.

    Returns:
        A list of low-severity staleness issues.
    """
    issues: list[ReviewIssue] = []
    now = datetime.now(timezone.utc)

    for mem in memories:
        age = now - mem.updated_at
        if age.days >= 30 and mem.importance < 0.5:
            issues.append(
                ReviewIssue(
                    memory_id=mem.id,
                    issue_type="stale",
                    severity="low",
                    description=(
                        f"Not accessed in {age.days} days and importance is {mem.importance:.2f}."
                    ),
                    suggestion="Consider deleting if no longer relevant.",
                    auto_fixable=False,
                )
            )

    return issues


def _detect_near_duplicate(memories: list[Memory]) -> list[ReviewIssue]:
    """Detect near-duplicate memories using text similarity.

    Uses :func:`compaction.text_similarity` with a 0.7 threshold.
    O(n^2) comparison capped at 500 memories per scope to stay fast.

    Args:
        memories: Memories to scan.

    Returns:
        A list of medium-severity duplicate issues.
    """
    issues: list[ReviewIssue] = []
    seen: set[str] = set()

    # Group by scope so we only compare within the same scope.
    by_scope: dict[str, list[Memory]] = {}
    for mem in memories:
        by_scope.setdefault(mem.scope, []).append(mem)

    for scope_mems in by_scope.values():
        # Cap to avoid excessive computation.
        capped = scope_mems[:500]
        for i in range(len(capped)):
            if capped[i].id in seen:
                continue
            for j in range(i + 1, len(capped)):
                if capped[j].id in seen:
                    continue
                sim = text_similarity(capped[i].text, capped[j].text)
                if sim >= 0.7:
                    issues.append(
                        ReviewIssue(
                            memory_id=capped[j].id,
                            issue_type="near_duplicate",
                            severity="medium",
                            description=(
                                f"Similar to memory {capped[i].id[:8]}... (similarity: {sim:.2f})."
                            ),
                            suggestion=(
                                f"Consider merging with {capped[i].id[:8]}... "
                                f"or deleting this duplicate."
                            ),
                            auto_fixable=False,
                        )
                    )
                    seen.add(capped[j].id)

    return issues


def _detect_low_quality(memories: list[Memory]) -> list[ReviewIssue]:
    """Detect low-quality memories using importance heuristics.

    Uses :func:`auto_importance.score_importance` and flags memories
    scoring below 0.4.

    Args:
        memories: Memories to scan.

    Returns:
        A list of low-severity quality issues.
    """
    issues: list[ReviewIssue] = []

    for mem in memories:
        score = score_importance(mem.text, mem.metadata)
        if score < 0.4:
            issues.append(
                ReviewIssue(
                    memory_id=mem.id,
                    issue_type="low_quality",
                    severity="low",
                    description=(
                        f"Low quality score ({score:.2f}). Text may be too vague or short."
                    ),
                    suggestion="Rewrite with more specific, actionable content.",
                    auto_fixable=False,
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Detector registry
# ---------------------------------------------------------------------------

_ALL_DETECTORS: dict[str, Any] = {
    "scope_mismatch": _detect_scope_mismatch,
    "too_verbose": _detect_too_verbose,
    "uncategorized": _detect_uncategorized,
    "stale": _detect_stale,
    "near_duplicate": _detect_near_duplicate,
    "low_quality": _detect_low_quality,
}


# ---------------------------------------------------------------------------
# Main review function
# ---------------------------------------------------------------------------


def review_memories(
    mesh: MemoryMesh,
    scope: str | None = None,
    detectors: list[str] | None = None,
    project_name: str | None = None,
) -> ReviewResult:
    """Audit memories for quality issues.

    Loads all memories for the given scope, runs each detector, and
    computes an overall quality score.

    Args:
        mesh: The :class:`MemoryMesh` instance to review.
        scope: ``"project"``, ``"global"``, or ``None`` (default) to
            review all memories.
        detectors: Subset of detector names to run, or ``None`` for all.
            Valid names: ``"scope_mismatch"``, ``"too_verbose"``,
            ``"uncategorized"``, ``"stale"``, ``"near_duplicate"``,
            ``"low_quality"``.
        project_name: Optional project/product name to check for in
            global memories.  If ``None``, auto-detected from the project
            root directory name.  Global memories mentioning a product
            name are flagged as scope mismatches.

    Returns:
        A :class:`ReviewResult` with all detected issues and a quality
        score from 0 to 100.
    """
    # Load memories.
    memories = mesh.list(limit=100_000, scope=scope)

    # Determine scope label for the result.
    scanned_scope = "all" if scope is None else scope

    result = ReviewResult(
        total_reviewed=len(memories),
        scanned_scope=scanned_scope,
    )

    if not memories:
        return result

    # Select detectors.
    if detectors is not None:
        active = {name: fn for name, fn in _ALL_DETECTORS.items() if name in detectors}
    else:
        active = _ALL_DETECTORS

    # Run each detector.  scope_mismatch gets the extra project_name arg.
    for name, fn in active.items():
        if name == "scope_mismatch":
            result.issues.extend(fn(memories, project_name=project_name))
        else:
            result.issues.extend(fn(memories))

    # Compute quality score.
    high_count = sum(1 for i in result.issues if i.severity == "high")
    medium_count = sum(1 for i in result.issues if i.severity == "medium")
    low_count = sum(1 for i in result.issues if i.severity == "low")

    score = 100 - (high_count * 10 + medium_count * 5 + low_count * 2)
    result.quality_score = max(0, min(100, score))

    return result
