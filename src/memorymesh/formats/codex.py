"""OpenAI Codex CLI format adapter for MemoryMesh.

Exports to and imports from Codex CLI's ``AGENTS.md`` format.  Uses clean
markdown bullets with HTML comments for round-trip importance preservation.
Writes only to a ``## MemoryMesh Synced Memories`` section so that
user-authored content is preserved.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from . import FormatAdapter, register_format
from ._shared import (
    group_by_category,
    group_by_topic_or_tier,
    importance_to_html_comment,
    inject_section,
    parse_importance_from_html_comment,
)

if TYPE_CHECKING:
    from ..memory import Memory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SECTION_HEADING = "## MemoryMesh Synced Memories"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


@register_format
class CodexAdapter(FormatAdapter):
    """Format adapter for OpenAI Codex CLI AGENTS.md files.

    Exports clean markdown bullets (no ``[importance:]`` prefix visible
    to Codex) with HTML comments for round-trip importance fidelity.
    Writes only to a ``## MemoryMesh Synced Memories`` section.
    """

    @property
    def name(self) -> str:
        return "codex"

    @property
    def display_name(self) -> str:
        return "OpenAI Codex CLI"

    @property
    def file_names(self) -> list[str]:
        return ["AGENTS.md"]

    def detect_project_path(self, project_root: str) -> str | None:
        """Detect the project AGENTS.md path.

        Args:
            project_root: Absolute path to the project root.

        Returns:
            Path to ``<project>/AGENTS.md`` if it exists, or the path
            where it would be created.
        """
        return os.path.join(project_root, "AGENTS.md")

    def detect_global_path(self) -> str | None:
        """Detect the global AGENTS.md path.

        Returns:
            Path to ``~/.codex/AGENTS.md`` if the ``~/.codex/`` directory
            exists.
        """
        codex_dir = os.path.join(os.path.expanduser("~"), ".codex")
        if os.path.isdir(codex_dir):
            return os.path.join(codex_dir, "AGENTS.md")
        return None

    def is_installed(self) -> bool:
        """Check if Codex CLI is installed (``~/.codex/`` exists)."""
        return os.path.isdir(os.path.join(os.path.expanduser("~"), ".codex"))

    def export_memories(
        self,
        memories: list[Memory],
        output_path: str,
        *,
        line_limit: int | None = None,
    ) -> int:
        """Export memories to Codex AGENTS.md format.

        Writes only to a ``## MemoryMesh Synced Memories`` section,
        preserving any existing content in the file.

        Args:
            memories: Pre-sorted list of memories.
            output_path: File path to write.
            line_limit: Maximum lines for the section. ``None`` = no limit.

        Returns:
            Number of memories written.
        """
        if not memories:
            return 0

        has_categories = any(m.metadata.get("category") for m in memories)
        sections = (
            group_by_category(memories) if has_categories else group_by_topic_or_tier(memories)
        )
        section_lines = self._build_section(sections)

        if line_limit and len(section_lines) > line_limit:
            section_lines = section_lines[:line_limit]

        section_content = "\n".join(section_lines)

        # Read existing file content if it exists.
        existing = ""
        if os.path.isfile(output_path):
            with open(output_path, encoding="utf-8") as f:
                existing = f.read()

        result = inject_section(existing, section_content)

        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)

        return sum(1 for line in section_lines if line.startswith("- "))

    def import_memories(
        self,
        input_path: str,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Parse memories from a Codex AGENTS.md file.

        Reads bullets from the ``## MemoryMesh Synced Memories`` section.
        Also reads bullets from outside that section (user-authored).

        Args:
            input_path: File path to read.

        Returns:
            A list of ``(text, importance, metadata)`` tuples.

        Raises:
            FileNotFoundError: If *input_path* does not exist.
        """
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"AGENTS.md not found: {input_path}")

        with open(input_path, encoding="utf-8") as f:
            raw_lines = f.readlines()

        entries: list[tuple[str, float, dict[str, Any]]] = []

        for raw_line in raw_lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(">"):
                continue
            if line.startswith("<!--") and line.endswith("-->"):
                continue
            if not line.startswith("- "):
                continue

            content = line[2:].strip()
            if not content:
                continue

            text, importance = parse_importance_from_html_comment(content)
            if text:
                entries.append((text, importance, {}))

        return entries

    def init_project(self, project_root: str) -> list[str]:
        """Initialise Codex CLI for a project.

        Creates or updates AGENTS.md with a MemoryMesh section.

        Args:
            project_root: Absolute path to the project root.

        Returns:
            A list of status messages.
        """
        messages: list[str] = []

        agents_path = os.path.join(project_root, "AGENTS.md")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        section = (
            f"{_SECTION_HEADING}\n"
            f"\n"
            f"> Synced from MemoryMesh. Last synced: {now} UTC\n"
            f"\n"
            f"_No memories synced yet. Run `memorymesh sync --to {agents_path} --format codex` to populate._\n"
        )

        if os.path.isfile(agents_path):
            with open(agents_path, encoding="utf-8") as f:
                existing = f.read()
            if _SECTION_HEADING in existing:
                messages.append(f"MemoryMesh section already present in {agents_path}")
                return messages
            result = inject_section(existing, section)
        else:
            result = f"# AGENTS.md\n\n{section}"

        with open(agents_path, "w", encoding="utf-8") as f:
            f.write(result)

        messages.append(f"Created/updated {agents_path} with MemoryMesh section")
        return messages

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_section(sections: dict[str, list[Memory]]) -> list[str]:
        """Build the MemoryMesh section content as lines."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        lines: list[str] = [
            _SECTION_HEADING,
            "",
            f"> Synced from MemoryMesh. Last synced: {now} UTC",
        ]

        for section_name, memories in sections.items():
            lines.append("")
            lines.append(f"### {section_name}")
            lines.append("")
            for mem in memories:
                text = mem.text.replace("\n", " ").strip()
                comment = importance_to_html_comment(mem.importance)
                lines.append(f"- {text} {comment}")

        return lines
