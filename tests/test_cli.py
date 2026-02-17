"""Tests for the MemoryMesh CLI (``memorymesh.cli``).

Covers ``list``, ``search``, ``show``, ``stats``, and ``export``
subcommands.  All tests use ``tmp_path`` fixtures and invoke the CLI
via ``main()`` with explicit argv, capturing output with ``capsys``.
"""

from __future__ import annotations

import json

import pytest

from memorymesh import MemoryMesh
from memorymesh.cli import main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mesh(tmp_path):
    """Create a MemoryMesh instance with project + global stores in tmp_path."""
    m = MemoryMesh(
        path=str(tmp_path / "project.db"),
        global_path=str(tmp_path / "global.db"),
        embedding="none",
    )
    yield m
    m.close()


@pytest.fixture()
def populated_mesh(mesh):
    """A mesh pre-populated with a few memories in both scopes."""
    mesh.remember("MemoryMesh is the SQLite of AI Memory", importance=0.9, scope="project")
    mesh.remember("User prefers dark mode", importance=1.0, scope="global")
    mesh.remember("Architecture uses dual-store pattern", importance=0.7, scope="project")
    return mesh


def _cli(tmp_path, argv, mesh=None):
    """Helper to build CLI args with --project-path and --global-path."""
    base = [
        "--project-path", str(tmp_path / "project.db"),
        "--global-path", str(tmp_path / "global.db"),
    ]
    return base + argv


# ---------------------------------------------------------------------------
# No subcommand (help)
# ---------------------------------------------------------------------------


