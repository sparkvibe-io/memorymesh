# API Reference

Full Python API for the `MemoryMesh` class.

## Core Methods

| Method | Description |
|---|---|
| `remember(text, metadata, importance, decay_rate, scope, auto_importance, session_id)` | Store a new memory |
| `recall(query, k, min_relevance, scope, session_id)` | Recall top-k relevant memories |
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

## Compaction Methods

| Method | Description |
|---|---|
| `compact(scope, similarity_threshold, dry_run)` | Detect and merge similar memories |

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
    scope="project",                 # Optional: "project" or "global"
    auto_importance=False,           # Optional: auto-score importance from text
    session_id=None,                 # Optional: group into a conversation session
)
```

When `auto_importance=True`, the `importance` parameter is ignored and MemoryMesh scores it automatically based on text analysis.

## recall()

```python
results = memory.recall(
    query="What theme?",             # Required: natural-language query
    k=5,                             # Optional: max results to return
    min_relevance=0.0,               # Optional: minimum relevance threshold
    scope=None,                      # Optional: "project", "global", or None (both)
    session_id=None,                 # Optional: boost memories from this session
)
```

When `session_id` is provided, memories from the same session receive a relevance boost in ranking.

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

[Back to README](../README.md)
