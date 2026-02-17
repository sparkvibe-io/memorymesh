"""Tests for the MemoryMesh HTML export (``memorymesh.html_export``).

Verifies that ``generate_html()`` produces valid, self-contained HTML
with correct content, XSS protection, and all expected UI elements.
"""

from __future__ import annotations

from memorymesh.html_export import generate_html
from memorymesh.memory import Memory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_memory(
    text: str = "Test memory",
    scope: str = "project",
    importance: float = 0.5,
    metadata: dict | None = None,
    access_count: int = 0,
) -> Memory:
    """Create a Memory for testing."""
    return Memory(
        text=text,
        scope=scope,
        importance=importance,
        metadata=metadata or {},
        access_count=access_count,
    )


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


def test_generates_valid_html():
    """Output is a complete HTML document."""
    html = generate_html([])
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html
    assert "<head>" in html
    assert "<body>" in html


def test_title_in_output():
    """Custom title appears in the HTML."""
    html = generate_html([], title="My Custom Title")
    assert "My Custom Title" in html


def test_empty_memories_shows_message():
    """Empty memory list shows a 'no memories' message."""
    html = generate_html([])
    assert "No memories stored yet" in html


def test_paths_in_subtitle():
    """Project and global paths appear in the subtitle."""
    html = generate_html(
        [],
        project_path="/home/user/.memorymesh/project.db",
        global_path="/home/user/.memorymesh/global.db",
    )
    assert "/home/user/.memorymesh/project.db" in html
    assert "/home/user/.memorymesh/global.db" in html


# ---------------------------------------------------------------------------
# Memory cards
# ---------------------------------------------------------------------------


def test_memory_text_appears():
    """Memory text content appears in the HTML."""
    mem = _make_memory(text="This is a test memory about architecture.")
    html = generate_html([mem])
    assert "This is a test memory about architecture." in html


def test_scope_badges():
    """Project and global memories get different scope badges."""
    memories = [
        _make_memory(text="Project memory", scope="project"),
        _make_memory(text="Global memory", scope="global"),
    ]
    html = generate_html(memories)
    assert "scope-project" in html
    assert "scope-global" in html


def test_importance_bar():
    """Importance value is rendered in the bar."""
    mem = _make_memory(importance=0.85)
    html = generate_html([mem])
    assert "0.85" in html
    assert "width:85%" in html


def test_metadata_rendered():
    """Metadata key-value pairs appear in the card."""
    mem = _make_memory(metadata={"topic": "architecture", "source": "user"})
    html = generate_html([mem])
    assert "topic" in html
    assert "architecture" in html
    assert "source" in html
    assert "user" in html


def test_access_count():
    """Access count appears in the card header."""
    mem = _make_memory(access_count=5)
    html = generate_html([mem])
    assert "5x" in html


def test_memory_id_truncated():
    """Only the first 8 chars of the ID appear in the card."""
    mem = _make_memory()
    html = generate_html([mem])
    assert mem.id[:8] in html


# ---------------------------------------------------------------------------
# Counts and filters
# ---------------------------------------------------------------------------


def test_scope_counts():
    """Filter buttons show correct scope counts."""
    memories = [
        _make_memory(scope="project"),
        _make_memory(scope="project"),
        _make_memory(scope="global"),
    ]
    html = generate_html(memories)
    assert "All (3)" in html
    assert "Project (2)" in html
    assert "Global (1)" in html


# ---------------------------------------------------------------------------
# XSS protection
# ---------------------------------------------------------------------------


def test_xss_in_text():
    """Script tags in memory text are escaped."""
    mem = _make_memory(text='<script>alert("xss")</script>')
    html = generate_html([mem])
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_xss_in_metadata():
    """Script tags in metadata values are escaped."""
    mem = _make_memory(metadata={"key": '<img onerror="alert(1)" src=x>'})
    html = generate_html([mem])
    assert 'onerror="alert' not in html
    assert "&lt;img" in html


def test_xss_in_title():
    """Script tags in the title are escaped."""
    html = generate_html([], title='<script>alert("title")</script>')
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# CSS and JS
# ---------------------------------------------------------------------------


def test_inline_css():
    """CSS is embedded inline (no external stylesheet links)."""
    html = generate_html([])
    assert "<style>" in html
    assert "prefers-color-scheme: dark" in html
    # No external CSS links
    assert '<link rel="stylesheet"' not in html


def test_inline_js():
    """JavaScript is embedded inline (no external script sources)."""
    html = generate_html([])
    assert "<script>" in html
    # No external script tags
    assert "src=" not in html.split("<script>")[0].split("</script>")[0] if "<script>" in html else True


def test_search_box():
    """Search input is present."""
    html = generate_html([])
    assert 'id="search"' in html
    assert "Search memories" in html


def test_responsive_viewport():
    """Viewport meta tag is present for mobile responsiveness."""
    html = generate_html([])
    assert 'name="viewport"' in html
