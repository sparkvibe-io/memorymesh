"""MemoryMesh ``init`` command -- project setup and MCP auto-configuration.

Implements the ``memorymesh init`` command which:

1. Detects the current project root.
2. Creates the ``.memorymesh/`` directory.
3. Auto-configures the Claude Code MCP server entry.
4. Injects the standard memory instructions into ``CLAUDE.md``.

Uses **only the Python standard library** (json, os, pathlib).
"""

from __future__ import annotations

import contextlib
import json
import os
import sys

from .store import detect_project_root

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MEMORYMESH_DIR = ".memorymesh"

_MCP_SERVER_ENTRY = {
    "command": "memorymesh-mcp",
    "args": [],
    "env": {},
}

_CLAUDE_MD_SECTION_HEADING = "## Memory (MemoryMesh)"

_CLAUDE_MD_SECTION = """\
## Memory (MemoryMesh)

MemoryMesh is configured as an MCP tool in this project. It adds persistent,
structured, cross-tool memory on top of your existing memory system. Use it
alongside your default memory -- it enhances, not replaces.

### At the start of every conversation

Call `mcp__memorymesh__recall` with a summary of the user's request to load
prior context, decisions, and patterns. If `session_start` is available,
call it to load user profile, guardrails, and project context.

### When to `recall`

- **Start of every conversation**: Check for relevant prior context.
- **Before making decisions**: Check if this was decided before.
- **When debugging**: Check if this problem was encountered previously.

### When to `remember`

- **When the user says "remember this"**: Store it with a category.
- **After completing a task**: Store key decisions and patterns.
  Use `category` to classify: `"decision"`, `"pattern"`, `"context"`.
- **When the user teaches you something**: Use `category: "preference"`
  or `category: "guardrail"` -- these auto-route to global scope.
- **After fixing a non-trivial bug**: Use `category: "mistake"`.

### Scope guidance

Categories auto-route scope. If not using categories:
- Use `scope: "project"` for project-specific decisions.
- Use `scope: "global"` for user preferences and identity.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_memorymesh_dir(project_root: str) -> bool:
    """Create the ``.memorymesh/`` directory in the project root if needed.

    Args:
        project_root: Absolute path to the project root directory.

    Returns:
        ``True`` if the directory was created, ``False`` if it already existed.
    """
    memorymesh_dir = os.path.join(project_root, _MEMORYMESH_DIR)
    if os.path.isdir(memorymesh_dir):
        return False
    os.makedirs(memorymesh_dir, mode=0o700, exist_ok=True)
    return True


def _configure_claude_mcp() -> str:
    """Write or update the Claude Code MCP config to include memorymesh.

    The config file is located at ``~/.claude/settings.json``.
    If the file exists, the memorymesh server entry is merged without
    destroying other server entries.

    Returns:
        A status message describing what was done.
    """
    config_dir = os.path.join(os.path.expanduser("~"), ".claude")
    config_path = os.path.join(config_dir, "settings.json")

    # Load existing config or start fresh.
    config: dict = {}
    if os.path.isfile(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            # If the file is corrupted, preserve a backup and start fresh.
            backup_path = config_path + ".bak"
            with contextlib.suppress(OSError):
                os.rename(config_path, backup_path)
            config = {}
            return (
                f"  Warning: Existing config was invalid; backed up to {backup_path}\n"
                f"  Created new config at {config_path}"
            )

    # Ensure the mcpServers key exists.
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Check if memorymesh is already configured.
    if "memorymesh" in config["mcpServers"]:
        return f"  Already configured in {config_path}"

    # Add the memorymesh server entry.
    config["mcpServers"]["memorymesh"] = _MCP_SERVER_ENTRY

    # Write the config.
    os.makedirs(config_dir, mode=0o700, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return f"  Added memorymesh server to {config_path}"


def _inject_claude_md(project_root: str) -> str:
    """Inject the memory instructions section into CLAUDE.md.

    If ``CLAUDE.md`` exists and already contains the section heading,
    nothing is changed.  If the file exists without the section, it is
    appended.  If the file does not exist, it is created with just the
    memory section.

    Args:
        project_root: Absolute path to the project root directory.

    Returns:
        A status message describing what was done.
    """
    claude_md_path = os.path.join(project_root, "CLAUDE.md")

    if os.path.isfile(claude_md_path):
        try:
            with open(claude_md_path, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            return f"  Error reading {claude_md_path}: {e}"

        # Check if the section already exists.
        if _CLAUDE_MD_SECTION_HEADING in content:
            return f"  Memory section already present in {claude_md_path}"

        # Append the section with a blank line separator.
        separator = "\n" if content.endswith("\n") else "\n\n"
        with open(claude_md_path, "a", encoding="utf-8") as f:
            f.write(separator + _CLAUDE_MD_SECTION)

        return f"  Appended memory section to {claude_md_path}"
    else:
        # Create CLAUDE.md with just the memory section.
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(_CLAUDE_MD_SECTION)

        return f"  Created {claude_md_path} with memory instructions"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_init(
    project_path: str | None = None,
    skip_mcp: bool = False,
    skip_claude_md: bool = False,
    only: str | None = None,
) -> int:
    """Run the ``memorymesh init`` command.

    Sets up MemoryMesh for the current project by creating the data
    directory, configuring the Claude Code MCP server, and injecting
    memory instructions into CLAUDE.md.  Optionally initialises other
    AI tool formats (codex, gemini) via the format adapter system.

    Args:
        project_path: Explicit project root path.  If ``None``, the project
            root is detected automatically using :func:`detect_project_root`.
        skip_mcp: If ``True``, skip Claude Code MCP configuration.
        skip_claude_md: If ``True``, skip CLAUDE.md injection.
        only: If set, only initialise this specific format adapter
            (``"claude"``, ``"codex"``, ``"gemini"``).

    Returns:
        Exit code: ``0`` for success, ``1`` for errors.
    """
    # 1. Detect project root.
    project_root: str | None
    if project_path is not None:
        project_root = os.path.realpath(project_path)
    else:
        project_root = detect_project_root()

    if project_root is None:
        print(
            "Error: Could not detect project root.\n"
            "Run this command from a directory that contains a .git directory\n"
            "or pyproject.toml, or pass --project-path explicitly.",
            file=sys.stderr,
        )
        return 1

    if not os.path.isdir(project_root):
        print(
            f"Error: Project path does not exist: {project_root}",
            file=sys.stderr,
        )
        return 1

    print(f"Initializing MemoryMesh in {project_root}")
    print()

    # If --only is specified for a non-claude format, delegate entirely.
    if only and only != "claude":
        from .formats import create_format_adapter

        adapter = create_format_adapter(only)
        messages = adapter.init_project(project_root)
        for msg in messages:
            print(f"[*] {msg}")
        print()
        print(f"Done! {adapter.display_name} is configured.")
        return 0

    # 2. Create .memorymesh/ directory.
    created = _ensure_memorymesh_dir(project_root)
    memorymesh_dir = os.path.join(project_root, _MEMORYMESH_DIR)
    if created:
        print(f"[+] Created {memorymesh_dir}/")
    else:
        print(f"[=] Directory already exists: {memorymesh_dir}/")

    # 3. Configure Claude Code MCP.
    if skip_mcp:
        print("[~] Skipped MCP configuration (--skip-mcp)")
    else:
        print("[*] Claude Code MCP configuration:")
        status = _configure_claude_mcp()
        print(status)

    # 4. Inject CLAUDE.md section.
    if skip_claude_md:
        print("[~] Skipped CLAUDE.md injection (--skip-claude-md)")
    else:
        print("[*] CLAUDE.md memory instructions:")
        status = _inject_claude_md(project_root)
        print(status)

    # 5. If no --only filter, also init other detected formats.
    if only is None:
        from .formats import get_all_adapters

        for adapter in get_all_adapters():
            if adapter.name == "claude":
                continue  # Already handled above.
            if adapter.is_installed():
                print(f"[*] {adapter.display_name}:")
                messages = adapter.init_project(project_root)
                for msg in messages:
                    print(f"  {msg}")

    print()
    print("Done! MemoryMesh is ready.")
    print("Restart Claude Code to pick up the MCP server configuration.")
    return 0
