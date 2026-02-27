# Roadmap

## What MemoryMesh Is

MemoryMesh is the SQLite of AI Memory -- an embeddable, zero-dependency Python library that gives any LLM application persistent, intelligent memory.

**Primary audience:** AI tool users (Claude Code, Cursor, Gemini CLI, Codex CLI). Install once, your AI remembers everything.

**Secondary audience:** Developers building LLM apps. Three lines of Python. No servers, no infrastructure, no vendor lock-in.

---

## v3.2 -- Launch Ready (Q1 2026)

Security hardening, test coverage, and distribution. Feature freeze until real user feedback is collected.

- Security fixes (metadata filter validation, file permissions, encryption documentation)
- MCP server test coverage
- README and messaging rewrite (pain-first narrative, demo GIF, separate MCP quick start)
- Documentation polish (slimmer getting-started, MCP verification step)
- Show HN launch, Reddit, awesome list submissions, MCP directory listing

---

## v4.0 -- Invisible Memory (Shipped v4.0.1)

The AI shouldn't need to "use" MemoryMesh. It should just work. **Status:** shipped on [PyPI](https://pypi.org/project/memorymesh/4.0.1/) and [GitHub](https://github.com/sparkvibe-io/memorymesh/releases/tag/v4.0.1).

### Smart Sync
Export the top-N most relevant memories to `.md` files, ranked by importance and recency -- not a full dump. Directly reduces token cost by injecting only what matters into every session.

- User-configurable ranking weights
- Graceful degradation to current full-dump behavior

### Auto-Remember Hooks
PostToolUse and Stop hooks that capture decisions, patterns, and key facts without requiring the AI to call `remember()`. Zero-instruction persistence -- memory happens as a side effect of working.

- Noise filtering gate before storing (length, keyword density, dedup)
- Privacy guard runs before capture (hooks may see API keys in tool output)

### Lean MCP
Consolidate MCP tools where real usage data supports it. Less schema overhead per session, same capabilities.

### Task-Aware Injection
`session_start` reads the user's first message and generates targeted context instead of a generic profile dump.

### Scaling & Architecture
- Fix full-table embedding scan (SQL-level pre-filter before loading vectors)
- SQLite FTS5 for keyword search when embeddings are disabled
- Split MCP server monolith into protocol + tools modules
- Custom exception hierarchy

### Measured Overhead
Instrument real token impact per session. Prove the value with data, not claims.

---

## v5.0 -- Adaptive Memory (2027)

Lightweight heuristics first. LLM-based anticipation deferred.

- **Question frequency tracking** -- Surface answers proactively when a topic recurs
- **Behavioral patterns** -- Learn coding styles and preferred approaches from access data
- **Multi-device sync** -- Document Syncthing/rsync with `.memorymesh/` (zero code)
- **Cross-session linking** -- Connect related sessions into chains

---

## Completed Milestones

| Version | Milestone |
|---|---|
| **v1.0** | Production-ready core: episodic memory, auto-importance, encrypted storage, compaction |
| **v2.0** | Personality engine: 9 memory categories, auto-categorization, session_start, structured sync |
| **v3.0** | Intelligent memory: pin support, privacy guard, contradiction detection, retrieval filters, web dashboard |
| **v3.1** | Setup & diagnostics: improved onboarding, health checks, runtime reconfiguration |
| **v4.0** | Invisible Memory: Smart Sync, configurable weights, EncryptedStore completeness, security hardening |
