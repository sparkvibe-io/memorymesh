"""Memory analytics and reporting for MemoryMesh.

Generates formatted text reports summarising the state of stored memories,
including scope breakdown, importance distribution, access patterns, stale
memory detection, and topic analysis.

Uses **only the Python standard library** (datetime, collections, math).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from .memory import GLOBAL_SCOPE, PROJECT_SCOPE, Memory

if TYPE_CHECKING:
    from .core import MemoryMesh

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BAR_CHAR = "\u2588"  # █
_MAX_BAR_WIDTH = 30
_STALE_DAYS = 7
_TOP_ACCESSED_LIMIT = 5
_TEXT_TRUNCATE_WIDTH = 50
_SECTION_WIDTH = 40

# Importance buckets: (label, lower_bound_inclusive, upper_bound_exclusive)
# The "critical" bucket is [0.9, 1.0] (inclusive on both ends), handled
# specially via the upper bound of 1.01.
_IMPORTANCE_BUCKETS: list[tuple[str, float, float]] = [
    ("Critical (0.9-1.0)", 0.9, 1.01),
    ("High (0.7-0.9)", 0.7, 0.9),
    ("Medium (0.5-0.7)", 0.5, 0.7),
    ("Low (0.0-0.5)", 0.0, 0.5),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, width: int) -> str:
    """Truncate text to *width* characters, adding ``...`` if needed.

    Args:
        text: Input text (newlines are collapsed to spaces).
        width: Maximum output width.

    Returns:
        Truncated single-line string.
    """
    flat = text.replace("\n", " ")
    if len(flat) <= width:
        return flat
    return flat[: max(width - 3, 0)] + "..."


def _bar(count: int, max_count: int) -> str:
    """Render a bar-chart bar scaled to :data:`_MAX_BAR_WIDTH`.

    Args:
        count: Value for this bar.
        max_count: The largest value across all bars (used for scaling).

    Returns:
        A string of ``_BAR_CHAR`` characters.
    """
    if max_count <= 0:
        return ""
    width = max(1, round(count / max_count * _MAX_BAR_WIDTH))
    return _BAR_CHAR * width


def _format_timestamp(dt: datetime) -> str:
    """Format a datetime to ``YYYY-MM-DD`` for display.

    Args:
        dt: A datetime instance.

    Returns:
        A short date string.
    """
    return dt.strftime("%Y-%m-%d")


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (assume UTC if naive).

    Args:
        dt: A datetime that may or may not have tzinfo.

    Returns:
        A timezone-aware datetime in UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(mesh: MemoryMesh, scope: str | None = None) -> str:
    """Generate a formatted text report of memory analytics.

    Loads all memories from the given *scope* and computes summary
    statistics including scope breakdown, embedding coverage, importance
    distribution, most-accessed memories, stale memories, and topic
    breakdown.

    Args:
        mesh: A configured :class:`MemoryMesh` instance.
        scope: ``"project"``, ``"global"``, or ``None`` (default) to
            analyse both stores.

    Returns:
        A multi-line formatted text report suitable for display in a
        terminal or inclusion in logs.
    """
    memories = mesh.list(limit=100_000, scope=scope)
    now = _utcnow()

    lines: list[str] = []

    # -- Header ------------------------------------------------------------
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")
    lines.append("MemoryMesh Memory Report")
    lines.append(f"Generated: {timestamp}")
    lines.append("\u2550" * 64)  # ════...
    lines.append("")

    # -- Overview ----------------------------------------------------------
    lines.extend(_section_overview(memories, scope))
    lines.append("")

    # -- Importance Distribution -------------------------------------------
    lines.extend(_section_importance(memories))
    lines.append("")

    # -- Most Accessed Memories --------------------------------------------
    lines.extend(_section_most_accessed(memories))
    lines.append("")

    # -- Stale Memories ----------------------------------------------------
    lines.extend(_section_stale(memories, now))
    lines.append("")

    # -- Topics ------------------------------------------------------------
    lines.extend(_section_topics(memories))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------


def _section_overview(memories: list[Memory], scope: str | None) -> list[str]:
    """Build the Overview section.

    Args:
        memories: All loaded memories.
        scope: The scope filter that was applied (for display).

    Returns:
        Lines of text for the overview section.
    """
    total = len(memories)
    project_count = sum(1 for m in memories if m.scope == PROJECT_SCOPE)
    global_count = sum(1 for m in memories if m.scope == GLOBAL_SCOPE)
    with_emb = sum(1 for m in memories if m.embedding is not None and len(m.embedding) > 0)
    without_emb = total - with_emb

    lines: list[str] = []
    lines.append("Overview")
    lines.append("\u2500" * _SECTION_WIDTH)  # ────...
    lines.append(f"  Total memories:      {total}")
    if scope is None:
        lines.append(f"  Project memories:    {project_count}")
        lines.append(f"  Global memories:     {global_count}")
    lines.append(f"  With embeddings:     {with_emb}")
    lines.append(f"  Without embeddings:  {without_emb}")
    return lines


def _section_importance(memories: list[Memory]) -> list[str]:
    """Build the Importance Distribution section with bar chart.

    Args:
        memories: All loaded memories.

    Returns:
        Lines of text for the importance section.
    """
    # Count memories per bucket.
    bucket_counts: list[tuple[str, int]] = []
    for label, lo, hi in _IMPORTANCE_BUCKETS:
        count = sum(1 for m in memories if lo <= m.importance < hi)
        bucket_counts.append((label, count))

    max_count = max((c for _, c in bucket_counts), default=0)

    lines: list[str] = []
    lines.append("Importance Distribution")
    lines.append("\u2500" * _SECTION_WIDTH)

    # Find the longest label for alignment.
    label_width = max((len(label) for label, _ in bucket_counts), default=0)

    for label, count in bucket_counts:
        bar = _bar(count, max_count) if count > 0 else ""
        lines.append(f"  {label:<{label_width}}  {bar} {count}")

    return lines


def _section_most_accessed(memories: list[Memory]) -> list[str]:
    """Build the Most Accessed Memories section.

    Args:
        memories: All loaded memories.

    Returns:
        Lines of text for the most-accessed section.
    """
    lines: list[str] = []
    lines.append("Most Accessed Memories")
    lines.append("\u2500" * _SECTION_WIDTH)

    # Sort by access_count descending, take top N.
    accessed = sorted(memories, key=lambda m: m.access_count, reverse=True)
    top = [m for m in accessed[:_TOP_ACCESSED_LIMIT] if m.access_count > 0]

    if not top:
        lines.append("  (no memories have been accessed yet)")
        return lines

    for rank, mem in enumerate(top, start=1):
        preview = _truncate(mem.text, _TEXT_TRUNCATE_WIDTH)
        lines.append(f"  {rank}. [{mem.access_count}x] {preview} ({mem.scope})")

    return lines


def _section_stale(memories: list[Memory], now: datetime) -> list[str]:
    """Build the Stale Memories section.

    A memory is considered stale if its ``updated_at`` timestamp is
    older than :data:`_STALE_DAYS` days from *now*.

    Args:
        memories: All loaded memories.
        now: The current UTC time.

    Returns:
        Lines of text for the stale memories section.
    """
    lines: list[str] = []
    lines.append(f"Stale Memories (not accessed in {_STALE_DAYS}+ days)")
    lines.append("\u2500" * _SECTION_WIDTH)

    cutoff = now - timedelta(days=_STALE_DAYS)
    stale = [m for m in memories if _ensure_aware(m.updated_at) < cutoff]

    if not stale:
        lines.append("  (none)")
        return lines

    # Sort oldest first.
    stale.sort(key=lambda m: m.updated_at)

    for mem in stale:
        short_id = mem.id[:8]
        preview = _truncate(mem.text, _TEXT_TRUNCATE_WIDTH)
        last = _format_timestamp(mem.updated_at)
        bullet = "\u2022"
        lines.append(f'  {bullet} {short_id}  "{preview}"  ({mem.scope}, last: {last})')

    return lines


def _section_topics(memories: list[Memory]) -> list[str]:
    """Build the Topics section from metadata.

    Extracts the ``"topic"`` key from each memory's metadata and
    produces a frequency table.

    Args:
        memories: All loaded memories.

    Returns:
        Lines of text for the topics section.
    """
    lines: list[str] = []
    lines.append("Topics (from metadata)")
    lines.append("\u2500" * _SECTION_WIDTH)

    topic_counts: Counter[str] = Counter()
    no_topic_count = 0

    for mem in memories:
        topic = mem.metadata.get("topic") if mem.metadata else None
        if topic:
            topic_counts[str(topic)] += 1
        else:
            no_topic_count += 1

    if not topic_counts and no_topic_count == 0:
        lines.append("  (no memories)")
        return lines

    # Sort by count descending, then alphabetically.
    sorted_topics = sorted(topic_counts.items(), key=lambda x: (-x[1], x[0]))

    # Find the longest topic name for alignment.
    all_labels = [t for t, _ in sorted_topics] + (["(no topic)"] if no_topic_count > 0 else [])
    label_width = max((len(lbl) for lbl in all_labels), default=0)

    for topic, count in sorted_topics:
        suffix = "memory" if count == 1 else "memories"
        lines.append(f"  {topic:<{label_width}}  {count} {suffix}")

    if no_topic_count > 0:
        suffix = "memory" if no_topic_count == 1 else "memories"
        lines.append(f"  {'(no topic)':<{label_width}}  {no_topic_count} {suffix}")

    return lines
