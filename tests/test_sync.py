"""Tests for the ``memorymesh sync`` module (``memorymesh.sync``).

Covers export to MEMORY.md, import from MEMORY.md, duplicate detection,
importance parsing, and line limit truncation.
"""

from __future__ import annotations

import os

import pytest

from memorymesh import MemoryMesh
from memorymesh.sync import sync_from_memory_md, sync_to_memory_md

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mesh(tmp_path):
    """Create a MemoryMesh instance with project + global stores."""
    m = MemoryMesh(
        path=str(tmp_path / "project.db"),
        global_path=str(tmp_path / "global.db"),
        embedding="none",
    )
    yield m
    m.close()


@pytest.fixture()
def populated_mesh(mesh):
    """A mesh with memories in both scopes."""
    mesh.remember("Architecture uses dual-store pattern", importance=0.9, scope="project")
    mesh.remember("User prefers dark mode", importance=1.0, scope="global")
    mesh.remember("Tests use pytest with tmp_path fixtures", importance=0.6, scope="project")
    mesh.remember("Low importance memory", importance=0.3, scope="project")
    return mesh


# ---------------------------------------------------------------------------
# sync_to_memory_md
# ---------------------------------------------------------------------------


def test_export_creates_file(tmp_path, populated_mesh):
    """Export creates a MEMORY.md file."""
    output = str(tmp_path / "MEMORY.md")
    count = sync_to_memory_md(populated_mesh, output)
    assert count > 0
    assert os.path.isfile(output)


def test_export_contains_memories(tmp_path, populated_mesh):
    """Exported file contains memory text."""
    output = str(tmp_path / "MEMORY.md")
    sync_to_memory_md(populated_mesh, output)
    content = (tmp_path / "MEMORY.md").read_text()
    assert "dual-store" in content
    assert "dark mode" in content


def test_export_has_header(tmp_path, populated_mesh):
    """Exported file has the standard header."""
    output = str(tmp_path / "MEMORY.md")
    sync_to_memory_md(populated_mesh, output)
    content = (tmp_path / "MEMORY.md").read_text()
    assert "# Project Memory (synced by MemoryMesh)" in content
    assert "Auto-generated" in content


def test_export_importance_prefix(tmp_path, populated_mesh):
    """Each bullet has [importance: X.XX] prefix."""
    output = str(tmp_path / "MEMORY.md")
    sync_to_memory_md(populated_mesh, output)
    content = (tmp_path / "MEMORY.md").read_text()
    assert "[importance: 0.90]" in content
    assert "[importance: 1.00]" in content


def test_export_empty_store(tmp_path):
    """Exporting empty store creates file with 'no memories' message."""
    m = MemoryMesh(
        path=str(tmp_path / "project.db"),
        global_path=str(tmp_path / "global.db"),
        embedding="none",
    )
    output = str(tmp_path / "MEMORY.md")
    count = sync_to_memory_md(m, output)
    m.close()
    assert count == 0
    content = (tmp_path / "MEMORY.md").read_text()
    assert "No memories stored" in content


def test_export_scope_filter(tmp_path, populated_mesh):
    """Exporting with scope filter only includes matching memories."""
    output = str(tmp_path / "MEMORY.md")
    sync_to_memory_md(populated_mesh, output, scope="project")
    content = (tmp_path / "MEMORY.md").read_text()
    assert "dual-store" in content
    assert "dark mode" not in content  # Global memory excluded


def test_export_respects_line_limit(tmp_path):
    """Export truncates when exceeding 200 lines."""
    m = MemoryMesh(
        path=str(tmp_path / "project.db"),
        global_path=str(tmp_path / "global.db"),
        embedding="none",
    )
    # Create enough memories to exceed 200 lines
    for i in range(250):
        m.remember(f"Memory number {i} with some extra text to fill the line", scope="project")

    output = str(tmp_path / "MEMORY.md")
    sync_to_memory_md(m, output, limit=250)
    m.close()

    lines = (tmp_path / "MEMORY.md").read_text().splitlines()
    assert len(lines) <= 200


