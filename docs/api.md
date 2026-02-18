# API Reference

Full Python API for the `MemoryMesh` class.

## Core Methods

| Method | Description |
|---|---|
| `remember(text, metadata, importance, decay_rate, scope, auto_importance, session_id, category, auto_categorize, pin, redact, on_conflict)` | Store a new memory |
| `recall(query, k, min_relevance, scope, session_id, category, min_importance, time_range, metadata_filter)` | Recall top-k relevant memories |
| `forget(memory_id)` | Delete a specific memory (checks both stores) |
| `forget_all(scope)` | Delete all memories in a scope (default: `"project"`) |
| `search(text, k)` | Alias for `recall()` |
| `get(memory_id)` | Retrieve a memory by ID (checks both stores) |
| `list(limit, offset, scope)` | List memories with pagination |
| `count(scope)` | Get number of memories (scope: `None` for total) |
| `get_time_range(scope)` | Get oldest/newest timestamps |
| `close()` | Close both database connections |

## Episodic Memory Methods

| Method | Description |
|---|---|
| `get_session(session_id)` | Retrieve all memories for a conversation session |
| `list_sessions()` | List all sessions with counts and timestamps |

## Session & Context Methods

| Method | Description |
|---|---|
| `session_start(project_context)` | Retrieve structured context for a new AI session |

## Compaction Methods

| Method | Description |
|---|---|
| `compact(scope, similarity_threshold, dry_run)` | Detect and merge similar memories |

## Update Methods

| Method | Description |
|---|---|
| `update(memory_id, text, importance, decay_rate, metadata, scope)` | Update an existing memory in-place. Supports scope migration. |

## Review Methods

| Method | Description |
|---|---|
| `review_memories(mesh, scope, detectors, project_name)` | Audit memories for quality issues (returns ReviewResult) |

## Constructor

```python
MemoryMesh(
    path=None,                    # Project database path (None = global-only)
    global_path=None,             # Global database path (default: ~/.memorymesh/global.db)
    embedding="local",            # "none", "local", "ollama", "openai"
    encryption_key=None,          # Passphrase for at-rest encryption (optional)
    relevance_weights=None,       # RelevanceWeights instance (optional)
    **kwargs,                     # Embedding provider options
)
```

## remember()

```python
memory.remember(
    text="User prefers dark mode",   # Required: the content to store
    metadata={"source": "chat"},     # Optional: key-value metadata
    importance=0.5,                  # Optional: importance score 0.0-1.0
    decay_rate=0.01,                 # Optional: how fast importance fades
    scope=None,                      # Optional: "project", "global", or None (auto-infer)
    auto_importance=False,           # Optional: auto-score importance from text
    session_id=None,                 # Optional: group into a conversation session
    category=None,                   # Optional: "preference", "guardrail", "mistake", etc.
    auto_categorize=False,           # Optional: auto-detect category from text
    pin=False,                       # Optional: pin memory (importance=1.0, never decays)
    redact=False,                    # Optional: redact detected secrets before storing
    on_conflict="keep_both",         # Optional: "keep_both", "update", or "skip"
)
```

When `auto_importance=True`, the `importance` parameter is ignored and MemoryMesh scores it automatically based on text analysis.

When `category` is set, the `scope` is automatically determined (e.g. `"preference"` -> global, `"decision"` -> project). When `auto_categorize=True`, category is detected from text heuristics and `auto_importance` is also enabled.

When `pin=True`, importance is set to `1.0` and decay rate to `0.0`, ensuring the memory never fades.

When `redact=True`, detected secrets (API keys, tokens, passwords) are replaced with `[REDACTED]` before storage.

The `on_conflict` parameter controls contradiction handling: `"keep_both"` (default) stores both and flags the contradiction, `"update"` replaces the most similar existing memory, `"skip"` discards the new memory if a contradiction is found (returns empty string).

When `scope` is `None` (default), MemoryMesh automatically infers the scope from the text content. Text about the user (preferences, habits, workflow) routes to global; text about the project (file paths, versions, implementations) routes to project. Set `scope` explicitly to override.

**Valid categories:**

