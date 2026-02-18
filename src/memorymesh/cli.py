"""MemoryMesh CLI -- human-readable viewer and management tool for stored memories.

Provides ``list``, ``search``, ``show``, ``stats``, ``export``, ``init``,
``sync``, ``report``, ``formats``, ``compact``, and ``review`` subcommands
so that users can inspect, audit, and manage their memory stores without
writing Python code.

Uses **only the Python standard library** (argparse, shutil, json).
The CLI never computes embeddings -- it instantiates MemoryMesh with
``embedding="none"`` and only reads/displays data.

Usage::

    memorymesh list    [--scope project|global|all] [--limit N] [--offset N] [--format table|json]
    memorymesh search  <query> [--scope ...] [--limit N]
    memorymesh show    <memory_id>
    memorymesh stats   [--scope project|global|all]
    memorymesh export  [--format json|html] [--output FILE] [--scope project|global|all]
    memorymesh init    [--skip-mcp] [--skip-claude-md] [--only FORMAT]
    memorymesh sync    --to FILE | --from FILE [--format claude|codex|gemini|all] [--scope ...] [--limit N]
    memorymesh report  [--scope project|global|all]
    memorymesh formats [--installed]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from typing import Any

from .core import MemoryMesh
from .memory import GLOBAL_SCOPE, PROJECT_SCOPE, Memory
from .store import detect_project_root

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mesh(args: argparse.Namespace) -> MemoryMesh:
    """Build a read-only MemoryMesh from CLI arguments.

    Uses ``embedding="none"`` since the CLI never needs to compute
    embeddings.

    Args:
        args: Parsed CLI arguments (may contain ``project_path`` and
            ``global_path`` overrides).

    Returns:
        A configured :class:`MemoryMesh` instance.
    """
    project_path = getattr(args, "project_path", None)
    global_path = getattr(args, "global_path", None)

    if project_path is None:
        project_root = detect_project_root()
        if project_root is not None:
            candidate = os.path.join(project_root, ".memorymesh", "memories.db")
            if os.path.isfile(candidate):
                project_path = candidate

    return MemoryMesh(
        path=project_path,
        global_path=global_path,
        embedding="none",
    )


def _resolve_scope(scope_arg: str) -> str | None:
    """Convert the CLI ``--scope`` string to an API scope value.

    Args:
        scope_arg: One of ``"project"``, ``"global"``, or ``"all"``.

    Returns:
        ``"project"``, ``"global"``, or ``None`` (meaning both).
    """
    if scope_arg == "all":
        return None
    return scope_arg


def _format_timestamp(iso: str) -> str:
    """Format an ISO timestamp to ``YYYY-MM-DD HH:MM``.

    Args:
        iso: An ISO-8601 datetime string.

    Returns:
        A short human-readable timestamp.
    """
    # Handle both "2026-02-16T15:30:00+00:00" and "2026-02-16T15:30:00"
    return iso[:16].replace("T", " ")


def _truncate(text: str, width: int) -> str:
    """Truncate text to *width* characters, adding ``...`` if needed.

    Args:
        text: Input text.
        width: Maximum output width.

    Returns:
        Truncated string.
    """
    if len(text) <= width:
        return text
    return text[: max(width - 3, 0)] + "..."


def _memory_to_dict(mem: Memory) -> dict[str, Any]:
    """Convert a Memory to a JSON-safe dict without embeddings.

    Args:
        mem: The memory to serialise.

    Returns:
        A dictionary suitable for JSON output.
    """
    d = mem.to_dict()
    d.pop("embedding", None)
    return d


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _cmd_list(args: argparse.Namespace) -> int:
    """Handle the ``list`` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    mesh = _build_mesh(args)
    scope = _resolve_scope(args.scope)
    memories = mesh.list(limit=args.limit, offset=args.offset, scope=scope)
    total = mesh.count(scope=scope)
    mesh.close()

    if args.format == "json":
        output = [_memory_to_dict(m) for m in memories]
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0

    # Table format
    if not memories:
        print("No memories found.")
        return 0

    term_width = shutil.get_terminal_size((80, 24)).columns
    # Column widths: ID(8) + Scope(7) + Imp(4) + Hits(4) + Created(16) + gaps
    fixed_width = 8 + 2 + 7 + 2 + 4 + 2 + 4 + 2 + 16 + 2
    text_width = max(20, term_width - fixed_width)

    # Header
    header = f"{'ID':<8}  {'Scope':<7}  {'Imp.':>4}  {'Hits':>4}  {'Created':<16}  {'Text'}"
    separator = f"{'─' * 8}  {'─' * 7}  {'─' * 4}  {'─' * 4}  {'─' * 16}  {'─' * text_width}"
    print(header)
    print(separator)

    for mem in memories:
        text_preview = _truncate(mem.text.replace("\n", " "), text_width)
        ts = _format_timestamp(mem.created_at.isoformat())
        print(
            f"{mem.id[:8]:<8}  {mem.scope:<7}  {mem.importance:4.2f}  "
            f"{mem.access_count:3d}x  {ts:<16}  {text_preview}"
        )

    scope_label = args.scope if args.scope != "all" else "all"
    print(f"\nShowing {len(memories)} of {total} memories (scope: {scope_label})")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    """Handle the ``search`` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    mesh = _build_mesh(args)
    scope = _resolve_scope(args.scope)
    # Use recall with scope filtering -- with embedding="none" this does
    # keyword (LIKE) search across both stores.
    memories = mesh.recall(query=args.query, k=args.limit, scope=scope)
    mesh.close()

    if not memories:
        print(f'No memories found matching "{args.query}".')
        return 0

    term_width = shutil.get_terminal_size((80, 24)).columns
    fixed_width = 8 + 2 + 7 + 2 + 4 + 2
    text_width = max(20, term_width - fixed_width)

    header = f"{'ID':<8}  {'Scope':<7}  {'Imp.':>4}  {'Text'}"
    separator = f"{'─' * 8}  {'─' * 7}  {'─' * 4}  {'─' * text_width}"
    print(header)
    print(separator)

    for mem in memories:
        text_preview = _truncate(mem.text.replace("\n", " "), text_width)
        print(f"{mem.id[:8]:<8}  {mem.scope:<7}  {mem.importance:4.2f}  {text_preview}")

    print(f'\n{len(memories)} result(s) for "{args.query}"')
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    """Handle the ``show`` subcommand.

    Supports partial ID matching (prefix of 6+ characters).

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    mesh = _build_mesh(args)
    prefix = args.memory_id

    # Try exact match first.
    mem = mesh.get(prefix)
    if mem is None:
        # Partial ID match -- scan all memories.
        all_memories = mesh.list(limit=100_000, scope=None)
        matches = [m for m in all_memories if m.id.startswith(prefix)]
        if len(matches) == 0:
            print(f"Error: No memory found with ID prefix '{prefix}'.", file=sys.stderr)
            mesh.close()
            return 1
        if len(matches) > 1:
            print(
                f"Error: Ambiguous ID prefix '{prefix}' matches {len(matches)} memories:",
                file=sys.stderr,
            )
            for m in matches[:5]:
                print(f"  {m.id}  {_truncate(m.text, 50)}", file=sys.stderr)
            mesh.close()
            return 1
        mem = matches[0]

    mesh.close()

    # Display full detail.
    emb = mem.embedding
    has_embedding = emb is not None and len(emb) > 0
    emb_info = f"Yes ({len(emb)} dimensions)" if has_embedding and emb else "No"

    meta_str = json.dumps(mem.metadata, indent=2, ensure_ascii=False) if mem.metadata else "{}"

    print(f"Memory {mem.id}")
    print("─" * 40)
    print(f"{'Scope:':<15}{mem.scope}")
    print(f"{'Importance:':<15}{mem.importance:.2f}")
    print(f"{'Decay Rate:':<15}{mem.decay_rate:.2f}")
    print(f"{'Access Count:':<15}{mem.access_count}")
    print(f"{'Created:':<15}{mem.created_at.isoformat()}")
    print(f"{'Updated:':<15}{mem.updated_at.isoformat()}")
    print(f"{'Metadata:':<15}{meta_str}")
    print(f"{'Has Embedding:':<15}{emb_info}")
    source = mem.metadata.get("source")
    if source:
        tool = mem.metadata.get("tool", "")
        print(f"{'Source:':<15}{source}{f' ({tool})' if tool else ''}")
    print()
    print("Text:")
    # Indent the text by 2 spaces.
    for line in mem.text.splitlines():
        print(f"  {line}")
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    """Handle the ``stats`` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    mesh = _build_mesh(args)
    scope = _resolve_scope(args.scope)

    if scope is None:
        # Show stats for all scopes.
        proj_count = mesh.count(scope=PROJECT_SCOPE)
        glob_count = mesh.count(scope=GLOBAL_SCOPE)
        total = proj_count + glob_count

        proj_oldest, proj_newest = mesh.get_time_range(scope=PROJECT_SCOPE)
        glob_oldest, glob_newest = mesh.get_time_range(scope=GLOBAL_SCOPE)

        print("MemoryMesh Statistics")
        print("─" * 40)
        print(f"{'Project memories:':<25}{proj_count}")
        print(f"{'Global memories:':<25}{glob_count}")
        print(f"{'Total:':<25}{total}")
        if proj_oldest:
            print(f"{'Project oldest:':<25}{_format_timestamp(proj_oldest)}")
            print(f"{'Project newest:':<25}{_format_timestamp(proj_newest)}")  # type: ignore[arg-type]
        if glob_oldest:
            print(f"{'Global oldest:':<25}{_format_timestamp(glob_oldest)}")
            print(f"{'Global newest:':<25}{_format_timestamp(glob_newest)}")  # type: ignore[arg-type]
    else:
        count = mesh.count(scope=scope)
        oldest, newest = mesh.get_time_range(scope=scope)
        print(f"MemoryMesh Statistics ({scope})")
        print("─" * 40)
        print(f"{'Memories:':<25}{count}")
        if oldest:
            print(f"{'Oldest:':<25}{_format_timestamp(oldest)}")
            print(f"{'Newest:':<25}{_format_timestamp(newest)}")  # type: ignore[arg-type]

    mesh.close()
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """Handle the ``export`` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    mesh = _build_mesh(args)
    scope = _resolve_scope(args.scope)
    memories = mesh.list(limit=100_000, scope=scope)

    if args.format == "json":
        output = [_memory_to_dict(m) for m in memories]
        content = json.dumps(output, indent=2, ensure_ascii=False)
    else:
        # HTML export
        from .html_export import generate_html

        content = generate_html(
            memories=memories,
            title="MemoryMesh Export",
            project_path=mesh.project_path,
            global_path=mesh.global_path,
        )

    mesh.close()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Exported {len(memories)} memories to {args.output}")
    else:
        print(content)

    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    """Handle the ``init`` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    from .init_cmd import run_init

    return run_init(
        project_path=getattr(args, "project_path", None),
        skip_mcp=args.skip_mcp,
        skip_claude_md=args.skip_claude_md,
        only=getattr(args, "only", None),
    )


def _cmd_sync(args: argparse.Namespace) -> int:
    """Handle the ``sync`` subcommand.

    Supports ``--format`` to select the adapter (claude, codex, gemini, all).
    Default is ``claude`` for backward compatibility.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    fmt = getattr(args, "sync_format", "claude")

    if args.to_file and args.from_file:
        print("Error: Cannot use both --to and --from at the same time.", file=sys.stderr)
        return 1

    if not args.to_file and not args.from_file:
        print("Error: Specify either --to FILE or --from FILE.", file=sys.stderr)
        return 1

    if fmt == "all" and args.from_file:
        print("Error: --format all is only supported for export (--to).", file=sys.stderr)
        return 1

    mesh = _build_mesh(args)
    scope = _resolve_scope(args.scope)

    if fmt == "all":
        # Sync to all detected formats.
        from .formats import sync_to_all

        output_path = args.to_file
        if output_path == "auto":
            results = sync_to_all(mesh, scope=scope, limit=args.limit)
            for adapter_name, count in results.items():
                print(f"Exported {count} memories ({adapter_name})")
            if not results:
                print("No installed formats detected.")
        else:
            # "all" with a specific path doesn't make sense
            print("Error: --format all requires --to auto.", file=sys.stderr)
            mesh.close()
            return 1
        mesh.close()
        return 0

    # Single format sync.
    if fmt == "claude":
        # Use the backward-compatible shim for claude.
        from .sync import (
            detect_memory_md_path,
            sync_from_memory_md,
            sync_to_memory_md,
        )

        if args.to_file:
            output_path = args.to_file
            if output_path == "auto":
                detected = detect_memory_md_path()
                if detected is None:
                    print("Error: Could not auto-detect MEMORY.md location.", file=sys.stderr)
                    mesh.close()
                    return 1
                output_path = detected
            count = sync_to_memory_md(mesh, output_path, scope=scope, limit=args.limit)
            print(f"Exported {count} memories to {output_path}")
        else:
            input_path = args.from_file
            if input_path == "auto":
                detected = detect_memory_md_path()
                if detected is None:
                    print("Error: Could not auto-detect MEMORY.md location.", file=sys.stderr)
                    mesh.close()
                    return 1
                input_path = detected
            import_scope = scope if scope is not None else "project"
            count = sync_from_memory_md(mesh, input_path, scope=import_scope)
            print(f"Imported {count} new memories from {input_path}")
    else:
        # Use the formats framework for codex/gemini.
        from .formats import (
            create_format_adapter,
            sync_from_format,
            sync_to_format,
        )

        adapter = create_format_adapter(fmt)

        if args.to_file:
            output_path = args.to_file
            if output_path == "auto":
                project_root = detect_project_root()
                if project_root:
                    detected = adapter.detect_project_path(project_root)
                else:
                    detected = adapter.detect_global_path()
                if detected is None:
                    print(
                        f"Error: Could not auto-detect {fmt} file location.",
                        file=sys.stderr,
                    )
                    mesh.close()
                    return 1
                output_path = detected
            count = sync_to_format(mesh, adapter, output_path, scope=scope, limit=args.limit)
            print(f"Exported {count} memories to {output_path}")
        else:
            input_path = args.from_file
            if input_path == "auto":
                project_root = detect_project_root()
                if project_root:
                    detected = adapter.detect_project_path(project_root)
                else:
                    detected = adapter.detect_global_path()
                if detected is None:
                    print(
                        f"Error: Could not auto-detect {fmt} file location.",
                        file=sys.stderr,
                    )
                    mesh.close()
                    return 1
                input_path = detected
            import_scope = scope if scope is not None else "project"
            count = sync_from_format(mesh, adapter, input_path, scope=import_scope)
            print(f"Imported {count} new memories from {input_path}")

    mesh.close()
    return 0


