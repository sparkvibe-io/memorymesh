"""Memory categories with automatic scope routing and categorization.

Defines the set of valid memory categories, maps each to its default scope
(``"global"`` or ``"project"``), and provides a heuristic-based
auto-categorization function for incoming text.

Uses **only the Python standard library** -- no external dependencies.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Category → scope mapping
# ---------------------------------------------------------------------------

CATEGORY_SCOPE_MAP: dict[str, str] = {
    "preference": "global",
    "guardrail": "global",
    "mistake": "global",
    "personality": "global",
    "question": "global",
    "decision": "project",
    "pattern": "project",
    "context": "project",
    "session_summary": "project",
}
"""Maps each category name to its default scope."""

VALID_CATEGORIES: frozenset[str] = frozenset(CATEGORY_SCOPE_MAP.keys())
"""The set of all recognised category names."""

GLOBAL_CATEGORIES: frozenset[str] = frozenset(
    k for k, v in CATEGORY_SCOPE_MAP.items() if v == "global"
)
"""Categories that default to global scope."""

PROJECT_CATEGORIES: frozenset[str] = frozenset(
    k for k, v in CATEGORY_SCOPE_MAP.items() if v == "project"
)
"""Categories that default to project scope."""


# ---------------------------------------------------------------------------
# Validation and scope routing
# ---------------------------------------------------------------------------


def validate_category(category: str) -> None:
    """Validate that *category* is a recognised category name.

    Args:
        category: The category string to validate.

    Raises:
        ValueError: If *category* is not in :data:`VALID_CATEGORIES`.
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category {category!r}. Must be one of: {sorted(VALID_CATEGORIES)}"
        )


def scope_for_category(category: str) -> str:
    """Return the default scope for a given category.

    Args:
        category: A valid category name.

    Returns:
        ``"global"`` or ``"project"``.

    Raises:
        ValueError: If *category* is not recognised.
    """
    validate_category(category)
    return CATEGORY_SCOPE_MAP[category]


# ---------------------------------------------------------------------------
# Auto-categorization keyword patterns
# ---------------------------------------------------------------------------

# Each entry is (category, compiled_patterns).  Patterns are tried in order;
# the first category with a match wins.  The list is ordered from most
# specific to least specific so that narrow categories beat broad ones.

_CATEGORY_PATTERNS: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "guardrail",
        [
            re.compile(r"\bnever\b", re.IGNORECASE),
            re.compile(r"\bdon'?t\b", re.IGNORECASE),
            re.compile(r"\bmust not\b", re.IGNORECASE),
            re.compile(r"\bavoid\b", re.IGNORECASE),
            re.compile(r"\bdo not\b", re.IGNORECASE),
            re.compile(r"\bforbid", re.IGNORECASE),
            re.compile(r"\bprohibit", re.IGNORECASE),
            re.compile(r"\brule:\s", re.IGNORECASE),
        ],
    ),
    (
        "mistake",
        [
            re.compile(r"\bmistake\b", re.IGNORECASE),
            re.compile(r"\bbug\b", re.IGNORECASE),
            re.compile(r"\bbroke\b", re.IGNORECASE),
            re.compile(r"\bforgot\b", re.IGNORECASE),
            re.compile(r"\bshould have\b", re.IGNORECASE),
            re.compile(r"\blesson\b", re.IGNORECASE),
            re.compile(r"\blearned\b", re.IGNORECASE),
            re.compile(r"\bregret\b", re.IGNORECASE),
            re.compile(r"\baccident", re.IGNORECASE),
        ],
    ),
    (
        "personality",
        [
            re.compile(r"\bI am\b", re.IGNORECASE),
            re.compile(r"\bI work\b", re.IGNORECASE),
            re.compile(r"\bmy role\b", re.IGNORECASE),
            re.compile(r"\bsenior\b", re.IGNORECASE),
            re.compile(r"\bjunior\b", re.IGNORECASE),
            re.compile(r"\bmy background\b", re.IGNORECASE),
            re.compile(r"\byears? of experience\b", re.IGNORECASE),
            re.compile(r"\bmy name\b", re.IGNORECASE),
        ],
    ),
    (
        "preference",
        [
            re.compile(r"\bprefer\b", re.IGNORECASE),
            re.compile(r"\balways use\b", re.IGNORECASE),
            re.compile(r"\blike to\b", re.IGNORECASE),
            re.compile(r"\bstyle\b", re.IGNORECASE),
            re.compile(r"\bfavou?rite\b", re.IGNORECASE),
            re.compile(r"\bdefault to\b", re.IGNORECASE),
        ],
    ),
    (
        "question",
        [
            re.compile(r"\bwhy\b.*\?", re.IGNORECASE),
            re.compile(r"\bhow\b.*\?", re.IGNORECASE),
            re.compile(r"\bwhat if\b", re.IGNORECASE),
            re.compile(r"\bconcern\b", re.IGNORECASE),
            re.compile(r"\bwonder\b", re.IGNORECASE),
            re.compile(r"\bcurious\b", re.IGNORECASE),
        ],
    ),
    (
        "decision",
        [
            re.compile(r"\bdecided\b", re.IGNORECASE),
            re.compile(r"\bchose\b", re.IGNORECASE),
            re.compile(r"\bpicked\b", re.IGNORECASE),
            re.compile(r"\bapproach\b", re.IGNORECASE),
            re.compile(r"\barchitecture\b", re.IGNORECASE),
            re.compile(r"\bwent with\b", re.IGNORECASE),
            re.compile(r"\bselected\b", re.IGNORECASE),
        ],
    ),
    (
        "pattern",
        [
            re.compile(r"\bconvention\b", re.IGNORECASE),
            re.compile(r"\bpattern\b", re.IGNORECASE),
            re.compile(r"\bstyle guide\b", re.IGNORECASE),
            re.compile(r"\balways do\b", re.IGNORECASE),
            re.compile(r"\bcoding standard\b", re.IGNORECASE),
            re.compile(r"\bbest practice\b", re.IGNORECASE),
        ],
    ),
    (
        "session_summary",
        [
            re.compile(r"\bsession summary\b", re.IGNORECASE),
            re.compile(r"\bsummary of\b.*\bsession\b", re.IGNORECASE),
            re.compile(r"\bwhat we did\b", re.IGNORECASE),
            re.compile(r"\baccomplished\b", re.IGNORECASE),
        ],
    ),
]


def auto_categorize(text: str, metadata: dict[str, Any] | None = None) -> str:
    """Detect the most likely category for a piece of text.

    Uses keyword/pattern matching to classify text into one of the
    recognised memory categories.  Falls back to ``"context"`` when no
    specific category is detected.

    Args:
        text: The memory text to classify.
        metadata: Optional metadata dict (reserved for future heuristics).

    Returns:
        A category name from :data:`VALID_CATEGORIES`.
    """
    # Check metadata hint first -- if the caller already tagged a category
    # in metadata, honour it.
    if metadata:
        hint = metadata.get("category")
        if isinstance(hint, str) and hint in VALID_CATEGORIES:
            return hint

    for category, patterns in _CATEGORY_PATTERNS:
        for pattern in patterns:
            if pattern.search(text):
                return category

    # Default fallback for project-specific facts.
    return "context"
