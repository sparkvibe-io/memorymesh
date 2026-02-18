"""Tests for the Gemini CLI format adapter (``memorymesh.formats.gemini``)."""

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
    return create_format_adapter("gemini")


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
    return mesh


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_creates_file(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "GEMINI.md")
    count = sync_to_format(populated_mesh, adapter, output)
    assert count > 0
    assert os.path.isfile(output)


def test_export_contains_memories(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "GEMINI.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "GEMINI.md").read_text()
    assert "dual-store" in content
    assert "dark mode" in content


def test_export_no_importance_prefix(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "GEMINI.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "GEMINI.md").read_text()
    assert "[importance:" not in content


def test_export_has_html_comment_importance(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "GEMINI.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "GEMINI.md").read_text()
    assert "<!-- memorymesh:importance=" in content


def test_export_has_section_heading(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "GEMINI.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "GEMINI.md").read_text()
    assert "## MemoryMesh Synced Memories" in content


def test_export_preserves_existing_content(tmp_path, adapter, populated_mesh):
    gemini_path = tmp_path / "GEMINI.md"
    gemini_path.write_text("# Project Config\n\nUser-authored instructions.\n")

    sync_to_format(populated_mesh, adapter, str(gemini_path))
    content = gemini_path.read_text()

    assert "# Project Config" in content
    assert "User-authored instructions." in content
    assert "## MemoryMesh Synced Memories" in content


def test_export_replaces_section_on_reexport(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "GEMINI.md")
    sync_to_format(populated_mesh, adapter, output)
    sync_to_format(populated_mesh, adapter, output)

    content = (tmp_path / "GEMINI.md").read_text()
    assert content.count("## MemoryMesh Synced Memories") == 1


def test_export_empty_returns_zero(tmp_path, adapter):
    m = MemoryMesh(
        path=str(tmp_path / "p.db"),
        global_path=str(tmp_path / "g.db"),
        embedding="none",
    )
    output = str(tmp_path / "GEMINI.md")
    count = sync_to_format(m, adapter, output)
    m.close()
    assert count == 0


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def test_import_parses_bullets(tmp_path, adapter):
    md = tmp_path / "GEMINI.md"
    md.write_text(
        "# GEMINI.md\n\n"
        "## MemoryMesh Synced Memories\n\n"
        "- Use SQLite for storage <!-- memorymesh:importance=0.85 -->\n"
        "- Plain text bullet\n"
    )
    entries = adapter.import_memories(str(md))
    assert len(entries) == 2
    assert entries[0][0] == "Use SQLite for storage"
    assert entries[0][1] == 0.85


def test_import_gemini_auto_section(tmp_path, adapter):
    """Gemini auto-added memories should be tagged with gemini_auto metadata."""
    md = tmp_path / "GEMINI.md"
    md.write_text(
        "## Gemini Added Memories\n\n- Gemini learned something\n\n## User Notes\n\n- User note\n"
    )
    entries = adapter.import_memories(str(md))
    assert len(entries) == 2

    # First entry (in Gemini auto section) should have gemini_auto metadata.
    assert entries[0][0] == "Gemini learned something"
    assert entries[0][2].get("gemini_auto") is True

    # Second entry (outside) should NOT have it.
    assert entries[1][0] == "User note"
    assert not entries[1][2].get("gemini_auto")


def test_import_file_not_found(adapter):
    with pytest.raises(FileNotFoundError):
        adapter.import_memories("/nonexistent/GEMINI.md")


def test_round_trip(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "GEMINI.md")
    sync_to_format(populated_mesh, adapter, output)

    mesh2 = MemoryMesh(
        path=str(tmp_path / "p2.db"),
        global_path=str(tmp_path / "g2.db"),
        embedding="none",
    )
    count = sync_from_format(mesh2, adapter, output, scope="project")
    assert count >= 2

    memories = mesh2.list(scope="project")
    importances = {round(m.importance, 2) for m in memories}
    assert 0.9 in importances or 1.0 in importances
    mesh2.close()


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_detect_project_path(tmp_path, adapter):
    path = adapter.detect_project_path(str(tmp_path))
    assert path == os.path.join(str(tmp_path), "GEMINI.md")


def test_is_installed(adapter):
    result = adapter.is_installed()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def test_init_creates_gemini_md(tmp_path, adapter):
    messages = adapter.init_project(str(tmp_path))
    assert len(messages) > 0

    gemini_path = tmp_path / "GEMINI.md"
    assert gemini_path.exists()
    content = gemini_path.read_text()
    assert "## MemoryMesh Synced Memories" in content


def test_init_appends_to_existing(tmp_path, adapter):
    gemini_path = tmp_path / "GEMINI.md"
    gemini_path.write_text("# Existing config\n\nUser stuff.\n")

    adapter.init_project(str(tmp_path))
    content = gemini_path.read_text()
    assert "# Existing config" in content
    assert "User stuff." in content
    assert "## MemoryMesh Synced Memories" in content


def test_init_idempotent(tmp_path, adapter):
    adapter.init_project(str(tmp_path))
    messages = adapter.init_project(str(tmp_path))
    assert any("already present" in m for m in messages)

    content = (tmp_path / "GEMINI.md").read_text()
    assert content.count("## MemoryMesh Synced Memories") == 1
