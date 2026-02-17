# API Reference

Full Python API for the `MemoryMesh` class.

| Method | Description |
|---|---|
| `remember(text, metadata, importance, scope)` | Store a new memory (scope: `"project"` or `"global"`) |
| `recall(query, k, min_relevance, scope)` | Recall top-k relevant memories (scope: `None` for both) |
| `forget(memory_id)` | Delete a specific memory (checks both stores) |
| `forget_all(scope)` | Delete all memories in a scope (default: `"project"`) |
| `search(text, k)` | Alias for `recall()` |
| `get(memory_id)` | Retrieve a memory by ID (checks both stores) |
| `list(limit, offset, scope)` | List memories with pagination |
| `count(scope)` | Get number of memories (scope: `None` for total) |
| `get_time_range(scope)` | Get oldest/newest timestamps |
| `close()` | Close both database connections |

## Context Manager

```python
with MemoryMesh() as memory:
    memory.remember("User prefers TypeScript")
    results = memory.recall("programming language")
# Database connection is cleanly closed
```

---

[Back to README](../README.md)
