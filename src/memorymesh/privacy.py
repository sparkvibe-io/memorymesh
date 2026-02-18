"""Privacy guard -- detect and optionally redact secrets before storing memories.

Provides regex-based detection of common secret patterns (API keys, tokens,
passwords, private keys) and optional redaction.  Runs on the write path
to warn users when sensitive data is about to be stored.

Uses **only the Python standard library** -- no external dependencies.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Secret detection patterns
# ---------------------------------------------------------------------------

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:sk|pk)[-_][a-zA-Z0-9_-]{20,}"), "API key"),
    (re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}"), "GitHub token"),
    (re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE), "password"),
    (re.compile(r"(?:secret|token|key)\s*[:=]\s*['\"]?\S{8,}", re.IGNORECASE), "secret/token"),
    (re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"), "private key"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "JWT token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"xox[bpsar]-[A-Za-z0-9-]{10,}"), "Slack token"),
]


def check_for_secrets(text: str) -> list[str]:
    """Check text for potential secrets and return detected types.

    Args:
        text: The text to scan for secrets.

    Returns:
        A list of detected secret type names (e.g. ``["API key", "JWT token"]``).
        Empty list means no secrets detected.
    """
    found: list[str] = []
    seen: set[str] = set()
    for pattern, label in _SECRET_PATTERNS:
        if label not in seen and pattern.search(text):
            found.append(label)
            seen.add(label)
    return found


def redact_secrets(text: str) -> str:
    """Replace detected secrets in text with ``[REDACTED]``.

    Args:
        text: The text containing potential secrets.

    Returns:
        Text with all detected secret patterns replaced by ``[REDACTED]``.
    """
    result = text
    for pattern, _label in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result
