# CLI Reference

The `memorymesh` CLI lets you inspect, manage, and sync your memory stores from the terminal.

| Command | Description |
|---|---|
| `memorymesh list` | List stored memories (table or JSON) |
| `memorymesh search <query>` | Search memories by keyword |
| `memorymesh show <id>` | Show full detail for a memory (supports partial IDs) |
| `memorymesh stats` | Show memory count, oldest/newest timestamps |
| `memorymesh export` | Export memories to JSON or HTML |
| `memorymesh compact` | Detect and merge similar/redundant memories |
| `memorymesh init` | Set up MemoryMesh for a project (MCP config + tool configs) |
| `memorymesh sync` | Sync memories to/from AI tool markdown files |
| `memorymesh formats` | List known format adapters and install status |
| `memorymesh report` | Generate a memory analytics report |
| `memorymesh review` | Audit memories for quality issues |

Most commands accept `--scope project|global|all` to filter by store. Run `memorymesh <command> --help` for full options.

## `memorymesh ui`

Launch a web-based dashboard for viewing and managing memories.

```bash
memorymesh ui [--port PORT] [--no-open]
```

Options:

| Option | Default | Description |
|---|---|---|
| `--port PORT` | `8765` | Port to run the web server on |
| `--no-open` | | Do not automatically open the browser |

The dashboard provides a searchable, filterable view of all memories across both project and global stores. It runs entirely locally -- no data leaves your machine.

## `memorymesh review`

Audit memories for quality issues and get an overall health score.

```bash
memorymesh review [--scope project|global|all] [--fix] [--verbose]
```

Options:

| Option | Default | Description |
|---|---|---|
| `--scope SCOPE` | `all` | Which scope to audit |
| `--fix` | | Auto-fix what it can (add categories to uncategorized memories) |
| `--verbose` | | Show each issue with memory preview and suggestion |

The review system detects 6 types of issues:

| Issue | Severity | Description |
|---|---|---|
| `scope_mismatch` | High | Memory in wrong scope (e.g. product name in global) |
| `too_verbose` | Medium | Text exceeds length limits (200 chars global, 500 project) |
| `near_duplicate` | Medium | Similar to another memory (>70% text similarity) |
| `uncategorized` | Low | Missing category metadata |
| `stale` | Low | Not accessed in 30+ days with low importance |
| `low_quality` | Low | Low auto-importance score (<0.4) |

Quality score formula: `100 - (high * 10 + medium * 5 + low * 2)`, clamped to 0-100.

## Compaction

The `compact` command detects and merges similar or redundant memories:

```bash
# Preview what would be merged (dry run)
memorymesh compact --dry-run

# Merge duplicates in the project store
memorymesh compact --scope project

# Set a custom similarity threshold (default: 0.85)
memorymesh compact --threshold 0.9

# Compact the global store
memorymesh compact --scope global
```

Compaction uses Jaccard word-set similarity to find near-duplicate memories. When two memories are similar above the threshold, they are merged: the higher-importance memory is kept, access counts are summed, and metadata is combined.

---

[Back to Home](index.md)
