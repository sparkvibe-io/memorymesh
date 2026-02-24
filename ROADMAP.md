# MemoryMesh Roadmap

This document tracks the full version history and upcoming plans for MemoryMesh.

---

## v0.1 -- MVP

- Core `remember()` / `recall()` / `forget()` API
- SQLite-based persistent storage
- Pluggable embedding providers (none, local, ollama, openai)
- Time-based memory decay
- Relevance scoring (semantic + recency + importance + frequency)
- MCP server for AI assistant integration (Claude Code, Cursor, Windsurf)
- Security hardening (input limits, path validation, error sanitization)
- Multi-tool memory sync (Claude, Codex, Gemini) with format adapters
- CLI viewer and management tool (`memorymesh list`, `search`, `stats`, `sync`, etc.)
- Automatic schema migrations (safe upgrades for existing databases)

## v1.0 -- Production Ready

- Episodic memory with session tracking (`session_id` on remember/recall)
- Auto-importance scoring (heuristic-based: keywords, structure, specificity)
- Encrypted storage at rest (application-level, zero external dependencies)
- Memory compaction (detect and merge similar/redundant memories)
- Comprehensive benchmarks (`make bench` -- throughput, latency, concurrency, disk usage)

## v2.0 -- Personality & Learning Engine

- Memory categories with automatic scope routing (`category="preference"` -> global)
- Auto-categorization from text heuristics (`auto_categorize=True`)
- `session_start()` method for structured context at the beginning of every AI session
- Category-aware sync produces structured MEMORY.md (User Profile, Guardrails, Decisions, etc.)
- 9 built-in categories: preference, guardrail, mistake, personality, question, decision, pattern, context, session_summary

## v3.0 -- Intelligent Memory (Current)

- Pin support for critical memories (zero decay, always top-ranked)
- Privacy guard with secret detection and optional redaction
- Contradiction detection with configurable conflict resolution
- Advanced retrieval filters (category, importance, time range, metadata)
- Web dashboard for browsing and searching memories (`memorymesh ui`)
- Evaluation suite (recall quality + adversarial robustness tests)
- Memory hygiene: `update()` API for in-place edits and scope migration, `review` system for auditing memory quality
- Subject-based scope inference: automatically routes memories to project or global scope based on text content

## v4.0 -- Invisible Memory (Direction B)

The AI shouldn't need to "use" MemoryMesh. It should just work.

- Invisible backend -- MemoryMesh powers .md files silently, no MCP tool calls required for basic operation
- Smart sync -- export top-N most relevant memories per project, not a full dump
- Auto-remember via hooks -- PostToolUse/Stop hooks persist decisions and patterns without AI cooperation
- Lean MCP -- consolidate tools, reduce schema overhead for projects that want dynamic recall
- Task-aware injection -- session_start analyzes the first message and generates targeted context
- Measured overhead -- instrument real token impact per session, self-optimize

## v5.0 -- Anticipatory Intelligence

- Question learning -- store questions users ask, proactively address similar ones in future sessions
- Behavioral learning -- track coding styles, interaction habits, preferred approaches across sessions
- Proactive anticipation -- use accumulated behavioral data to anticipate needs across all LLMs
- Multi-device sync -- same memory available on every machine
- Cross-session episodic continuity -- understand narrative arcs that flat files cannot represent
