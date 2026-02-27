# MemoryMesh Roadmap

## What MemoryMesh Is

MemoryMesh is the SQLite of AI Memory -- an embeddable, zero-dependency Python library that gives any LLM application persistent, intelligent memory.

**Primary audience:** AI tool users (Claude Code, Cursor, Gemini CLI, Codex CLI). MemoryMesh runs as an invisible MCP-powered backend. You install it once, your AI remembers everything, and you never think about it again.

**Secondary audience:** Developers building LLM apps. Three lines of Python give your agents long-term memory backed by SQLite. No servers, no infrastructure, no vendor lock-in.

---

## Strategic Context (February 2026)

A 7-agent product review (architect, security, developer, designer, marketing, futurist, product analyst) surfaced a critical insight: **MemoryMesh is a well-engineered product searching for its first users.** The code is ahead of the market, not behind it.

**The window:** 12-18 months before ChatGPT, Claude, and Gemini all ship native persistent memory, commoditizing the basic use case. Our moat is what provider memory *cannot* do: cross-tool portability, local-first privacy, zero-dependency embeddability, and MCP ecosystem presence.

**The shift:** The previous roadmap assumed features were the bottleneck. They are not. Distribution is. The roadmap now reflects this.

---

## v3.2 -- Launch Ready (Now)

**Goal:** Fix critical issues, harden what exists, and get MemoryMesh in front of real users. Feature freeze -- no new capabilities until 10+ real users provide feedback.

### Security Hardening

- [ ] **Fix SQL injection in `search_filtered`** -- `store.py:534-538` interpolates metadata_filter keys into SQL. Replace character-stripping with strict allowlist regex: `^[a-zA-Z_][a-zA-Z0-9_]*$`
- [ ] **Set SQLite file permissions** -- Explicitly `os.chmod(path, 0o600)` on database files after creation. Current umask defaults may leave `global.db` world-readable.
- [ ] **Fix MCP server version** -- `mcp_server.py:61` hardcodes `"3.0.0"`. Should reference `__version__`.
- [ ] **Document encryption threat model** -- The custom crypto (HMAC-SHA256 CTR mode) is defense-in-depth, not primary security. Say so prominently. Note that embeddings are stored unencrypted.

### Test Gaps

- [ ] **Add MCP server tests** -- 1,422 lines with zero test coverage. Priority: JSON-RPC handshake, each tool call, error responses, message size limits, batch handling.
- [ ] **Add migration consistency test** -- Assert that a fresh `_FULL_SCHEMA` install and a v1 -> v2 migrated install produce identical schemas.
- [ ] **Add adversarial store tests** -- SQL injection attempts via metadata_filter, corrupt database files.

### README & Messaging Rewrite

- [ ] **Reorder README narrative** -- Lead with the pain ("AI tools start every session with amnesia"), then competitive table, then Quick Start code. Move emotional hook *before* the install command.
- [ ] **Rewrite first paragraph** -- Replace the dense wall of text with a punchy 2-liner: "Give any LLM persistent memory in 3 lines of Python. Zero dependencies. Fully local."
- [ ] **Add demo GIF** -- Terminal recording of `remember()` -> `recall()` with output using asciinema or VHS.
- [ ] **Add GitHub social preview image** -- Branded OG card for link previews on Twitter/LinkedIn/Slack.
- [ ] **Set GitHub topics** -- `ai-memory`, `llm`, `sqlite`, `mcp`, `claude`, `memory-layer`, `embeddings`, `python`, `local-first`, `privacy`.
- [ ] **Create separate MCP quick start** in the README, elevated above the Python API example.

### Documentation Polish

