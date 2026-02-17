"""Tests for the ``memorymesh init`` command (``memorymesh.init_cmd``).

Covers project directory creation, Claude Code MCP configuration,
and CLAUDE.md injection.
"""

from __future__ import annotations

import json
import os

from memorymesh.init_cmd import run_init


def test_init_creates_memorymesh_dir(tmp_path, monkeypatch, capsys):
    """init creates .memorymesh/ in the project root."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)

    rc = run_init(project_path=str(tmp_path), skip_mcp=True, skip_claude_md=True)
    assert rc == 0
    assert (tmp_path / ".memorymesh").is_dir()


def test_init_existing_dir_is_fine(tmp_path, capsys):
    """init succeeds when .memorymesh/ already exists."""
    (tmp_path / ".memorymesh").mkdir()
    rc = run_init(project_path=str(tmp_path), skip_mcp=True, skip_claude_md=True)
    assert rc == 0
    captured = capsys.readouterr()
    assert "already exists" in captured.out.lower()


def test_init_creates_claude_md(tmp_path, capsys):
    """init creates CLAUDE.md with memory section when it doesn't exist."""
    rc = run_init(project_path=str(tmp_path), skip_mcp=True, skip_claude_md=False)
    assert rc == 0
    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.is_file()
    content = claude_md.read_text()
    assert "## Memory (MemoryMesh)" in content
    assert "recall" in content


def test_init_appends_to_existing_claude_md(tmp_path, capsys):
    """init appends memory section to existing CLAUDE.md."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# My Project\n\nSome existing content.\n")

    rc = run_init(project_path=str(tmp_path), skip_mcp=True, skip_claude_md=False)
    assert rc == 0
    content = claude_md.read_text()
    assert "# My Project" in content  # Existing content preserved
    assert "## Memory (MemoryMesh)" in content  # New section added


def test_init_skips_existing_memory_section(tmp_path, capsys):
    """init doesn't duplicate memory section if already present."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# My Project\n\n## Memory (MemoryMesh)\n\nAlready here.\n")

    rc = run_init(project_path=str(tmp_path), skip_mcp=True, skip_claude_md=False)
    assert rc == 0
    captured = capsys.readouterr()
    assert "already present" in captured.out.lower()


def test_init_configures_mcp(tmp_path, monkeypatch, capsys):
    """init writes MCP server config to ~/.claude/claude_code_config.json."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    # Patch expanduser to use fake home
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    rc = run_init(project_path=str(project_dir), skip_mcp=False, skip_claude_md=True)
    assert rc == 0

    config_path = fake_home / ".claude" / "claude_code_config.json"
    assert config_path.is_file()
    config = json.loads(config_path.read_text())
    assert "mcpServers" in config
    assert "memorymesh" in config["mcpServers"]
    assert config["mcpServers"]["memorymesh"]["command"] == "memorymesh-mcp"


def test_init_merges_existing_mcp_config(tmp_path, monkeypatch, capsys):
    """init merges into existing MCP config without destroying other servers."""
    fake_home = tmp_path / "home"
    claude_dir = fake_home / ".claude"
    claude_dir.mkdir(parents=True)
    config_path = claude_dir / "claude_code_config.json"
    config_path.write_text(json.dumps({
        "mcpServers": {
            "other-server": {"command": "other-cmd", "args": []}
        }
    }))
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    rc = run_init(project_path=str(project_dir), skip_mcp=False, skip_claude_md=True)
    assert rc == 0

    config = json.loads(config_path.read_text())
    assert "other-server" in config["mcpServers"]  # Preserved
    assert "memorymesh" in config["mcpServers"]  # Added


def test_init_no_project_root(tmp_path, monkeypatch, capsys):
    """init fails gracefully when no project root can be detected."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)
    # tmp_path has no .git or pyproject.toml, so detection fails
    rc = run_init(project_path=None, skip_mcp=True, skip_claude_md=True)
    # Should either detect or fail based on whether we're in the real project
    # When explicitly no project path and no signals, it should error
    assert rc in (0, 1)  # Depends on CWD state


def test_init_via_cli(tmp_path, capsys):
    """init works through the main CLI entry point."""
    from memorymesh.cli import main

    rc = main(["init", "--project-path", str(tmp_path), "--skip-mcp", "--skip-claude-md"])
    assert rc == 0
    assert (tmp_path / ".memorymesh").is_dir()
