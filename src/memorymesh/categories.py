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


# ---------------------------------------------------------------------------
# Subject-based scope inference
# ---------------------------------------------------------------------------

# Patterns whose subject is the USER (→ global scope).
_USER_SUBJECT_PATTERNS: list[re.Pattern[str]] = [
    # Explicit user references
    re.compile(r"\buser prefers?\b", re.IGNORECASE),
    re.compile(r"\buser likes?\b", re.IGNORECASE),
    re.compile(r"\buser wants?\b", re.IGNORECASE),
    re.compile(r"\buser hates?\b", re.IGNORECASE),
    re.compile(r"\buser always\b", re.IGNORECASE),
    re.compile(r"\buser never\b", re.IGNORECASE),
    re.compile(r"\buser[''\u2019]s\b", re.IGNORECASE),
    # Possessive name patterns: "<Name>'s patterns", "<Name>'s workflow"
    re.compile(r"\b[A-Z][a-z]+[''\u2019]s (?:pattern|workflow|habit|style|preference)", re.IGNORECASE),
    # Cross-project / universal phrasing
    re.compile(r"\bacross all projects?\b", re.IGNORECASE),
    re.compile(r"\bin every project\b", re.IGNORECASE),
    re.compile(r"\bglobal preference\b", re.IGNORECASE),
    re.compile(r"\bglobal setting\b", re.IGNORECASE),
    # Interaction / personality descriptions
    re.compile(r"\binteraction pattern", re.IGNORECASE),
    re.compile(r"\bcommunication style\b", re.IGNORECASE),
    re.compile(r"\bcoding style\b", re.IGNORECASE),
    re.compile(r"\bworkflow preference\b", re.IGNORECASE),
    re.compile(r"\bpersonal preference\b", re.IGNORECASE),
]

# Patterns whose subject is the PROJECT (→ project scope).
_PROJECT_SUBJECT_PATTERNS: list[re.Pattern[str]] = [
    # File paths and code references
    re.compile(r"\bsrc/"),
    re.compile(r"\btests?/"),
    re.compile(r"\b\w+\.py\b"),
    re.compile(r"\b\w+\.ts\b"),
    re.compile(r"\b\w+\.js\b"),
    re.compile(r"\b\w+\.go\b"),
    re.compile(r"\b\w+\.rs\b"),
    # Build / config files
    re.compile(r"\bpyproject\.toml\b"),
    re.compile(r"\bpackage\.json\b"),
    re.compile(r"\bCargo\.toml\b"),
    re.compile(r"\bgo\.mod\b"),
    re.compile(r"\bCLAUDE\.md\b"),
    re.compile(r"\bAGENTS\.md\b"),
    # Implementation specifics
    re.compile(r"\bimplementation state\b", re.IGNORECASE),
    re.compile(r"\bimplemented\b.*\b\d{4}-\d{2}-\d{2}\b", re.IGNORECASE),
    re.compile(r"\bv\d+\.\d+\.\d+\b.*\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\btests? pass", re.IGNORECASE),
    re.compile(r"\bcommit\b.*\b[0-9a-f]{7,}\b", re.IGNORECASE),
]


def infer_scope(
    text: str,
    category_scope: str | None = None,
    project_name: str | None = None,
) -> str | None:
    """Infer the correct scope based on the **subject** of the text.

    Analyses the text to determine whether it describes the *user* (habits,
    preferences, personality -- things that travel across projects) or the
    *project* (architecture, implementation, file paths -- things specific
    to one codebase).

    This is a second-pass refinement that can override the category-based
    scope when the subject clearly disagrees.  For example, a memory
    categorised as ``"pattern"`` (normally project scope) whose text says
    ``"Krishna's patterns: asks 'what does this mean' before acting"`` is
    about the **user**, not the codebase, so it should be global.

    Args:
        text: The memory text to analyse.
        category_scope: The scope already determined by category routing
            (``"project"`` or ``"global"``), or ``None`` if no category
            was set.
        project_name: Optional project/product name.  If the text mentions
            this name, it is considered project-specific.

    Returns:
        ``"global"``, ``"project"``, or ``None`` if no strong signal is
        found (meaning the caller should keep the existing scope).
    """
    user_score = 0
    project_score = 0

    for pattern in _USER_SUBJECT_PATTERNS:
        if pattern.search(text):
            user_score += 1

    for pattern in _PROJECT_SUBJECT_PATTERNS:
        if pattern.search(text):
            project_score += 1

    # Dynamic project-name pattern.
    if project_name and len(project_name) >= 3:
        name_pat = re.compile(rf"\b{re.escape(project_name)}\b", re.IGNORECASE)
        if name_pat.search(text):
            project_score += 2  # strong signal

    # Only override when there is a clear winner.
    if user_score > 0 and user_score > project_score:
        return "global"
    if project_score > 0 and project_score > user_score:
        return "project"

    return None


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
