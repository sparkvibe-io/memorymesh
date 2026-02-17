# CLI Reference

The `memorymesh` CLI lets you inspect, manage, and sync your memory stores from the terminal.

| Command | Description |
|---|---|
| `memorymesh list` | List stored memories (table or JSON) |
| `memorymesh search <query>` | Search memories by keyword |
| `memorymesh show <id>` | Show full detail for a memory (supports partial IDs) |
| `memorymesh stats` | Show memory count, oldest/newest timestamps |
| `memorymesh export` | Export memories to JSON or HTML |
| `memorymesh init` | Set up MemoryMesh for a project (MCP config + tool configs) |
| `memorymesh sync` | Sync memories to/from AI tool markdown files |
| `memorymesh formats` | List known format adapters and install status |
| `memorymesh report` | Generate a memory analytics report |

Most commands accept `--scope project|global|all` to filter by store. Run `memorymesh <command> --help` for full options.

---

[Back to README](../README.md)