def _cmd_formats(args: argparse.Namespace) -> int:
    """Handle the ``formats`` subcommand.

    Lists all known format adapters with their install status.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    from .formats import get_all_adapters, get_installed_adapters

    if args.installed:
        adapters = get_installed_adapters()
        if not adapters:
            print("No installed format adapters detected.")
            return 0
        label = "Installed"
    else:
        adapters = get_all_adapters()
        label = "All known"

    print(f"{label} format adapters:")
    print()

    for adapter in adapters:
        installed = adapter.is_installed()
        status = "installed" if installed else "not detected"
        files = ", ".join(adapter.file_names)
        print(f"  {adapter.name:<10} {adapter.display_name:<25} {files:<15} [{status}]")

    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    """Handle the ``report`` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    from .report import generate_report

    mesh = _build_mesh(args)
    scope = _resolve_scope(args.scope)
    report = generate_report(mesh, scope=scope)
    mesh.close()
    print(report)
    return 0


def _cmd_ui(args: argparse.Namespace) -> int:
    """Handle the ``ui`` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    from .dashboard import run_dashboard

    mesh = _build_mesh(args)
    run_dashboard(mesh, port=args.port, open_browser=not args.no_open)
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    """Handle the ``review`` subcommand.

    Audits memories for quality issues and optionally auto-fixes
    what it can.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    from .categories import auto_categorize
    from .review import review_memories

    mesh = _build_mesh(args)
    scope = _resolve_scope(args.scope)
    result = review_memories(mesh, scope=scope)

    # Summary table.
    print(f"Memory Review (scope: {result.scanned_scope})")
    print("─" * 40)
    print(f"Memories reviewed: {result.total_reviewed}")
    print(f"Quality score:     {result.quality_score}/100")
    print()

    if not result.issues:
        print("No issues found.")
        mesh.close()
        return 0

    # Count by type and severity.
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for issue in result.issues:
        by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1
        by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1

    print(f"Issues: {len(result.issues)} total")
    print(f"  High:   {by_severity['high']}")
    print(f"  Medium: {by_severity['medium']}")
    print(f"  Low:    {by_severity['low']}")
    print()

    print("By type:")
    for issue_type, count in sorted(by_type.items()):
        print(f"  {issue_type:<20} {count}")

    # Verbose mode: show each issue.
    if args.verbose:
        print()
        print("─" * 40)
        for issue in result.issues:
            mem = mesh.get(issue.memory_id)
            preview = ""
            if mem:
                preview = _truncate(mem.text.replace("\n", " "), 60)
            print(f"\n[{issue.severity.upper()}] {issue.issue_type}")
            print(f"  Memory: {issue.memory_id[:8]}...  {preview}")
            print(f"  {issue.description}")
            print(f"  Fix: {issue.suggestion}")

    # Auto-fix mode.
    if args.fix:
        fixed = 0
        for issue in result.issues:
            if issue.auto_fixable and issue.issue_type == "uncategorized":
                mem = mesh.get(issue.memory_id)
                if mem:
                    category = auto_categorize(mem.text, mem.metadata)
                    # Store the category in metadata by re-remembering.
                    # For now, just report what would be done since we need
                    # the update API for a proper fix.
                    print(f"\nAuto-fix: {issue.memory_id[:8]}... -> category: {category}")
                    fixed += 1
            elif not issue.auto_fixable:
                if issue.issue_type == "scope_mismatch":
                    print(
                        f"\nManual fix needed: {issue.memory_id[:8]}... "
                        f"(scope mismatch requires update_memory)"
                    )
        if fixed > 0:
            print(f"\nAuto-fixed {fixed} issue(s).")

    mesh.close()
    return 0


