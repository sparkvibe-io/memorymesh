# Roadmap

## v5.0 -- Performance & Scale

Scalability improvements for 5K+ memories.

- sqlite-vec ANN vector indexing
- FTS5 keyword search
- `remember_batch()` for bulk inserts
- Category as real column with composite covering index and CHECK constraints
- Persist decay to DB, separate `last_accessed_at` from `updated_at`
- `backup()`/`restore()` API
- `StoreProtocol` abstract interface
- NumPy-accelerated cosine similarity

---

## v5.x -- Adaptive Memory

Spaced-repetition learning, automatic memory consolidation, cross-session linking, multi-device sync.

---

## Completed

| Version | Milestone |
|---|---|
| **v4.3** | Performance: bulk access updates, light listing (skip embeddings), recency feedback loop fix |
| **v4.1** | Hardening: contradiction scan optimization, CORS/SSRF security, atomic scope migration, PEP 561 |
| **v4.0** | Invisible Memory: Smart Sync, configurable weights, EncryptedStore, security hardening |
| **v3.x** | Intelligent memory: pin support, privacy guard, contradiction detection, retrieval filters, dashboard |
| **v2.0** | Personality engine: 9 categories, auto-categorization, session_start, structured sync |
| **v1.0** | Production-ready core: episodic memory, auto-importance, encrypted storage, compaction |
