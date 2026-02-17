"""Tests for the Claude Code format adapter (``memorymesh.formats.claude``)."""

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
    return create_format_adapter("claude")


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
    mesh.remember("Tests use pytest", importance=0.6, scope="project")
    return mesh


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_creates_file(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "MEMORY.md")
    count = sync_to_format(populated_mesh, adapter, output)
    assert count > 0
    assert os.path.isfile(output)


def test_export_contains_memories(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "MEMORY.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "MEMORY.md").read_text()
    assert "dual-store" in content
    assert "dark mode" in content


def test_export_has_importance_prefix(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "MEMORY.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "MEMORY.md").read_text()
    assert "[importance: 0.90]" in content


def test_export_has_header(tmp_path, adapter, populated_mesh):
    output = str(tmp_path / "MEMORY.md")
    sync_to_format(populated_mesh, adapter, output)
    content = (tmp_path / "MEMORY.md").read_text()
    assert "# Project Memory (synced by MemoryMesh)" in content


def test_export_empty_writes_placeholder(tmp_path, adapter):
    output = str(tmp_path / "MEMORY.md")
    m = MemoryMesh(
        path=str(tmp_path / "p.db"),
        global_path=str(tmp_path / "g.db"),
        embedding="none",
    )
    memories = m.list()
    adapter.export_memories(memories, output)
    m.close()
    content = (tmp_path / "MEMORY.md").read_text()
    assert "No memories stored" in content


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def test_import_parses_bullets(tmp_path, adapter):
    md = tmp_path / "MEMORY.md"
    md.write_text(
        "# Header\n\n"
        "- [importance: 0.85] Decision A\n"
        "- Plain text\n"
    )
    entries = adapter.import_memories(str(md))
    assert len(entries) == 2
    assert entries[0] == ("Decision A", 0.85, {})
    assert entries[1][0] == "Plain text"
    assert entries[1][1] == 0.5


def test_import_file_not_found(adapter):
    with pytest.raises(FileNotFoundError):
        adapter.import_memories("/nonexistent/MEMORY.md")


def test_round_trip(tmp_path, adapter, populated_mesh):
    """Export then import should recover memories."""
    output = str(tmp_path / "MEMORY.md")
    sync_to_format(populated_mesh, adapter, output)

    mesh2 = MemoryMesh(
        path=str(tmp_path / "p2.db"),
        global_path=str(tmp_path / "g2.db"),
        embedding="none",
    )
    count = sync_from_format(mesh2, adapter, output, scope="project")
    assert count >= 2
    mesh2.close()


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_detect_global_path_returns_none(adapter):
    assert adapter.detect_global_path() is None


def test_is_installed(adapter):
    # On a machine with Claude Code installed, this should be True.
    # On CI without ~/.claude, it will be False. Just check it doesn't crash.
    result = adapter.is_installed()
    assert isinstance(result, bool)
