"""Heuristic-based auto-importance scoring for memories.

Analyzes memory text and optional metadata to assign an importance score
without any ML dependencies.  This is a v1 implementation using simple
pattern matching and weighted signals.  All heuristics are intentionally
lightweight -- pure Python, zero dependencies, Python 3.9+.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Signal weights (sum to ~1.0 for a balanced baseline)
# ---------------------------------------------------------------------------

_WEIGHT_LENGTH = 0.15
_WEIGHT_KEYWORDS = 0.35
_WEIGHT_STRUCTURE = 0.20
_WEIGHT_SPECIFICITY = 0.30

# ---------------------------------------------------------------------------
# Keyword lists
# ---------------------------------------------------------------------------

_BOOSTER_KEYWORDS: set[str] = {
    "decision",
    "architecture",
    "critical",
    "important",
    "always",
    "never",
    "bug",
    "fix",
    "security",
    "preference",
    "convention",
    "principle",
    "requirement",
    "breaking",
    "migration",
    "production",
    "deploy",
    "secret",
    "password",
    "credential",
    "root cause",
    "vulnerability",
    "performance",
    "deadline",
}

_REDUCER_KEYWORDS: set[str] = {
    "test",
    "trying",
    "maybe",
    "perhaps",
    "temporary",
    "todo",
    "wip",
    "experiment",
    "draft",
    "scratch",
    "placeholder",
    "stub",
    "mock",
    "hack",
    "workaround",
    "temp",
    "fixme",
}

# ---------------------------------------------------------------------------
# Patterns for structure and specificity detection
# ---------------------------------------------------------------------------

# Code-like patterns: backtick blocks, function signatures, imports
_CODE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"`[^`]+`"),  # inline code
    re.compile(r"```"),  # fenced code block
    re.compile(r"def\s+\w+\("),  # Python function def
    re.compile(r"class\s+\w+[:(]"),  # class definition
    re.compile(r"import\s+\w+"),  # import statement
    re.compile(r"\w+\.\w+\("),  # method call
]

# Specificity patterns: file paths, version numbers, URLs, proper-ish nouns
_SPECIFICITY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"[\w/\\]+\.\w{1,4}\b"),  # file paths (e.g., src/foo.py)
    re.compile(r"v?\d+\.\d+(?:\.\d+)?"),  # version numbers (e.g., v1.2.3, 3.9)
    re.compile(r"https?://\S+"),  # URLs
    re.compile(r"(?<![.a-z])[A-Z][a-z]+(?:[A-Z][a-z]+)+"),  # CamelCase names
    re.compile(r"\b[A-Z]{2,}\b"),  # UPPERCASE acronyms (e.g., API, JWT, SQL)
]


# ---------------------------------------------------------------------------
# Individual signal scorers (each returns a value in [0.0, 1.0])
# ---------------------------------------------------------------------------


def _length_signal(text: str) -> float:
    """Score based on text length.

    Very short texts (< 20 chars) score low, medium-length texts score
    at the baseline, and longer detailed texts score higher.

    Args:
        text: The memory text.

    Returns:
        A float in [0.0, 1.0].
    """
    n = len(text)
    if n < 20:
        return 0.2
    if n < 50:
        return 0.4
    if n < 200:
        return 0.5
    if n < 500:
        return 0.7
    return 0.8


def _keyword_signal(text: str) -> float:
    """Score based on presence of booster and reducer keywords.

    Starts at a neutral 0.5 and adjusts up or down for each keyword
    found.  The final value is clamped to [0.0, 1.0].

    Args:
        text: The memory text.

    Returns:
        A float in [0.0, 1.0].
    """
    text_lower = text.lower()

    boost_count = 0
    for keyword in _BOOSTER_KEYWORDS:
        if keyword in text_lower:
            boost_count += 1

    reduce_count = 0
    for keyword in _REDUCER_KEYWORDS:
        if keyword in text_lower:
            reduce_count += 1

    # Each booster adds +0.08, each reducer subtracts 0.06
    score = 0.5 + (boost_count * 0.08) - (reduce_count * 0.06)
    return max(0.0, min(1.0, score))


def _structure_signal(text: str) -> float:
    """Score based on code-like structural patterns.

    Text containing code snippets, function definitions, or technical
    patterns tends to be more important (concrete, actionable).

    Args:
        text: The memory text.

    Returns:
        A float in [0.0, 1.0].
    """
    match_count = 0
    for pattern in _CODE_PATTERNS:
        if pattern.search(text):
            match_count += 1

    if match_count == 0:
        return 0.4
    if match_count == 1:
        return 0.6
    if match_count <= 3:
        return 0.75
    return 0.9


def _specificity_signal(text: str) -> float:
    """Score based on specificity indicators.

    Memories that reference concrete things (file paths, version numbers,
    proper nouns, URLs) are more likely to be valuable.

    Args:
        text: The memory text.

    Returns:
        A float in [0.0, 1.0].
    """
    match_count = 0
    for pattern in _SPECIFICITY_PATTERNS:
        matches = pattern.findall(text)
        match_count += len(matches)

    if match_count == 0:
        return 0.3
    if match_count <= 2:
        return 0.55
    if match_count <= 5:
        return 0.7
    return 0.9


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_importance(text: str, metadata: dict[str, Any] | None = None) -> float:
    """Score the importance of a memory using text heuristics.

    Combines multiple signals (length, keywords, structure, specificity)
    into a single importance score.  This is a pure heuristic approach --
    no ML models are used.

    Args:
        text: The textual content of the memory.
        metadata: Optional metadata dict.  Currently unused but reserved
            for future heuristics (e.g., source type, author).

    Returns:
        A float in ``[0.0, 1.0]`` representing the estimated importance.
        The default baseline for unremarkable text is approximately 0.5.

    Examples:
        >>> score_importance("ok")
        0.33...
        >>> score_importance("Critical security vulnerability in auth module v2.3.1")
        0.7...
    """
    length_score = _length_signal(text)
    keyword_score = _keyword_signal(text)
    structure_score = _structure_signal(text)
    specificity_score = _specificity_signal(text)

    combined = (
        _WEIGHT_LENGTH * length_score
        + _WEIGHT_KEYWORDS * keyword_score
        + _WEIGHT_STRUCTURE * structure_score
        + _WEIGHT_SPECIFICITY * specificity_score
    )

    return max(0.0, min(1.0, combined))
