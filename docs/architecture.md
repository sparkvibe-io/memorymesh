# Architecture

System design overview for MemoryMesh.

```
+-----------------------------------------------------+
|                   Your Application                   |
+-----------------------------------------------------+
                          |
                          v
+-----------------------------------------------------+
|               MemoryMesh Core (core.py)              |
|   remember()     recall()     forget()     compact() |
+-----------------------------------------------------+
     |              |              |              |
     v              v              v              v
+-----------+ +-----------+ +-----------+ +-----------+
|  Memory   | | Embedding | | Relevance | |Compaction |
|  Store    | | Provider  | |  Engine   | |  Engine   |
| store.py  | |embeddings | |relevance  | |compaction |
|           | |  .py      | |  .py      | |  .py      |
+-----------+ +-----------+ +-----------+ +-----------+
     |              |
     v              v
+-----------+ +-----------+
|Encryption | |  Auto-    |
| (optional)| | Importance|
|encryption | |auto_import|
|  .py      | | ance.py   |
+-----------+ +-----------+
     |
     v
+-----------------------------------------------------+
|                 SQLite Databases                      |
|   ~/.memorymesh/global.db  (user-wide preferences)  |
|   <project>/.memorymesh/memories.db  (per-project)  |
+-----------------------------------------------------+
```

## Understanding Scopes

```
~/.memorymesh/global.db          <project>/.memorymesh/memories.db
┌─────────────────────┐          ┌─────────────────────┐
│    GLOBAL STORE      │          │   PROJECT STORE      │
│                      │          │                      │
│  preferences         │          │  decisions           │
│  guardrails          │          │  patterns            │
│  mistakes            │          │  context             │
│  personality         │          │  session summaries   │
│  questions           │          │                      │
└─────────────────────┘          └─────────────────────┘
         │                                  │
         └────────── recall() ──────────────┘
                  searches both
```

- **Global store** (`~/.memorymesh/global.db`) -- user-wide preferences, guardrails, mistakes, personality, and recurring questions. Shared across all projects.
- **Project store** (`<project>/.memorymesh/memories.db`) -- architecture decisions, code patterns, project context, and session summaries. Isolated per project.

`recall()` merges results from both stores by default. `forget_all()` clears only the project store unless you explicitly pass `scope="global"`.

## Memory Lifecycle

1. **remember()** -- Text is embedded (if an embedding provider is configured), optionally scanned for secrets, checked for contradictions, and stored in the appropriate SQLite database.
2. **recall()** -- The query is embedded, then both vector similarity search and keyword fallback are used to find candidates. Results are ranked by a composite score of semantic similarity, recency, importance, and access frequency.
3. **forget()** -- Deletes a specific memory by ID from whichever store contains it.
4. **Time decay** -- Each memory has an importance score and a decay rate. Over time, `new_importance = importance * exp(-decay_rate * days_since_update)`. Pinned memories have `decay_rate=0` and never fade. Frequently accessed memories stay relevant because recall updates the `updated_at` timestamp.

## Key Modules

| Module | Purpose |
|---|---|
| `core.py` | Public API: `remember()`, `recall()`, `forget()`, `compact()`, session methods |
| `store.py` | SQLite storage layer with per-thread connections |
| `embeddings.py` | Pluggable embedding providers (local, ollama, openai, none) |
| `relevance.py` | Scoring engine: semantic similarity + recency + importance + frequency |
| `compaction.py` | Detect and merge similar/redundant memories |
| `auto_importance.py` | Heuristic-based importance scoring from text analysis |
| `encryption.py` | Application-level at-rest encryption for text and metadata |
| `memory.py` | `Memory` dataclass with session_id, serialization helpers |
| `migrations.py` | Schema versioning via `PRAGMA user_version` |

## Schema Migrations

MemoryMesh automatically manages database schema upgrades. When you upgrade to a new version, existing databases are migrated in-place without data loss the next time they are opened.

- **Fresh installs** get the latest schema directly.
- **Existing databases** are detected and upgraded incrementally.
- **Both project and global stores** migrate independently.
- **Migrations are additive-only** -- no columns or data are ever deleted.

### Migration History

| Version | Description |
|---|---|
| v1 | Initial schema (memories table, importance and updated_at indexes) |
| v2 | Add `session_id` column and index for episodic memory |

Schema versions are tracked using SQLite's built-in `PRAGMA user_version`. You can check the current version programmatically:

```python
from memorymesh.store import MemoryStore

store = MemoryStore(path=".memorymesh/memories.db")
print(store.schema_version)  # e.g. 2
```

No manual steps are needed. Just upgrade the package and MemoryMesh handles the rest.

## Memory Data Model

Each memory stores the following fields:

| Field | Type | Description |
|---|---|---|
| `id` | TEXT | Unique identifier (UUID hex) |
| `text` | TEXT | The memory content (free-form text) |
| `metadata_json` | TEXT | JSON key-value metadata |
| `embedding_blob` | BLOB | Vector embedding (binary packed float32) |
| `session_id` | TEXT | Optional conversation session identifier |
| `created_at` | TEXT | ISO-8601 creation timestamp |
| `updated_at` | TEXT | ISO-8601 last-access timestamp |
| `access_count` | INTEGER | Number of times recalled |
| `importance` | REAL | Importance score 0.0-1.0 |
| `decay_rate` | REAL | Rate of importance decay over time |

When encryption is enabled, `text` and `metadata_json` are encrypted before storage.

---

[Back to Home](index.md)
