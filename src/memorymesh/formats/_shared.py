"""Shared utilities for format adapters.

Provides text normalisation, duplicate detection, importance grouping,
and HTML comment parsing used across all adapters.

Uses **only the Python standard library** -- no external dependencies.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..memory import Memory

# ---------------------------------------------------------------------------
# HTML comment importance pattern
# ---------------------------------------------------------------------------

_HTML_COMMENT_IMPORTANCE = re.compile(r"<!--\s*memorymesh:importance=([\d.]+)\s*-->")
"""Regex to extract importance from HTML comment metadata."""

_IMPORTANCE_PREFIX = re.compile(r"^\[importance:\s*([\d.]+)\]\s*(.*)$")
"""Regex to extract ``[importance: X.XX]`` prefix from a bullet point."""


# ---------------------------------------------------------------------------
# Text normalisation and deduplication
# ---------------------------------------------------------------------------


def normalise(text: str) -> str:
    """Normalise text for duplicate comparison.

    Lowercases, strips, and collapses whitespace.

    Args:
        text: Raw text.

    Returns:
        Normalised string.
    """
    return " ".join(text.lower().split())


def is_duplicate(text: str, candidates: list[Memory]) -> bool:
    """Check whether *text* already exists among the candidate memories.

    Uses exact text comparison (case-insensitive, whitespace-normalised)
    to determine duplicates.

    Args:
        text: The text to check.
        candidates: Memories returned by recall for this text.

    Returns:
        ``True`` if a duplicate is found.
    """
    normalised = normalise(text)
    return any(normalise(mem.text) == normalised for mem in candidates)


# ---------------------------------------------------------------------------
# Importance grouping
# ---------------------------------------------------------------------------

HIGH_IMPORTANCE_THRESHOLD = 0.8
"""Importance threshold for the 'Key Decisions' tier."""

MEDIUM_IMPORTANCE_THRESHOLD = 0.5
"""Importance threshold for the 'Patterns & Conventions' tier."""

DEFAULT_TIER_LABELS = {
    "high": "Key Decisions",
    "medium": "Patterns & Conventions",
    "low": "Recent Learnings",
}
"""Default section headers for importance-tiered grouping."""

CATEGORY_SECTION_LABELS: dict[str, str] = {
    "personality": "User Profile",
    "preference": "User Profile",
    "guardrail": "Guardrails",
    "mistake": "Common Mistakes",
    "question": "Common Questions",
    "decision": "Decisions",
    "pattern": "Patterns & Conventions",
    "context": "Project Context",
    "session_summary": "Last Session",
}
"""Maps category names to human-readable section headings for sync output."""


def group_by_topic_or_tier(
    memories: list[Memory],
) -> dict[str, list[Memory]]:
    """Group memories into named sections.

    If a memory has ``metadata["topic"]``, it is grouped under that topic
    name.  Otherwise it is grouped by importance tier.

    Args:
        memories: Pre-sorted list of memories (highest importance first).

    Returns:
        An ordered dictionary mapping section names to lists of memories.
    """
    sections: dict[str, list[Memory]] = {}

    has_topics = any(m.metadata.get("topic") for m in memories)

    if has_topics:
        for mem in memories:
            topic = mem.metadata.get("topic")
            section_name = topic.strip().title() if topic and isinstance(topic, str) else "Other"
            sections.setdefault(section_name, []).append(mem)
    else:
        for mem in memories:
            if mem.importance >= HIGH_IMPORTANCE_THRESHOLD:
                tier = DEFAULT_TIER_LABELS["high"]
            elif mem.importance >= MEDIUM_IMPORTANCE_THRESHOLD:
                tier = DEFAULT_TIER_LABELS["medium"]
            else:
                tier = DEFAULT_TIER_LABELS["low"]
            sections.setdefault(tier, []).append(mem)

    return sections


def group_by_category(
    memories: list[Memory],
) -> dict[str, list[Memory]]:
    """Group memories by their ``metadata["category"]`` value.

    Memories without a category are grouped using
    :func:`group_by_topic_or_tier` and merged into the result.

    Args:
        memories: Pre-sorted list of memories (highest importance first).

    Returns:
        An ordered dictionary mapping section names to lists of memories.
    """
    categorized: dict[str, list[Memory]] = {}
    uncategorized: list[Memory] = []

    for mem in memories:
        cat = mem.metadata.get("category")
        if isinstance(cat, str) and cat in CATEGORY_SECTION_LABELS:
            label = CATEGORY_SECTION_LABELS[cat]
            categorized.setdefault(label, []).append(mem)
        else:
            uncategorized.append(mem)

    # Merge uncategorized memories using legacy grouping.
    if uncategorized:
        legacy_groups = group_by_topic_or_tier(uncategorized)
        for section_name, mems in legacy_groups.items():
            categorized.setdefault(section_name, []).extend(mems)

    return categorized


# ---------------------------------------------------------------------------
# HTML comment helpers
# ---------------------------------------------------------------------------


def importance_to_html_comment(importance: float) -> str:
    """Encode importance as an HTML comment for round-trip fidelity.

    Args:
        importance: Score in ``[0, 1]``.

    Returns:
        An HTML comment string, e.g. ``<!-- memorymesh:importance=0.90 -->``.
    """
    return f"<!-- memorymesh:importance={importance:.2f} -->"


def parse_importance_from_html_comment(line: str) -> tuple[str, float]:
    """Extract importance from an HTML comment appended to a line.

    If no comment is found, returns the line unchanged with default
    importance 0.5.

    Args:
        line: A markdown line potentially containing an HTML comment.

    Returns:
        A ``(clean_line, importance)`` tuple.
    """
    match = _HTML_COMMENT_IMPORTANCE.search(line)
    if match:
        try:
            importance = max(0.0, min(1.0, float(match.group(1))))
        except ValueError:
            importance = 0.5
        clean = line[: match.start()].rstrip() + line[match.end() :]
        clean = clean.strip()
        return clean, importance
    return line.strip(), 0.5


def parse_importance_prefix(content: str) -> tuple[str, float]:
    """Extract importance from ``[importance: X.XX]`` prefix.

    Args:
        content: Bullet content (after removing the ``- `` prefix).

    Returns:
        A ``(clean_text, importance)`` tuple.
    """
    match = _IMPORTANCE_PREFIX.match(content)
    if match:
        try:
            importance = max(0.0, min(1.0, float(match.group(1))))
        except ValueError:
            importance = 0.5
        return match.group(2).strip(), importance
    return content, 0.5


# ---------------------------------------------------------------------------
# Section-based file manipulation
# ---------------------------------------------------------------------------

_SECTION_HEADING = "## MemoryMesh Synced Memories"


def inject_section(existing_content: str, section_content: str) -> str:
    """Replace or insert the MemoryMesh section in an existing file.

    Preserves all content outside the ``## MemoryMesh Synced Memories``
    section.  If the section already exists, it is replaced.  Otherwise
    it is appended.

    Args:
        existing_content: The current file content.
        section_content: The new section content (including the heading).

    Returns:
        The updated file content.
    """
    heading = _SECTION_HEADING
    if heading in existing_content:
        # Find the section boundaries.
        start = existing_content.index(heading)

        # Find the end: next heading of same or higher level, or EOF.
        rest = existing_content[start + len(heading) :]
        # Look for the next ## heading (same level or higher).
        next_heading = re.search(r"\n(?=## |\n# )", rest)
        end = start + len(heading) + next_heading.start() if next_heading else len(existing_content)

        # Reconstruct: before + new section + after
        before = existing_content[:start].rstrip()
        after = existing_content[end:].lstrip("\n")

        parts = [before]
        if before:
            parts.append("")
        parts.append(section_content.rstrip())
        if after:
            parts.append("")
            parts.append(after)
        else:
            parts.append("")

        return "\n".join(parts)
    else:
        # Append the section.
        if existing_content and not existing_content.endswith("\n"):
            existing_content += "\n"
        if existing_content and not existing_content.endswith("\n\n"):
            existing_content += "\n"
        return existing_content + section_content.rstrip() + "\n"