- [ ] **Slim getting-started.md** -- Move concepts (scopes, categories, relevance scoring) to a separate Concepts page. Getting-started should end after successful install + first example + "Next Steps."
- [ ] **Add verification step to MCP setup** -- "How do I know it worked?" section after every MCP config, referencing `memorymesh status`.
- [ ] **Elevate "Teaching Your AI"** from the bottom of mcp-server.md to a prominent callout near the top.
- [ ] **Harmonize quick start** between landing page (`MemoryMesh()`) and getting-started (`MemoryMesh(embedding="none")`). Pick one. No args is better.
- [ ] **Add estimated timelines** to docs/roadmap.md. A roadmap without dates reads as a wish list.

### Launch Distribution

- [ ] **Show HN post** -- "Show HN: MemoryMesh -- The SQLite of AI Memory (zero-dep Python library for LLM memory)". Tuesday-Thursday, 9-11am EST.
- [ ] **Reddit posts** -- r/LocalLLaMA (local-first + Ollama angle), r/ClaudeAI (MCP persistent memory), r/Python (zero-dep library).
- [ ] **Awesome list submissions** -- awesome-mcp-servers, awesome-llm, awesome-python, awesome-ai-tools.
- [ ] **MCP directory listing** -- Get listed on MCP registries and tool directories.
- [ ] **dev.to article** -- "AI Agent Memory in 2026: Why I Built MemoryMesh Instead of Using Mem0."
- [ ] **Get 10 real users** -- Offer hands-on setup. Watch them use it. Collect feedback. Let users drive the next features.

### Quick Code Fixes

- [x] **Move `logging.basicConfig()`** from module level to inside `main()`. *(shipped in v4.0.0)*
- [x] **Update Development Status classifier** -- now `4 - Beta`. *(shipped in v4.0.0)*
- [ ] **Add `--version` flag** to CLI root command.

---

## v4.0 -- Invisible Memory (Shipped v4.0.1)

**Goal:** Make MemoryMesh truly invisible. AI shouldn't need to "use" it -- it should just work.

