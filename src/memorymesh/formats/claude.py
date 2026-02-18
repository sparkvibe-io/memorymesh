"""Claude Code format adapter for MemoryMesh.

Exports to and imports from Claude Code's ``MEMORY.md`` format, using the
``[importance: X.XX]`` prefix convention and importance-tiered grouping.

This adapter is a refactoring of the original ``memorymesh.sync`` module.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from . import FormatAdapter, register_format
from ._shared import (
    group_by_category,
    group_by_topic_or_tier,
    parse_importance_prefix,
)

if TYPE_CHECKING:
    from ..memory import Memory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MEMORY_MD_LINE_LIMIT = 200
"""Maximum number of lines allowed in the generated MEMORY.md file."""


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


@register_format
class ClaudeAdapter(FormatAdapter):
    """Format adapter for Claude Code MEMORY.md files.

    Export format uses ``[importance: X.XX]`` prefixed bullets grouped
    by topic or importance tier.
    """

    @property
    def name(self) -> str:
        return "claude"

    @property
    def display_name(self) -> str:
        return "Claude Code"

    @property
    def file_names(self) -> list[str]:
        return ["MEMORY.md"]

    def detect_project_path(self, project_root: str) -> str | None:
        """Detect Claude Code's project MEMORY.md path.

        Claude Code stores project memory at::

            ~/.claude/projects/-<path-with-dashes>/memory/MEMORY.md

        Args:
            project_root: Absolute path to the project root.

        Returns:
            Absolute file path, or ``None`` if not found.
        """
        claude_projects_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects")
        if not os.path.isdir(claude_projects_dir):
            return None

        # Encode path: "/Users/foo/bar" -> "-Users-foo-bar"
        encoded_name = project_root.replace(os.sep, "-")
        if not encoded_name.startswith("-"):
            encoded_name = "-" + encoded_name

        # Try exact match.
        exact_path = os.path.join(claude_projects_dir, encoded_name, "memory", "MEMORY.md")
        if os.path.isfile(exact_path):
            return exact_path

        # Scan for partial matches.
        project_dir_name = os.path.basename(project_root)
        try:
            entries = os.listdir(claude_projects_dir)
        except OSError:
            return None

        for entry in entries:
            if entry.endswith("-" + project_dir_name):
                candidate = os.path.join(claude_projects_dir, entry, "memory", "MEMORY.md")
                if os.path.isfile(candidate):
                    return candidate

        return None

    def detect_global_path(self) -> str | None:
        """Claude Code doesn't have a global MEMORY.md."""
        return None

    def is_installed(self) -> bool:
        """Check if Claude Code is installed (``~/.claude/`` exists)."""
        return os.path.isdir(os.path.join(os.path.expanduser("~"), ".claude"))

    def export_memories(
        self,
        memories: list[Memory],
        output_path: str,
        *,
        line_limit: int | None = None,
    ) -> int:
        """Export memories to Claude Code MEMORY.md format.

        Args:
            memories: Pre-sorted list of memories.
            output_path: File path to write.
            line_limit: Maximum lines. Defaults to 200.

        Returns:
            Number of memories written.
        """
        if line_limit is None:
            line_limit = _MEMORY_MD_LINE_LIMIT

        if not memories:
            self._write_empty_file(output_path)
            return 0

        has_categories = any(m.metadata.get("category") for m in memories)
        sections = (
            group_by_category(memories) if has_categories else group_by_topic_or_tier(memories)
        )
        lines = self._build_markdown(sections)

        truncated_count = 0
        if len(lines) > line_limit:
            total_bullets = sum(1 for line in lines if line.startswith("- "))
            lines = lines[: line_limit - 2]
            kept_bullets = sum(1 for line in lines if line.startswith("- "))
            truncated_count = total_bullets - kept_bullets
            lines.append("")
            lines.append(
                f"> Truncated: {truncated_count} additional memories omitted "
                f"to stay within the {line_limit}-line limit."
            )

        content = "\n".join(lines) + "\n"
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return sum(1 for line in lines if line.startswith("- "))

    def import_memories(
        self,
        input_path: str,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Parse memories from a Claude Code MEMORY.md file.

        Args:
            input_path: File path to read.

        Returns:
            A list of ``(text, importance, metadata)`` tuples.

        Raises:
            FileNotFoundError: If *input_path* does not exist.
        """
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"MEMORY.md not found: {input_path}")

        with open(input_path, encoding="utf-8") as f:
            raw_lines = f.readlines()

        entries: list[tuple[str, float, dict[str, Any]]] = []

        for raw_line in raw_lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(">"):
                continue
            if not line.startswith("- "):
                continue

            content = line[2:].strip()
            if not content:
                continue

            text, importance = parse_importance_prefix(content)
            if text:
                entries.append((text, importance, {}))

        return entries

    def init_project(self, project_root: str) -> list[str]:
        """Initialise Claude Code for a project.

        Delegates to the existing init_cmd module for MCP config and
        CLAUDE.md injection.

        Args:
            project_root: Absolute path to the project root.

        Returns:
            A list of status messages.
        """
        from ..init_cmd import (
            _configure_claude_mcp,
            _ensure_memorymesh_dir,
            _inject_claude_md,
        )

        messages: list[str] = []

        created = _ensure_memorymesh_dir(project_root)
        mm_dir = os.path.join(project_root, ".memorymesh")
        if created:
            messages.append(f"Created {mm_dir}/")
        else:
            messages.append(f"Directory already exists: {mm_dir}/")

        messages.append(_configure_claude_mcp())
        messages.append(_inject_claude_md(project_root))

        return messages

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_empty_file(output_path: str) -> None:
        """Write an empty MEMORY.md with just the header."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        lines = [
            "# Project Memory (synced by MemoryMesh)",
            "",
            f"> Auto-generated from MemoryMesh. Last synced: {now} UTC",
            "> Do not edit manually -- changes will be overwritten on next sync.",
            "",
            "No memories stored yet.",
            "",
        ]
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    @staticmethod
    def _build_markdown(sections: dict[str, list[Memory]]) -> list[str]:
        """Build the full markdown content as a list of lines."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        lines: list[str] = [
            "# Project Memory (synced by MemoryMesh)",
            "",
            f"> Auto-generated from MemoryMesh. Last synced: {now} UTC",
            "> Do not edit manually -- changes will be overwritten on next sync.",
        ]

        for section_name, memories in sections.items():
            lines.append("")
            lines.append(f"## {section_name}")
            lines.append("")
            for mem in memories:
                text = mem.text.replace("\n", " ").strip()
                lines.append(f"- [importance: {mem.importance:.2f}] {text}")

        return lines
