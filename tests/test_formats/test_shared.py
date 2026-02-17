"""Tests for shared format utilities (``memorymesh.formats._shared``)."""

from __future__ import annotations

from memorymesh.formats._shared import (
    importance_to_html_comment,
    inject_section,
    is_duplicate,
    normalise,
    parse_importance_from_html_comment,
    parse_importance_prefix,
)
from memorymesh.memory import Memory

# ---------------------------------------------------------------------------
# normalise
# ---------------------------------------------------------------------------


def test_normalise_lowercases():
    assert normalise("Hello World") == "hello world"


def test_normalise_collapses_whitespace():
    assert normalise("  hello   world  ") == "hello world"


def test_normalise_strips():
    assert normalise("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# is_duplicate
# ---------------------------------------------------------------------------


def test_is_duplicate_exact_match():
    mem = Memory(text="Use SQLite for storage")
    assert is_duplicate("Use SQLite for storage", [mem])


def test_is_duplicate_case_insensitive():
    mem = Memory(text="use sqlite for storage")
    assert is_duplicate("Use SQLite For Storage", [mem])


def test_is_duplicate_whitespace_normalised():
    mem = Memory(text="Use  SQLite   for storage")
    assert is_duplicate("Use SQLite for storage", [mem])


def test_is_duplicate_no_match():
    mem = Memory(text="Use SQLite for storage")
    assert not is_duplicate("Use PostgreSQL", [mem])


def test_is_duplicate_empty_candidates():
    assert not is_duplicate("anything", [])


# ---------------------------------------------------------------------------
# HTML comment helpers
# ---------------------------------------------------------------------------


def test_importance_to_html_comment():
    assert importance_to_html_comment(0.9) == "<!-- memorymesh:importance=0.90 -->"


def test_importance_to_html_comment_zero():
    assert importance_to_html_comment(0.0) == "<!-- memorymesh:importance=0.00 -->"


def test_parse_importance_from_html_comment():
    line = "Use SQLite <!-- memorymesh:importance=0.85 -->"
    text, imp = parse_importance_from_html_comment(line)
    assert text == "Use SQLite"
    assert imp == 0.85


def test_parse_importance_no_comment():
    line = "Use SQLite for storage"
    text, imp = parse_importance_from_html_comment(line)
    assert text == "Use SQLite for storage"
    assert imp == 0.5


def test_parse_importance_clamped():
    line = "text <!-- memorymesh:importance=1.50 -->"
    _text, imp = parse_importance_from_html_comment(line)
    assert imp == 1.0


# ---------------------------------------------------------------------------
# parse_importance_prefix
# ---------------------------------------------------------------------------


def test_parse_importance_prefix_match():
    text, imp = parse_importance_prefix("[importance: 0.90] Some memory")
    assert text == "Some memory"
    assert imp == 0.90


def test_parse_importance_prefix_no_match():
    text, imp = parse_importance_prefix("Just plain text")
    assert text == "Just plain text"
    assert imp == 0.5


# ---------------------------------------------------------------------------
# inject_section
# ---------------------------------------------------------------------------


def test_inject_section_into_empty_file():
    result = inject_section("", "## MemoryMesh Synced Memories\n\n- item 1")
    assert "## MemoryMesh Synced Memories" in result
    assert "- item 1" in result


def test_inject_section_appends():
    existing = "# My AGENTS.md\n\nSome user content.\n"
    section = "## MemoryMesh Synced Memories\n\n- memory 1"
    result = inject_section(existing, section)
    assert "# My AGENTS.md" in result
    assert "Some user content." in result
    assert "## MemoryMesh Synced Memories" in result
    assert "- memory 1" in result


def test_inject_section_replaces_existing():
    existing = (
        "# Header\n\n"
        "## MemoryMesh Synced Memories\n\n"
        "- old memory\n\n"
        "## Other Section\n\n"
        "Other content.\n"
    )
    section = "## MemoryMesh Synced Memories\n\n- new memory"
    result = inject_section(existing, section)
    assert "- old memory" not in result
    assert "- new memory" in result
    assert "## Other Section" in result
    assert "Other content." in result


def test_inject_section_preserves_content_above_and_below():
    existing = (
        "# Title\n\nBefore content.\n\n"
        "## MemoryMesh Synced Memories\n\n- old\n\n"
        "## Footer\n\nAfter content.\n"
    )
    section = "## MemoryMesh Synced Memories\n\n- replaced"
    result = inject_section(existing, section)
    assert "Before content." in result
    assert "After content." in result
    assert "- replaced" in result
    assert "- old" not in result
