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

## Category-Aware Sync (v2.0)

When memories have categories (set via `category` parameter or `auto_categorize=True`), the sync output is automatically organized into structured sections:

```markdown
## User Profile
- [importance: 0.95] Senior Python developer, prefers concise explanations

## Guardrails
- [importance: 1.00] Never auto-commit without asking

## Decisions
- [importance: 0.90] Chose SQLite over PostgreSQL for simplicity

## Project Context
- [importance: 0.85] Main entry point is src/core.py
```

Memories without categories continue to use the existing topic/importance-tier grouping. The structured format makes MEMORY.md more useful as an always-on system prompt -- the AI can quickly find guardrails, understand the user, and recall project context.

---

[Back to README](../README.md)
