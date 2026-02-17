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

Most commands accept `--scope project|global|all` to filter by store. Run `memorymesh <command> --help` for full options.

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
