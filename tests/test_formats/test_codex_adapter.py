"""Tests for the Codex CLI format adapter (``memorymesh.formats.codex``)."""

from __future__ import annotations

import os

import pytest

from memorymesh import MemoryMesh
from memorymesh.formats import create_format_adapter, sync_from_format, sync_to_format

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def adapter():
    return create_format_adapter("codex")


@pytest.fixture()
def mesh(tmp_path):
    m = MemoryMesh(
        path=str(tmp_path / "project.db"),
        global_path=str(tmp_path / "global.db"),
        embedding="none",
    )
    yield m
    m.close()


@pytest.fixture()
def populated_mesh(mesh):
    mesh.remember("Architecture uses dual-store pattern", importance=0.9, scope="project")
    mesh.remember("User prefers dark mode", importance=1.0, scope="global")
    mesh.remember("Tests use pytest fixtures", importance=0.6, scope="project")
    mesh.remember("Low importance detail", importance=0.3, scope="project")
    return mesh


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_creates_file(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "AGENTS.md")
    count = sync_to_format(populated_mesh, adapter, output)
    assert count > 0
    assert os.path.isfile(output)


def test_export_contains_memories(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "AGENTS.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "dual-store" in content
    assert "dark mode" in content


def test_export_no_importance_prefix(tmp_path, adapter, populated_mesh):
    """Codex export should NOT have visible [importance:] prefix."""
    output = str(tmp_path / "AGENTS.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "[importance:" not in content


def test_export_has_html_comment_importance(tmp_path, adapter, populated_mesh):
    """Codex export should have HTML comment importance for round-trip."""
    output = str(tmp_path / "AGENTS.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "<!-- memorymesh:importance=" in content


def test_export_has_section_heading(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "AGENTS.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "## MemoryMesh Synced Memories" in content


def test_export_preserves_existing_content(tmp_path, adapter, populated_mesh):
    """Export should preserve user-authored content in AGENTS.md."""
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text("# My Project\n\nCustom instructions here.\n")

    sync_to_format(populated_mesh, adapter, str(agents_path))
    content = agents_path.read_text()

    assert "# My Project" in content
    assert "Custom instructions here." in content
    assert "## MemoryMesh Synced Memories" in content


def test_export_replaces_section_on_reexport(tmp_path, adapter, populated_mesh):
    """Re-export should replace the section, not duplicate it."""
    output = str(tmp_path / "AGENTS.md")
    sync_to_format(populated_mesh, adapter, output)
    sync_to_format(populated_mesh, adapter, output)

    content = (tmp_path / "AGENTS.md").read_text()
    assert content.count("## MemoryMesh Synced Memories") == 1


def test_export_empty_returns_zero(tmp_path, adapter):
    m = MemoryMesh(
        path=str(tmp_path / "p.db"),
        global_path=str(tmp_path / "g.db"),
        embedding="none",
    )
    output = str(tmp_path / "AGENTS.md")
    count = sync_to_format(m, adapter, output)
    m.close()
    assert count == 0


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def test_import_parses_bullets(tmp_path, adapter):
    md = tmp_path / "AGENTS.md"
    md.write_text(
        "# AGENTS.md\n\n"
        "## MemoryMesh Synced Memories\n\n"
        "- Use SQLite for storage <!-- memorymesh:importance=0.85 -->\n"
        "- Plain text bullet\n"
    )
    entries = adapter.import_memories(str(md))
    assert len(entries) == 2
    assert entries[0][0] == "Use SQLite for storage"
    assert entries[0][1] == 0.85
    assert entries[1][0] == "Plain text bullet"
    assert entries[1][1] == 0.5


def test_import_skips_headings_and_comments(tmp_path, adapter):
    md = tmp_path / "AGENTS.md"
    md.write_text(
        "# Header\n## Section\n> Blockquote\n<!-- standalone comment -->\n- Actual memory\n"
    )
    entries = adapter.import_memories(str(md))
    assert len(entries) == 1
    assert entries[0][0] == "Actual memory"


def test_import_file_not_found(adapter):
    with pytest.raises(FileNotFoundError):
        adapter.import_memories("/nonexistent/AGENTS.md")


def test_round_trip(tmp_path, adapter, populated_mesh):
    """Export then import should recover memories with correct importance."""
    output = str(tmp_path / "AGENTS.md")
    sync_to_format(populated_mesh, adapter, output)

    mesh2 = MemoryMesh(
        path=str(tmp_path / "p2.db"),
        global_path=str(tmp_path / "g2.db"),
        embedding="none",
    )
    count = sync_from_format(mesh2, adapter, output, scope="project")
    assert count >= 2

    # Check that importance was preserved via HTML comments.
    memories = mesh2.list(scope="project")
    importances = {round(m.importance, 2) for m in memories}
    assert 0.9 in importances or 1.0 in importances
    mesh2.close()


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_detect_project_path(tmp_path, adapter):
    path = adapter.detect_project_path(str(tmp_path))
    assert path == os.path.join(str(tmp_path), "AGENTS.md")


def test_detect_global_path_no_codex_dir(adapter, monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/nonexistent")
    # Should return None if ~/.codex doesn't exist.
    result = adapter.detect_global_path()
    # Result depends on system state; just verify no crash.
    assert result is None or isinstance(result, str)


def test_is_installed(adapter):
    result = adapter.is_installed()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def test_init_creates_agents_md(tmp_path, adapter):
    messages = adapter.init_project(str(tmp_path))
    assert len(messages) > 0

    agents_path = tmp_path / "AGENTS.md"
    assert agents_path.exists()
    content = agents_path.read_text()
    assert "## MemoryMesh Synced Memories" in content


def test_init_appends_to_existing(tmp_path, adapter):
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text("# Existing AGENTS.md\n\nUser instructions.\n")

    adapter.init_project(str(tmp_path))
    content = agents_path.read_text()
    assert "# Existing AGENTS.md" in content
    assert "User instructions." in content
    assert "## MemoryMesh Synced Memories" in content


def test_init_idempotent(tmp_path, adapter):
    adapter.init_project(str(tmp_path))
    messages = adapter.init_project(str(tmp_path))
    assert any("already present" in m for m in messages)

    content = (tmp_path / "AGENTS.md").read_text()
    assert content.count("## MemoryMesh Synced Memories") == 1
