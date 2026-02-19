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

## v4.0 -- Advanced

- Graph-based memory relationships
- Multi-device sync
- Plugin system for custom relevance strategies
- Streaming recall for large memory sets
