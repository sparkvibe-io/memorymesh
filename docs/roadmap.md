# Roadmap

## What MemoryMesh Is

MemoryMesh is the SQLite of AI Memory -- an embeddable, zero-dependency Python library that gives any LLM application persistent, intelligent memory. It serves two audiences:

- **AI tool users** (Claude Code, Cursor, Gemini CLI) -- MemoryMesh runs as an invisible backend, powering `.md` memory files with ranked, structured data. You install it once and forget it exists.
- **Developers building LLM apps** -- MemoryMesh is an embeddable library. Three lines of Python give your agents long-term memory backed by SQLite. No servers, no infrastructure, no vendor lock-in.

---

## What's Next: v4.0 -- Invisible Memory

The AI shouldn't need to "use" MemoryMesh. It should just work.

### Smart Sync

Export the top-N most relevant memories to `.md` files, ranked by importance and recency -- not a full dump. Directly reduces token cost by injecting only what matters into every session.

- Expose ranking weights as user-configurable: `score = w1·recency + w2·importance + w3·similarity`
- Graceful degradation: if Smart Sync is disabled or fails, fall back to current full-dump behavior

### Auto-Remember Hooks

PostToolUse and Stop hooks that capture decisions, patterns, and key facts without requiring the AI to call `remember()`. Zero-instruction persistence -- memory happens as a side effect of working.

- Noise filtering is critical: heuristic gate (length threshold, keyword density, dedup against recent memories) before storing

### Lean MCP

Consolidate the current 10 MCP tools into fewer, more powerful operations. Less schema overhead per session, lower cognitive load for the AI, same capabilities.

### Task-Aware Injection

`session_start` reads the user's first message and generates targeted context instead of a generic profile dump. The AI gets exactly the memories relevant to what it's about to do.

### Measured Overhead

Instrument real token impact per session. Track how many tokens MemoryMesh adds vs. saves. Self-optimize. Prove the value with numbers, not claims.

---

## v5.0 Vision -- Anticipatory Intelligence

- **Question learning** -- Store questions users ask, proactively surface answers in future sessions
- **Behavioral tracking** -- Learn coding styles, interaction patterns, and preferred approaches across sessions
- **Proactive anticipation** -- Use accumulated data to anticipate needs before the user asks. Start with lightweight heuristics (e.g., "user asked about X three times → surface on next session") using existing access_count data before full LLM-based anticipation
- **Multi-device sync** -- Same memory available on every machine. Phase 1: document Syncthing/rsync with `.memorymesh/` (zero code). Phase 2: optional encrypted cloud sync as opt-in
- **Cross-session continuity** -- Understand narrative arcs that flat files cannot represent

---

## Completed Milestones

| Version | Milestone |
|---|---|
| **v1.0** | Production-ready core: episodic memory, auto-importance, encrypted storage, compaction |
| **v2.0** | Personality engine: 9 memory categories, auto-categorization, session_start, structured sync |
| **v3.0** | Intelligent memory: pin support, privacy guard, contradiction detection, retrieval filters, web dashboard |
| **v3.1** | Setup & diagnostics: improved onboarding, health checks, runtime reconfiguration |
