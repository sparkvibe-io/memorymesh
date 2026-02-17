"""Multi-format sync adapters for MemoryMesh.

Provides the :class:`FormatAdapter` ABC, a registry of known formats,
factory functions, and high-level sync helpers.

Architecture mirrors the :mod:`memorymesh.embeddings` provider pattern:
each adapter class is registered via :func:`register_format` and can be
instantiated by name via :func:`create_format_adapter`.

Uses **only the Python standard library** -- no external dependencies.

Usage::

    from memorymesh.formats import create_format_adapter, sync_to_format

    adapter = create_format_adapter("codex")
    sync_to_format(mesh, adapter, "/path/to/AGENTS.md", scope="project")
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ._shared import is_duplicate

if TYPE_CHECKING:
    from ..core import MemoryMesh
    from ..memory import Memory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FormatAdapter ABC
# ---------------------------------------------------------------------------


class FormatAdapter(ABC):
    """Abstract base class for format adapters.

    Each adapter knows how to export MemoryMesh memories to, and import
    from, a specific AI tool's markdown format.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short machine-readable name, e.g. ``"claude"``, ``"codex"``."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g. ``"Claude Code"``, ``"OpenAI Codex CLI"``."""

    @property
    @abstractmethod
    def file_names(self) -> list[str]:
        """Expected file names for this format, e.g. ``["AGENTS.md"]``."""

    @abstractmethod
    def detect_project_path(self, project_root: str) -> str | None:
        """Detect the project-scoped file path for this format.

        Args:
            project_root: Absolute path to the project root.

        Returns:
            Absolute file path, or ``None`` if not found/applicable.
        """

    @abstractmethod
    def detect_global_path(self) -> str | None:
        """Detect the global file path for this format.

        Returns:
            Absolute file path, or ``None`` if not found/applicable.
        """

    @abstractmethod
    def is_installed(self) -> bool:
        """Check whether the corresponding tool appears to be installed.

        Returns:
            ``True`` if configuration directories or files are found.
        """

    @abstractmethod
    def export_memories(
        self,
        memories: list[Memory],
        output_path: str,
        *,
        line_limit: int | None = None,
    ) -> int:
        """Export memories to the format's markdown file.

        Args:
            memories: Pre-sorted list of memories (highest importance first).
            output_path: File path to write.
            line_limit: Maximum lines for the output. ``None`` means no limit.

        Returns:
            Number of memories written.
        """

    @abstractmethod
    def import_memories(
        self,
        input_path: str,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Parse memories from the format's markdown file.

        Does NOT write to MemoryMesh -- returns raw data for the caller
        to handle deduplication and scope routing.

        Args:
            input_path: File path to read.

        Returns:
            A list of ``(text, importance, metadata)`` tuples.

        Raises:
            FileNotFoundError: If *input_path* does not exist.
        """

    @abstractmethod
    def init_project(self, project_root: str) -> list[str]:
        """Initialise this format for a project.

        May create files, inject configuration sections, etc.

        Args:
            project_root: Absolute path to the project root.

        Returns:
            A list of status messages describing what was done.
        """


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[FormatAdapter]] = {}
_ALL_LOADED = False


def register_format(cls: type[FormatAdapter]) -> type[FormatAdapter]:
    """Class decorator to register a format adapter.

    Usage::

        @register_format
        class MyAdapter(FormatAdapter):
            ...

    Args:
        cls: The adapter class to register.

    Returns:
        The class unchanged (for use as a decorator).
    """
    # Instantiate temporarily to read the name property.
    # All adapters should be lightweight to construct.
    instance = cls()
    adapter_name: str = instance.name
    _REGISTRY[adapter_name] = cls
    return cls


def create_format_adapter(name: str) -> FormatAdapter:
    """Create a format adapter by name.

    Args:
        name: The adapter name (e.g. ``"claude"``, ``"codex"``, ``"gemini"``).

    Returns:
        A new adapter instance.

    Raises:
        ValueError: If the name is not registered.
    """
    _ensure_adapters_loaded()
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Unknown format {name!r}. Available: {available}"
        )
    return _REGISTRY[name]()


def get_all_adapters() -> list[FormatAdapter]:
    """Return instances of all registered format adapters.

    Returns:
        A list of adapter instances, sorted by name.
    """
    _ensure_adapters_loaded()
    return [cls() for cls in sorted(_REGISTRY.values(), key=lambda c: c.__name__)]


def get_installed_adapters() -> list[FormatAdapter]:
    """Return instances of adapters whose tools are detected on the system.

    Returns:
        A list of adapter instances where :meth:`is_installed` is ``True``.
    """
    return [a for a in get_all_adapters() if a.is_installed()]


def get_format_names() -> list[str]:
    """Return all registered format names.

    Returns:
        Sorted list of format name strings.
    """
    _ensure_adapters_loaded()
    return sorted(_REGISTRY.keys())


def _ensure_adapters_loaded() -> None:
    """Lazy-import all adapter modules to populate the registry."""
    global _ALL_LOADED
    if _ALL_LOADED:
        return
    _ALL_LOADED = True
    # Import adapter modules so their @register_format decorators run.
    from . import claude as _claude  # noqa: F401
    from . import codex as _codex  # noqa: F401
    from . import gemini as _gemini  # noqa: F401


# ---------------------------------------------------------------------------
# High-level sync functions
# ---------------------------------------------------------------------------


def sync_to_format(
    mesh: MemoryMesh,
    adapter: FormatAdapter,
    output_path: str,
    *,
    scope: str | None = None,
    limit: int = 50,
    line_limit: int | None = None,
) -> int:
    """Export MemoryMesh memories using a specific format adapter.

    Args:
        mesh: A configured :class:`MemoryMesh` instance.
        adapter: The format adapter to use.
        output_path: File path to write.
        scope: ``"project"``, ``"global"``, or ``None`` for both.
        limit: Maximum number of memories to export.
        line_limit: Maximum lines for the output file.

    Returns:
        Number of memories exported.
    """
    memories = mesh.list(limit=limit, scope=scope)
    if not memories:
        return 0

    memories.sort(key=lambda m: m.importance, reverse=True)
    return adapter.export_memories(memories, output_path, line_limit=line_limit)


def sync_from_format(
    mesh: MemoryMesh,
    adapter: FormatAdapter,
    input_path: str,
    *,
    scope: str = "project",
) -> int:
    """Import memories from a format-specific file into MemoryMesh.

    Handles deduplication and scope routing.

    Args:
        mesh: A configured :class:`MemoryMesh` instance.
        adapter: The format adapter to use.
        input_path: File path to read.
        scope: Target scope for imported memories.

    Returns:
        Number of new memories imported.
    """
    entries = adapter.import_memories(input_path)
    if not entries:
        return 0

    imported = 0
    for text, importance, metadata in entries:
        existing = mesh.recall(query=text, k=5, scope=scope)
        if is_duplicate(text, existing):
            logger.debug("Skipping duplicate: %.60s...", text)
            continue

        # Merge adapter-supplied metadata with source tracking.
        meta = {"source": adapter.name, "imported": True}
        meta.update(metadata)

        mesh.remember(
            text=text,
            metadata=meta,
            importance=importance,
            scope=scope,
        )
        imported += 1

    logger.info(
        "Imported %d memories from %s (adapter=%s, scope=%s)",
        imported,
        input_path,
        adapter.name,
        scope,
    )
    return imported


def sync_to_all(
    mesh: MemoryMesh,
    *,
    scope: str | None = None,
    limit: int = 50,
    project_root: str | None = None,
) -> dict[str, int]:
    """Sync memories to all detected/installed format adapters.

    For each installed adapter, attempts to auto-detect the output path
    and exports memories there.

    Args:
        mesh: A configured :class:`MemoryMesh` instance.
        scope: ``"project"``, ``"global"``, or ``None`` for both.
        limit: Maximum number of memories per export.
        project_root: Project root for path detection. If ``None``,
            auto-detected.

    Returns:
        A dict mapping adapter names to export counts.
    """
    if project_root is None:
        from ..store import detect_project_root

        project_root = detect_project_root()

    results: dict[str, int] = {}

    for adapter in get_installed_adapters():
        # Try project path first, then global.
        output_path: str | None = None
        if project_root:
            output_path = adapter.detect_project_path(project_root)
        if output_path is None:
            output_path = adapter.detect_global_path()

        if output_path is None:
            logger.debug(
                "No output path found for %s, skipping", adapter.name
            )
            continue

        count = sync_to_format(
            mesh, adapter, output_path, scope=scope, limit=limit
        )
        results[adapter.name] = count

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "FormatAdapter",
    "register_format",
    "create_format_adapter",
    "get_all_adapters",
    "get_installed_adapters",
    "get_format_names",
    "sync_to_format",
    "sync_from_format",
    "sync_to_all",
]
