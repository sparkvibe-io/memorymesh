"""Bidirectional sync between MemoryMesh and Claude Code MEMORY.md files.

This module is a **backward-compatible shim** that delegates to
:class:`memorymesh.formats.claude.ClaudeAdapter`.  All original public
functions (``sync_to_memory_md``, ``sync_from_memory_md``,
``detect_memory_md_path``) retain their exact signatures and behaviour.

For multi-format sync, use :mod:`memorymesh.formats` directly.

Uses **only the Python standard library** -- no external dependencies.

Usage::

    from memorymesh import MemoryMesh
    from memorymesh.sync import sync_to_memory_md, sync_from_memory_md

    mesh = MemoryMesh(path="project.db")
    exported = sync_to_memory_md(mesh, "MEMORY.md")
    imported = sync_from_memory_md(mesh, "MEMORY.md")
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from .formats.claude import ClaudeAdapter

if TYPE_CHECKING:
    from .core import MemoryMesh

logger = logging.getLogger(__name__)

# Singleton adapter instance for the shim functions.
_claude_adapter = ClaudeAdapter()


# ---------------------------------------------------------------------------
# Export: MemoryMesh -> MEMORY.md
# ---------------------------------------------------------------------------


def sync_to_memory_md(
    mesh: MemoryMesh,
    output_path: str | os.PathLike[str],
    scope: str | None = None,
    limit: int = 50,
) -> int:
    """Export MemoryMesh memories to a MEMORY.md-compatible markdown file.

    This is a backward-compatible wrapper around
    :func:`memorymesh.formats.sync_to_format` with the Claude adapter.

    Args:
        mesh: A configured :class:`MemoryMesh` instance.
        output_path: File path to write the markdown output.
        scope: ``"project"``, ``"global"``, or ``None`` (default) to
            export from both stores.
        limit: Maximum number of memories to export.  Defaults to 50.

    Returns:
        The number of memories exported.
    """
    # Fetch memories and delegate to the adapter directly to handle
    # the empty-store case (writes a "no memories" placeholder).
    memories = mesh.list(limit=limit, scope=scope)
    if not memories:
        _claude_adapter.export_memories([], str(output_path))
        return 0

    memories.sort(key=lambda m: m.importance, reverse=True)
    return _claude_adapter.export_memories(memories, str(output_path))


# ---------------------------------------------------------------------------
# Import: MEMORY.md -> MemoryMesh
# ---------------------------------------------------------------------------


def sync_from_memory_md(
    mesh: MemoryMesh,
    input_path: str | os.PathLike[str],
    scope: str = "project",
) -> int:
    """Import a MEMORY.md file into MemoryMesh.

    This is a backward-compatible wrapper around
    :func:`memorymesh.formats.sync_from_format` with the Claude adapter.

    Args:
        mesh: A configured :class:`MemoryMesh` instance.
        input_path: Path to the MEMORY.md file to import.
        scope: ``"project"`` (default) or ``"global"``.

    Returns:
        The number of new memories imported.

    Raises:
        FileNotFoundError: If *input_path* does not exist.
    """
    # Use the adapter to parse, then import with the legacy source name
    # for backward compatibility (old code used "memory.md" not "claude").
    entries = _claude_adapter.import_memories(str(input_path))
    if not entries:
        return 0

    from .formats._shared import is_duplicate

    imported = 0
    for text, importance, _metadata in entries:
        existing = mesh.recall(query=text, k=5, scope=scope)
        if is_duplicate(text, existing):
            continue

        mesh.remember(
            text=text,
            metadata={"source": "memory.md", "imported": True},
            importance=importance,
            scope=scope,
        )
        imported += 1

    return imported


# ---------------------------------------------------------------------------
# Auto-detection of MEMORY.md location
# ---------------------------------------------------------------------------


def detect_memory_md_path() -> str | None:
    """Auto-detect the MEMORY.md location used by Claude Code.

    Claude Code stores project memory at::

        ~/.claude/projects/-<path-with-dashes>/memory/MEMORY.md

    where the directory name is the absolute project path with ``/``
    replaced by ``-``.

    Returns:
        Absolute path to MEMORY.md, or ``None`` if not found.
    """
    from .store import detect_project_root

    project_root = detect_project_root()
    if project_root is None:
        logger.debug("No project root detected; cannot locate MEMORY.md")
        return None

    return _claude_adapter.detect_project_path(project_root)