| Category | Scope | Description |
|---|---|---|
| `preference` | global | User coding style, tool preferences |
| `guardrail` | global | Rules AI must follow |
| `mistake` | global | Past mistakes to avoid |
| `personality` | global | User character traits |
| `question` | global | Recurring questions/concerns |
| `decision` | project | Architecture/design decisions |
| `pattern` | project | Code patterns and conventions |
| `context` | project | Project-specific facts |
| `session_summary` | project | Auto-generated session summaries |

## update()

```python
memory.update(
    memory_id="abc123",              # Required: ID of memory to update
    text="Updated text",             # Optional: new text (re-embeds if changed)
    importance=0.8,                  # Optional: new importance score
    decay_rate=0.0,                  # Optional: new decay rate
    metadata={"category": "decision"},  # Optional: new metadata
    scope="global",                  # Optional: migrate to different scope
)
```

When `scope` is provided, the memory is moved from its current store to the new scope's store (cross-scope migration). Only the fields you pass are changed -- omitted fields retain their current values.

## recall()

```python
results = memory.recall(
    query="What theme?",             # Required: natural-language query
    k=5,                             # Optional: max results to return
    min_relevance=0.0,               # Optional: minimum relevance threshold
    scope=None,                      # Optional: "project", "global", or None (both)
    session_id=None,                 # Optional: boost memories from this session
    category=None,                   # Optional: filter by category (e.g. "decision")
    min_importance=None,             # Optional: minimum importance threshold
    time_range=None,                 # Optional: (start_iso, end_iso) filter
    metadata_filter=None,            # Optional: dict of key-value pairs to match
)
```

When `session_id` is provided, memories from the same session receive a relevance boost in ranking.

When `category`, `min_importance`, `time_range`, or `metadata_filter` are set, the candidate set is pre-filtered before ranking. This is more efficient than post-filtering, especially for large memory stores.

## Privacy Guard

```python
from memorymesh.privacy import check_for_secrets, redact_secrets

# Check for potential secrets
secrets = check_for_secrets("API key: sk-abc123456789")
# ["API key"]

# Redact secrets
clean = redact_secrets("token: sk-abc123456789")
# "token: [REDACTED]"
```

## Contradiction Detection

```python
from memorymesh.contradiction import find_contradictions, ConflictMode

# Find memories that may contradict new text
contradictions = find_contradictions(text, embedding, store, threshold=0.75)
# Returns: [(memory, similarity_score), ...]

# ConflictMode enum
ConflictMode.KEEP_BOTH   # Store both, flag contradiction
ConflictMode.UPDATE       # Replace most similar existing memory
ConflictMode.SKIP         # Discard new memory if contradiction found
```

## compact()

```python
result = memory.compact(
    scope="project",                 # Optional: scope to compact
    similarity_threshold=0.85,       # Optional: Jaccard similarity threshold
    dry_run=False,                   # Optional: preview without deleting
)

print(result.merged_count)           # Number of merges performed
print(result.deleted_ids)            # IDs of memories that were merged away
print(result.kept_ids)               # IDs of memories that absorbed merges
```

## session_start()

```python
context = memory.session_start(
    project_context="working on auth module",  # Optional: helps find relevant project memories
)

# Returns a structured dict:
# {
#     "user_profile": ["Senior Python developer", "Prefers dark mode"],
#     "guardrails": ["Never auto-commit without asking"],
#     "common_mistakes": ["Forgot to run tests before pushing"],
#     "common_questions": ["Always asks about test coverage"],
#     "project_context": ["Uses SQLite for storage", "Google-style docstrings"],
#     "last_session": ["Implemented auth module, 15 tests added"],
# }
```

## Context Manager

```python
with MemoryMesh() as memory:
    memory.remember("User prefers TypeScript")
    results = memory.recall("programming language")
# Database connection is cleanly closed
```

## Episodic Memory

```python
# Store memories with a session ID
memory.remember("User asked about auth", session_id="session-001")
memory.remember("Decided to use JWT", session_id="session-001")

# Retrieve all memories from a session
session_memories = memory.get_session("session-001")

# List all sessions
sessions = memory.list_sessions()
# [{"session_id": "session-001", "count": 2, "first_at": "...", "last_at": "..."}]

# Boost same-session memories during recall
results = memory.recall("authentication", session_id="session-001")
```

---

[Back to Home](index.md)
