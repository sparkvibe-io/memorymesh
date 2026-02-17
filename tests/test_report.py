"""Tests for the ``memorymesh report`` module (``memorymesh.report``).

Covers report generation with various memory configurations.
"""

from __future__ import annotations

from memorymesh import MemoryMesh
from memorymesh.report import generate_report

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mesh(tmp_path):
    """Create a MemoryMesh instance."""
    return MemoryMesh(
        path=str(tmp_path / "project.db"),
        global_path=str(tmp_path / "global.db"),
        embedding="none",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_report_empty_store(tmp_path):
    """Report on empty store shows zero counts."""
    mesh = _make_mesh(tmp_path)
    report = generate_report(mesh)
    mesh.close()
    assert "Total memories:" in report
    assert "0" in report


def test_report_with_memories(tmp_path):
    """Report shows correct overview counts."""
    mesh = _make_mesh(tmp_path)
    mesh.remember("Project memory 1", scope="project", importance=0.9)
    mesh.remember("Project memory 2", scope="project", importance=0.6)
    mesh.remember("Global memory 1", scope="global", importance=1.0)
    report = generate_report(mesh)
    mesh.close()

    assert "Total memories:" in report
    assert "Project memories:" in report
    assert "Global memories:" in report


def test_report_importance_distribution(tmp_path):
    """Report shows importance distribution buckets."""
    mesh = _make_mesh(tmp_path)
    mesh.remember("Critical", scope="project", importance=0.95)
    mesh.remember("High", scope="project", importance=0.75)
    mesh.remember("Medium", scope="project", importance=0.55)
    mesh.remember("Low", scope="project", importance=0.3)
    report = generate_report(mesh)
    mesh.close()

    assert "Importance Distribution" in report
    assert "Critical" in report
    assert "High" in report
    assert "Medium" in report
    assert "Low" in report


def test_report_topics(tmp_path):
    """Report shows topic breakdown from metadata."""
    mesh = _make_mesh(tmp_path)
    mesh.remember("Arch decision", scope="project", metadata={"topic": "architecture"})
    mesh.remember("Arch pattern", scope="project", metadata={"topic": "architecture"})
    mesh.remember("Bug fix", scope="project", metadata={"topic": "debugging"})
    mesh.remember("No topic", scope="project")
    report = generate_report(mesh)
    mesh.close()

    assert "Topics" in report
    assert "architecture" in report
    assert "debugging" in report
    assert "(no topic)" in report


def test_report_most_accessed(tmp_path):
    """Report shows most accessed memories."""
    mesh = _make_mesh(tmp_path)
    mesh.remember("Frequently accessed", scope="project")
    # Access it a few times
    mesh.recall("Frequently accessed", k=1, scope="project")
    mesh.recall("Frequently accessed", k=1, scope="project")
    report = generate_report(mesh)
    mesh.close()

    assert "Most Accessed" in report


def test_report_stale_section_present(tmp_path):
    """Report includes stale memories section."""
    mesh = _make_mesh(tmp_path)
    mesh.remember("Some memory", scope="project")
    report = generate_report(mesh)
    mesh.close()

    assert "Stale Memories" in report


def test_report_scope_filter(tmp_path):
    """Report with scope filter only shows that scope."""
    mesh = _make_mesh(tmp_path)
    mesh.remember("Project only", scope="project")
    mesh.remember("Global only", scope="global")
    report = generate_report(mesh, scope="project")
    mesh.close()

    assert "Total memories:" in report
    # Should not show the scope breakdown when filtered
    assert "Project memories:" not in report


def test_report_via_cli(tmp_path, capsys):
    """report works through the main CLI entry point."""
    from memorymesh.cli import main

    mesh = _make_mesh(tmp_path)
    mesh.remember("CLI report test", scope="project")
    mesh.close()

    rc = main([
        "--project-path", str(tmp_path / "project.db"),
        "--global-path", str(tmp_path / "global.db"),
        "report",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "MemoryMesh Memory Report" in captured.out