def test_no_subcommand(capsys):
    """Running with no subcommand prints help and returns 0."""
    rc = main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert "memorymesh" in captured.out.lower()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_empty_store(tmp_path, capsys):
    """Listing an empty store shows a friendly message."""
    m = MemoryMesh(
        path=str(tmp_path / "project.db"),
        global_path=str(tmp_path / "global.db"),
        embedding="none",
    )
    m.close()

    rc = main(_cli(tmp_path, ["list"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "No memories found" in captured.out


def test_list_with_memories(tmp_path, populated_mesh, capsys):
    """Listing shows memories in table format."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["list"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "ID" in captured.out
    assert "Scope" in captured.out
    assert "Showing 3 of 3" in captured.out


def test_list_scope_project(tmp_path, populated_mesh, capsys):
    """Listing with --scope project shows only project memories."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["list", "--scope", "project"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "Showing 2 of 2" in captured.out


def test_list_scope_global(tmp_path, populated_mesh, capsys):
    """Listing with --scope global shows only global memories."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["list", "--scope", "global"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "Showing 1 of 1" in captured.out


def test_list_json_format(tmp_path, populated_mesh, capsys):
    """Listing with --format json produces valid JSON without embeddings."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["list", "--format", "json"]))
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) == 3
    # Embeddings should be stripped.
    for item in data:
        assert "embedding" not in item


def test_list_pagination(tmp_path, populated_mesh, capsys):
    """Listing with --limit and --offset paginates correctly."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["list", "--limit", "1", "--offset", "0"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "Showing 1 of 3" in captured.out


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_finds_results(tmp_path, populated_mesh, capsys):
    """Searching for a keyword returns matching memories."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["search", "dark mode"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "dark mode" in captured.out.lower()


def test_search_no_results(tmp_path, populated_mesh, capsys):
    """Searching for a non-existent term shows a friendly message."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["search", "xyznonexistent"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "No memories found" in captured.out


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


def test_show_exact_id(tmp_path, mesh, capsys):
    """Showing a memory by exact ID displays full details."""
    mem_id = mesh.remember("Test memory for show command", scope="project")
    mesh.close()

    rc = main(_cli(tmp_path, ["show", mem_id]))
    assert rc == 0
    captured = capsys.readouterr()
    assert f"Memory {mem_id}" in captured.out
    assert "Test memory for show command" in captured.out
    assert "Scope:" in captured.out
    assert "Importance:" in captured.out


def test_show_partial_id(tmp_path, mesh, capsys):
    """Showing a memory by partial ID prefix works."""
    mem_id = mesh.remember("Partial ID test memory", scope="project")
    prefix = mem_id[:8]
    mesh.close()

    rc = main(_cli(tmp_path, ["show", prefix]))
    assert rc == 0
    captured = capsys.readouterr()
    assert f"Memory {mem_id}" in captured.out
    assert "Partial ID test memory" in captured.out


def test_show_not_found(tmp_path, mesh, capsys):
    """Showing a non-existent ID returns error."""
    mesh.close()
    rc = main(_cli(tmp_path, ["show", "deadbeef00000000"]))
    assert rc == 1
    captured = capsys.readouterr()
    assert "No memory found" in captured.err


def test_show_ambiguous_id(tmp_path, capsys):
    """Showing an ambiguous prefix returns an error listing matches."""
    m = MemoryMesh(
        path=str(tmp_path / "project.db"),
        global_path=str(tmp_path / "global.db"),
        embedding="none",
    )
    # Store many memories to increase chance of prefix collision.
    ids = []
    for i in range(200):
        ids.append(m.remember(f"Memory number {i}", scope="project"))
    m.close()

    # Find a 1-char prefix that matches multiple IDs.
    from collections import Counter

    prefix_counts = Counter(mid[0] for mid in ids)
    common_prefix = prefix_counts.most_common(1)[0][0]

    rc = main(_cli(tmp_path, ["show", common_prefix]))
    assert rc == 1
    captured = capsys.readouterr()
    assert "Ambiguous" in captured.err


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


def test_stats_empty(tmp_path, capsys):
    """Stats on empty store shows zero counts."""
    m = MemoryMesh(
        path=str(tmp_path / "project.db"),
        global_path=str(tmp_path / "global.db"),
        embedding="none",
    )
    m.close()

    rc = main(_cli(tmp_path, ["stats"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "Total:" in captured.out
    assert "0" in captured.out


def test_stats_with_memories(tmp_path, populated_mesh, capsys):
    """Stats shows correct counts for project and global."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["stats"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "Project memories:" in captured.out
    assert "Global memories:" in captured.out
    assert "2" in captured.out  # 2 project
    assert "1" in captured.out  # 1 global


def test_stats_scope_filter(tmp_path, populated_mesh, capsys):
    """Stats with --scope project shows only project info."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["stats", "--scope", "project"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "project" in captured.out.lower()
    assert "Memories:" in captured.out


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


def test_export_json_stdout(tmp_path, populated_mesh, capsys):
    """Export as JSON to stdout produces valid JSON."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["export", "--format", "json"]))
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) == 3


def test_export_json_file(tmp_path, populated_mesh, capsys):
    """Export as JSON to a file writes the file."""
    populated_mesh.close()
    outfile = str(tmp_path / "export.json")
    rc = main(_cli(tmp_path, ["export", "--format", "json", "-o", outfile]))
    assert rc == 0

    with open(outfile) as f:
        data = json.load(f)
    assert len(data) == 3


def test_export_html_stdout(tmp_path, populated_mesh, capsys):
    """Export as HTML to stdout produces valid HTML."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["export", "--format", "html"]))
    assert rc == 0
    captured = capsys.readouterr()
    assert "<!DOCTYPE html>" in captured.out
    assert "MemoryMesh Export" in captured.out


def test_export_html_file(tmp_path, populated_mesh, capsys):
    """Export as HTML to a file writes the file."""
    populated_mesh.close()
    outfile = str(tmp_path / "export.html")
    rc = main(_cli(tmp_path, ["export", "--format", "html", "-o", outfile]))
    assert rc == 0

    with open(outfile) as f:
        content = f.read()
    assert "<!DOCTYPE html>" in content


def test_export_scope_filter(tmp_path, populated_mesh, capsys):
    """Export with --scope project only exports project memories."""
    populated_mesh.close()
    rc = main(_cli(tmp_path, ["export", "--format", "json", "--scope", "project"]))
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 2
    assert all(m["scope"] == "project" for m in data)
