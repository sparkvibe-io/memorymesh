# MemoryMesh Roadmap

**The SQLite of AI Memory.** Embeddable, zero-dependency, local-first.

---

## v4.1 -- Hardening (In Progress)

Fixes from the March 2026 multi-AI critique (6 reviewers, 3 AI engines). No new features — pure correctness, security, and performance.

### Critical Fixes
- [ ] Fix contradiction.py full-table scan: use `get_candidates_with_embeddings(limit=500)` instead of `get_all_with_embeddings(limit=10_000)`
- [ ] Make scope migration atomic: copy-first-then-delete in `update(scope=...)`
- [ ] Remove dashboard wildcard CORS (`Access-Control-Allow-Origin: *`)
- [ ] Replace `assert self._mesh` guards with proper if/raise in MCP server
- [ ] Fix `on_conflict` silent fallback: raise on invalid value instead of defaulting to KEEP_BOTH
- [ ] Expand SSRF blocklist: add `fe80::`, `0.0.0.0`, decimal-encoded IPs
- [ ] Add `PRAGMA busy_timeout = 5000` to SQLite connections
- [ ] Add `py.typed` PEP 561 marker

### Quick Wins
- [ ] Fix `apply_decay` docstring (claims mutates `updated_at`, doesn't)
- [ ] Add `MAX_REQUEST_BODY` to dashboard PATCH handler
- [ ] Expand secret detection regex: `sk-ant-` (Anthropic), `AIza` (Google)
- [ ] Cache MCP handler dispatch dicts (rebuilt on every message currently)

---

## v5.0 -- Performance & Scale

The #1 critique finding: **scalability is the weakest dimension (C+)**. At 5K+ memories, O(N) scans on every read/write will drive users away. Fix this before adding features.

### Database Layer
- [ ] Add `sqlite-vec` as optional ANN index (O(log N) vector search)
- [ ] Add SQLite FTS5 for keyword search (replace LIKE '%query%')
- [ ] Add `category` as a real column with index (currently buried in JSON blob)
- [ ] Add CHECK constraints: `importance BETWEEN 0.0 AND 1.0`, `decay_rate >= 0`
- [ ] Add composite covering index for `(importance DESC, updated_at DESC) WHERE embedding_blob IS NOT NULL`
- [ ] Add `created_at` index for time-range queries
- [ ] Wrap schema migrations in explicit transactions

### Batch Operations
- [ ] `remember_batch()`: single-pass embedding, single contradiction scan, single transaction
- [ ] `bulk_update_access(ids)`: eliminate N+1 pattern in recall()
- [ ] Bulk DELETE in compaction (single `WHERE id IN (...)`)

### Query Optimization
- [ ] Projection: exclude `embedding_blob` from queries that don't need it (session_start, smart_sync, list)
- [ ] Fix smart_sync shim: preserve multi-signal ranking instead of re-sorting by importance
- [ ] Separate `last_accessed_at` from `updated_at` to break recency feedback loop
- [ ] Persist decayed importance back to database

### API Improvements
- [ ] Add `backup()` / `restore()` using SQLite's online backup API
- [ ] Define `StoreProtocol` so EncryptedMemoryStore is protocol-based, not duck-typed
- [ ] Move `cosine_similarity` from store.py to utils.py
- [ ] Add NumPy-accelerated cosine when available (10-50x speedup)
- [ ] Use `clear()` + VACUUM to reclaim disk space

---

## v5.x -- Adaptive Memory

**Prerequisite:** v5.0 scale fixes proven at 10K+ memories.

- [ ] Spaced-repetition importance reinforcement (access strengthens memories)
- [ ] `prune(min_importance)` for true forgetting
- [ ] Associative memory linking (co-activated memories)
- [ ] Automatic memory consolidation/summarization
- [ ] Question frequency tracking for proactive surfacing
- [ ] Cross-session linking via metadata chains
- [ ] Multi-device sync documentation (Syncthing/rsync)

---

## Competitive Position

| Axis | MemoryMesh | Mem0 / Letta / Zep |
|---|---|---|
| Dependencies | Zero (stdlib) | Vector DBs, Docker, cloud |
| Privacy | Data never leaves machine | Cloud-first |
| Cross-tool | Claude + Codex + Gemini + Cursor | Framework-locked |
| Cost | Free forever, MIT | $0-$249/mo, VC-funded |
| MCP-native | Built-in | No MCP support |

**We do NOT compete on:** graph memory, enterprise features, managed cloud, or raw scale. We compete on: simplicity, locality, cross-tool portability, free forever.

---

## Completed

| Version | Shipped |
|---|---|
| **v4.0** | Smart Sync, configurable weights, EncryptedStore, security hardening, MCP test suite (126 tests) |
| **v3.x** | Pin support, privacy guard, contradiction detection, retrieval filters, dashboard, diagnostics |
| **v2.0** | 9 categories, auto-categorization, session_start, structured sync |
| **v1.0** | Core: episodic memory, auto-importance, encrypted storage, compaction |

Full history: [archive/vision/](archive/vision/)
