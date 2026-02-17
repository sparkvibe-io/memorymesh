# Multi-Tool Memory Sync

MemoryMesh stores all memories in SQLite. The sync feature exports them to the markdown files that each AI tool reads natively, so your knowledge follows you across tools.

```bash
# Export to Claude Code's MEMORY.md
memorymesh sync --to auto --format claude

# Export to Codex CLI's AGENTS.md
memorymesh sync --to auto --format codex

# Export to Gemini CLI's GEMINI.md
memorymesh sync --to auto --format gemini

# Export to ALL detected tools at once
memorymesh sync --to auto --format all

# Import memories FROM a markdown file back into MemoryMesh
memorymesh sync --from AGENTS.md --format codex

# List which tools are detected on your system
memorymesh formats
```

## How it works

- Each tool gets its own **format adapter** that outputs native markdown (no MemoryMesh-specific markup visible to the tool).
- Exports write only to a `## MemoryMesh Synced Memories` section, preserving any content you wrote yourself.
- Importance scores round-trip via invisible HTML comments, so re-importing preserves priority.
- Use `--to auto` to let MemoryMesh detect the correct file path for each tool.

---

[Back to README](../README.md)
