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
|   remember()     recall()     forget()     search()  |
+-----------------------------------------------------+
          |                          |
          v                          v
+-------------------+   +-------------------------+
|   Memory Store    |   |   Embedding Provider    |
|   (store.py)      |   |   (embeddings.py)       |
|                   |   |                         |
|  Semantic Memory  |   |  local / ollama /       |
|  Episodic Memory  |   |  openai / none          |
+-------------------+   +-------------------------+
          |                          |
          v                          v
+-------------------+   +-------------------------+
| Relevance Engine  |   |   Vector Similarity     |
| (relevance.py)    |   |   + Keyword Matching    |
|                   |   |   + Time Decay           |
| Score & Rank      |   +-------------------------+
+-------------------+
          |
          v
+-----------------------------------------------------+
|                 SQLite Databases                      |
|   ~/.memorymesh/global.db  (user-wide preferences)  |
|   <project>/.memorymesh/memories.db  (per-project)  |
+-----------------------------------------------------+
```

## Schema Migrations

MemoryMesh automatically manages database schema upgrades. When you upgrade to a new version, existing databases are migrated in-place without data loss the next time they are opened.

- **Fresh installs** get the latest schema directly.
- **Existing databases** are detected and upgraded incrementally.
- **Both project and global stores** migrate independently.
- **Migrations are additive-only** -- no columns or data are ever deleted.

Schema versions are tracked using SQLite's built-in `PRAGMA user_version`. You can check the current version programmatically:

```python
from memorymesh.store import MemoryStore

store = MemoryStore(path=".memorymesh/memories.db")
print(store.schema_version)  # e.g. 1
```

No manual steps are needed. Just upgrade the package and MemoryMesh handles the rest.

---

[Back to README](../README.md)