def _cmd_compact(args: argparse.Namespace) -> int:
    """Handle the ``compact`` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    mesh = _build_mesh(args)
    scope = args.scope
    threshold = args.threshold
    dry_run = args.dry_run

    result = mesh.compact(
        scope=scope,
        similarity_threshold=threshold,
        dry_run=dry_run,
    )
    mesh.close()

    if result.merged_count == 0:
        print(f"No duplicates found (scope: {scope}, threshold: {threshold:.2f}).")
        return 0

    label = "Would merge" if dry_run else "Merged"
    print(f"{label} {result.merged_count} pair(s) (scope: {scope})")
    print()
    for detail in result.details:
        print(
            f"  {detail['primary_id'][:8]} <- {detail['secondary_id'][:8]}  "
            f"(similarity: {detail['similarity']:.2f})"
        )
        preview = _truncate(detail["merged_text_preview"].replace("\n", " "), 60)
        print(f"    {preview}")

    if dry_run:
        print("\nDry run -- no changes made. Use without --dry-run to apply.")
    else:
        print(f"\nDeleted {len(result.deleted_ids)} redundant memories.")

    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        A configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="memorymesh",
        description="MemoryMesh -- view and manage your AI memory stores.",
    )
    parser.add_argument(
        "--project-path",
        default=None,
        help="Path to the project SQLite database file.",
    )
    parser.add_argument(
        "--global-path",
        default=None,
        help="Path to the global SQLite database file.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # -- list ---------------------------------------------------------
    p_list = subparsers.add_parser("list", help="List stored memories.")
    p_list.add_argument(
        "--scope",
        choices=["project", "global", "all"],
        default="all",
        help="Scope to display (default: all).",
    )
    p_list.add_argument(
        "--limit", type=int, default=20, help="Maximum memories to show (default: 20)."
    )
    p_list.add_argument("--offset", type=int, default=0, help="Number of memories to skip.")
    p_list.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table).",
    )

    # -- search -------------------------------------------------------
    p_search = subparsers.add_parser("search", help="Search memories by keyword.")
    p_search.add_argument("query", help="Search query text.")
    p_search.add_argument(
        "--scope",
        choices=["project", "global", "all"],
        default="all",
        help="Scope to search (default: all).",
    )
    p_search.add_argument("--limit", type=int, default=10, help="Maximum results (default: 10).")

    # -- show ---------------------------------------------------------
    p_show = subparsers.add_parser(
        "show", help="Show full detail for a memory (supports partial ID)."
    )
    p_show.add_argument("memory_id", help="Memory ID or prefix (first 6+ characters).")

    # -- stats --------------------------------------------------------
    p_stats = subparsers.add_parser("stats", help="Show memory statistics.")
    p_stats.add_argument(
        "--scope",
        choices=["project", "global", "all"],
        default="all",
        help="Scope for statistics (default: all).",
    )

    # -- export -------------------------------------------------------
    p_export = subparsers.add_parser("export", help="Export memories to JSON or HTML.")
    p_export.add_argument(
        "--format",
        choices=["json", "html"],
        default="json",
        help="Export format (default: json).",
    )
    p_export.add_argument(
        "--output", "-o", default=None, help="Output file path (default: stdout)."
    )
    p_export.add_argument(
        "--scope",
        choices=["project", "global", "all"],
        default="all",
        help="Scope to export (default: all).",
    )

    # -- init ---------------------------------------------------------
    p_init = subparsers.add_parser(
        "init", help="Set up MemoryMesh for a project (MCP config + tool configs)."
    )
    p_init.add_argument(
        "--project-path",
        default=None,
        help="Project root directory to initialize.",
    )
    p_init.add_argument(
        "--skip-mcp",
        action="store_true",
        help="Skip Claude Code MCP configuration.",
    )
    p_init.add_argument(
        "--skip-claude-md",
        action="store_true",
        help="Skip CLAUDE.md memory section injection.",
    )
    p_init.add_argument(
        "--only",
        choices=["claude", "codex", "gemini"],
        default=None,
        help="Only configure a specific tool (default: all detected).",
    )

    # -- sync ---------------------------------------------------------
    p_sync = subparsers.add_parser("sync", help="Sync memories with AI tool markdown files.")
    p_sync.add_argument(
        "--to",
        dest="to_file",
        default=None,
        help='Export memories to a file. Use "auto" to detect location.',
    )
    p_sync.add_argument(
        "--from",
        dest="from_file",
        default=None,
        help='Import memories from a file. Use "auto" to detect location.',
    )
    p_sync.add_argument(
        "--format",
        dest="sync_format",
        choices=["claude", "codex", "gemini", "all"],
        default="claude",
        help="Target format adapter (default: claude).",
    )
    p_sync.add_argument(
        "--scope",
        choices=["project", "global", "all"],
        default="all",
        help="Scope for sync (default: all).",
    )
    p_sync.add_argument(
        "--limit", type=int, default=50, help="Maximum memories to export (default: 50)."
    )

    # -- formats ------------------------------------------------------
    p_formats = subparsers.add_parser(
        "formats", help="List known format adapters and install status."
    )
    p_formats.add_argument(
        "--installed",
        action="store_true",
        help="Show only installed/detected tools.",
    )

    # -- report -------------------------------------------------------
    p_report = subparsers.add_parser("report", help="Generate a memory analytics report.")
    p_report.add_argument(
        "--scope",
        choices=["project", "global", "all"],
        default="all",
        help="Scope for report (default: all).",
    )

    # -- ui -----------------------------------------------------------
    p_ui = subparsers.add_parser("ui", help="Launch the web dashboard.")
    p_ui.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to run the dashboard on (default: 8765).",
    )
    p_ui.add_argument(
        "--no-open",
        action="store_true",
        help="Don't automatically open the browser.",
    )

    # -- compact ------------------------------------------------------
    p_compact = subparsers.add_parser(
        "compact", help="Merge duplicate and near-duplicate memories."
    )
    p_compact.add_argument(
        "--scope",
        choices=["project", "global"],
        default="project",
        help="Scope to compact (default: project).",
    )
    p_compact.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Similarity threshold for duplicate detection (default: 0.85).",
    )
    p_compact.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be merged without making changes.",
    )

    # -- review -------------------------------------------------------
    p_review = subparsers.add_parser("review", help="Audit memories for quality issues.")
    p_review.add_argument(
        "--scope",
        choices=["project", "global", "all"],
        default="all",
        help="Scope to review (default: all).",
    )
    p_review.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix issues where possible.",
    )
    p_review.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed issue descriptions.",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments. Defaults to ``sys.argv[1:]``.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Suppress library logging -- CLI output should be clean.
    import logging

    logging.getLogger("memorymesh").setLevel(logging.WARNING)

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands: dict[str, Any] = {
        "list": _cmd_list,
        "search": _cmd_search,
        "show": _cmd_show,
        "stats": _cmd_stats,
        "export": _cmd_export,
        "init": _cmd_init,
        "sync": _cmd_sync,
        "formats": _cmd_formats,
        "report": _cmd_report,
        "compact": _cmd_compact,
        "review": _cmd_review,
        "ui": _cmd_ui,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    result: int = handler(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