# ---------------------------------------------------------------------------
# sync_from_memory_md
# ---------------------------------------------------------------------------


def test_import_from_file(tmp_path, mesh):
    """Import reads bullet points from a MEMORY.md file."""
    md_file = tmp_path / "MEMORY.md"
    md_file.write_text(
        "# Project Memory\n\n"
        "> Some header\n\n"
        "## Decisions\n\n"
        "- [importance: 0.90] Use SQLite for storage\n"
        "- [importance: 0.70] Prefer dataclasses over dicts\n"
        "- Simple text without importance\n"
    )
    count = sync_from_memory_md(mesh, str(md_file), scope="project")
    assert count == 3

    # Verify they're stored
    assert mesh.count(scope="project") == 3


def test_import_extracts_importance(tmp_path, mesh):
    """Import correctly parses importance from [importance: X.XX] prefix."""
    md_file = tmp_path / "MEMORY.md"
    md_file.write_text("- [importance: 0.85] High importance memory\n")
    sync_from_memory_md(mesh, str(md_file), scope="project")

    memories = mesh.list(scope="project")
    assert len(memories) == 1
    assert memories[0].importance == 0.85


def test_import_default_importance(tmp_path, mesh):
    """Import defaults to 0.5 importance when no prefix."""
    md_file = tmp_path / "MEMORY.md"
    md_file.write_text("- Memory without importance prefix\n")
    sync_from_memory_md(mesh, str(md_file), scope="project")

    memories = mesh.list(scope="project")
    assert len(memories) == 1
    assert memories[0].importance == 0.5


def test_import_skips_duplicates(tmp_path, mesh):
    """Import doesn't create duplicate memories."""
    mesh.remember("Use SQLite for storage", scope="project")

    md_file = tmp_path / "MEMORY.md"
    md_file.write_text("- Use SQLite for storage\n")
    count = sync_from_memory_md(mesh, str(md_file), scope="project")
    assert count == 0  # Already exists


def test_import_adds_metadata(tmp_path, mesh):
    """Imported memories have source metadata."""
    md_file = tmp_path / "MEMORY.md"
    md_file.write_text("- Imported decision\n")
    sync_from_memory_md(mesh, str(md_file), scope="project")

    memories = mesh.list(scope="project")
    assert memories[0].metadata.get("source") == "memory.md"
    assert memories[0].metadata.get("imported") is True


def test_import_file_not_found(tmp_path, mesh):
    """Import raises FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        sync_from_memory_md(mesh, str(tmp_path / "nonexistent.md"))


def test_import_skips_headers(tmp_path, mesh):
    """Import skips header lines (#), blockquotes (>), and empty lines."""
    md_file = tmp_path / "MEMORY.md"
    md_file.write_text(
        "# Header\n"
        "\n"
        "> Blockquote\n"
        "\n"
        "## Section\n"
        "\n"
        "- Actual memory\n"
    )
    count = sync_from_memory_md(mesh, str(md_file), scope="project")
    assert count == 1


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_sync_via_cli_to(tmp_path, populated_mesh, capsys):
    """sync --to works through the CLI."""
    from memorymesh.cli import main

    output = str(tmp_path / "export.md")
    populated_mesh.close()
    rc = main([
        "--project-path", str(tmp_path / "project.db"),
        "--global-path", str(tmp_path / "global.db"),
        "sync", "--to", output,
    ])
    assert rc == 0
    assert os.path.isfile(output)


def test_sync_via_cli_from(tmp_path, capsys):
    """sync --from works through the CLI."""
    from memorymesh.cli import main

    md_file = tmp_path / "input.md"
    md_file.write_text("- CLI import test memory\n")

    rc = main([
        "--project-path", str(tmp_path / "project.db"),
        "--global-path", str(tmp_path / "global.db"),
        "sync", "--from", str(md_file),
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Imported 1" in captured.out