**Status:** Shipped as v4.0.0 (core features) and v4.0.1 (mkdocs pin). Available on [PyPI](https://pypi.org/project/memorymesh/4.0.1/) and [GitHub](https://github.com/sparkvibe-io/memorymesh/releases/tag/v4.0.1).

### Smart Sync

Export the top-N most relevant memories to `.md` files, ranked by importance and recency -- not a full dump.

- Ranking formula: `score = w1*recency + w2*importance` (no similarity component -- sync has no query context)
- User-configurable weights
- Graceful degradation to full-dump on failure
- **Review finding:** This is architecturally sound. `session_start()` already does category-based collection. Low risk.

### Auto-Remember Hooks

PostToolUse and Stop hooks that capture decisions and patterns without requiring the AI to call `remember()`.

- **Critical:** Noise filtering gate *before* storing (length threshold, keyword density, dedup against recent memories)
- **Critical:** Run privacy guard *before* storing (hooks may capture API keys from tool output)
- **Critical:** Auto-captured memories get a review queue and opt-out mechanism
- **Review finding:** The hot path risk is real. Every `remember()` runs contradiction detection which does a full embedding scan. Without batching or pre-filtering, hooks add hundreds of ms per invocation.

### Lean MCP

Consolidate 10 MCP tools where usage data supports it. Do not consolidate speculatively -- let real tool usage patterns drive which tools merge.

- **Review finding:** Tool count is not the real overhead. The `session_start` response size matters more.

### Task-Aware Injection

`session_start` reads the user's first message and generates targeted context instead of a generic profile dump.

- **Review finding:** When `embedding="none"` (the MCP default), this degrades to keyword matching, which may be insufficient. Consider SQLite FTS5 as a keyword search upgrade.

### Scaling Fixes (Informed by Architecture Review)

- [ ] **Fix full-table embedding scan** -- `get_all_with_embeddings()` loads ALL memories on every `recall()`. At 5K+ memories, this is 7.5MB per query. Add SQL-level pre-filter (category, time window, importance floor) before loading embeddings.
- [ ] **Consider SQLite FTS5** for keyword search when embeddings are disabled (the MCP default config).
- [ ] **Define `StoreProtocol`** -- Make `EncryptedMemoryStore` formally implement the same interface as `MemoryStore`. Currently missing `search_filtered` and `update_fields`.
- [ ] **Fix Memory mutation during recall** -- `recall()` mutates `scope`, `importance`, and `access_count` on Memory objects in-place. Work on copies, not originals.
- [ ] **Split `mcp_server.py`** -- Extract tool handlers to `mcp_tools.py`, keep only protocol plumbing in `mcp_server.py`.
- [ ] **Add custom exception hierarchy** -- `MemoryMeshError` base with `StoreError`, `EmbeddingError`, `EncryptionError`.
- [ ] **Add embedding provider registry** -- `register_provider(name, cls)` for third-party extensibility without source modification.

### Measured Overhead

Instrument real token impact per session. Track what MemoryMesh adds vs. saves. Prove the value with data, not claims.

---

## v5.0 -- Adaptive Memory (Vision)

**Renamed from "Anticipatory Intelligence."** The review consensus: ship lightweight heuristics first, defer LLM-based anticipation. Do not overpromise.

**Prerequisite:** Active community and proven v4.0 adoption.

### Adaptive Recall (Heuristic-First)

- **Question frequency tracking** -- "User asked about X three times, surface it proactively." Uses existing `access_count` data.
- **Behavioral pattern detection** -- Learn coding styles and preferred approaches from `access_count` and `updated_at` trends.
- **Smart session_start** -- Weight recently and frequently accessed memories higher in session context.

### Multi-Device Sync (Phase 1 Only)

- **Document Syncthing/rsync** with `.memorymesh/` directory (zero code required).
- **WAL mode caveat:** Document that SQLite WAL files must not be synced separately.
- ~~Phase 2 (encrypted cloud sync)~~ -- **Deprioritized.** Slippery slope away from local-first. Revisit only if user demand is overwhelming.

### Cross-Session Continuity

- Link sessions into chains via `metadata_json` (e.g., "continued from session X").
- **Review finding:** Full narrative arc understanding requires temporal knowledge graph capabilities. Start with simple session linking, not the full vision.

### NOT in v5.0 (Explicitly Deferred)

- LLM-based proactive anticipation (contradicts zero-dependency principle)
- Encrypted cloud sync (mission creep away from local-first)
- Graph memory (competing with Mem0 on their turf with their $24M)

---

## Competitive Positioning

**MemoryMesh wins on axes that Mem0, Letta, and Zep structurally cannot match:**

| Axis | MemoryMesh | Competitors |
|---|---|---|
| Dependencies | Zero (stdlib only) | Vector DBs, Docker, cloud accounts |
| Privacy | Data cannot leave your machine | Cloud-first or server-required |
| Cross-tool | Claude + Codex + Gemini + Cursor simultaneously | Framework-locked or single-tool |
| Cost | Free forever, MIT, no tiers | $0-$249/mo, credit-based, VC-funded |
| MCP-native | Built-in MCP server | No MCP support (Mem0, Letta) |

**MemoryMesh does NOT compete on:** graph memory, enterprise features, managed cloud, or raw scale. These are Mem0's game. Don't play it.

---

## Completed Milestones

| Version | Milestone |
|---|---|
| **v1.0** | Production-ready core: episodic memory, auto-importance, encrypted storage, compaction |
| **v2.0** | Personality engine: 9 memory categories, auto-categorization, session_start, structured sync |
| **v3.0** | Intelligent memory: pin support, privacy guard, contradiction detection, retrieval filters, web dashboard |
| **v3.1** | Setup & diagnostics: improved onboarding, health checks, runtime reconfiguration |
| **v4.0** | Invisible Memory: Smart Sync, configurable weights, EncryptedStore completeness, security hardening |

Full version history: [archive/ROADMAP-v3.md](archive/ROADMAP-v3.md)
