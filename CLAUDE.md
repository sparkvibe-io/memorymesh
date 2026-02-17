# CLAUDE.md - Guidance for Claude Code

## Repository Purpose

MemoryMesh is an open-source, embeddable AI memory library. It provides persistent, intelligent memory for any LLM application using SQLite as the storage backend. The design philosophy mirrors SQLite itself: simple, reliable, zero-dependency, and embeddable.

## Key Entry Points

- `src/memorymesh/core.py` -- The main `MemoryMesh` class. This is the primary public API and the starting point for understanding the codebase.
- `src/memorymesh/store.py` -- SQLite storage layer. Handles all database operations, schema management, and memory persistence.
- `src/memorymesh/embeddings.py` -- Pluggable embedding providers. Abstracts over local (sentence-transformers), Ollama, OpenAI, and keyword-based matching.
- `src/memorymesh/relevance.py` -- Relevance scoring engine. Combines vector similarity, keyword overlap, and time-based decay to rank memories.
- `src/memorymesh/mcp_server.py` -- MCP (Model Context Protocol) server. Exposes memory tools over stdin/stdout JSON-RPC for use with Claude Code, Cursor, and other MCP-compatible clients.
- `src/memorymesh/memory.py` -- The `Memory` dataclass. Defines the core data model used throughout the library.

## Architecture

```
core.py (public API: remember / recall / forget)
  -> store.py (SQLite read/write, schema migrations)
     - project store: <project-root>/.memorymesh/memories.db
     - global store:  ~/.memorymesh/global.db
  -> embeddings.py (pluggable: local, ollama, openai, none)
  -> relevance.py (scoring: similarity + keywords + time decay)
```

MemoryMesh uses a **hybrid dual-store** pattern:

- **Project store** (`<project-root>/.memorymesh/memories.db`) -- project-specific memories, decisions, and patterns. Isolated per project.
- **Global store** (`~/.memorymesh/global.db`) -- user preferences, identity, and cross-project facts. Shared across all projects.

`recall()` queries both stores by default and merges results. `forget_all()` defaults to clearing only the project store (global is protected). The `scope` parameter (`"project"` or `"global"`) controls routing throughout the API.

No external services are required for the base installation.

## Development

### Testing
```bash
make test          # Run full test suite with pytest
pytest tests/      # Run tests directly
pytest tests/ -x   # Stop on first failure
```

### Building
```bash
make build         # Build distribution packages
```

### Linting and Formatting
```bash
make lint          # Run ruff linter
make format        # Auto-format with ruff
make typecheck     # Run mypy type checking
```

### Full Check
```bash
make all           # Run lint + test + typecheck
```

## Design Principles

1. **Simplicity** -- The public API should be obvious. `remember()`, `recall()`, `forget()`. Minimize cognitive overhead.
2. **Zero External Dependencies** -- The base install has no dependencies beyond the Python standard library. All third-party packages (sentence-transformers, openai, httpx) are optional extras.
3. **Framework-Agnostic** -- MemoryMesh must never depend on or assume any specific LLM framework (LangChain, LlamaIndex, etc.). It is a library, not a framework.
4. **Cross-Platform** -- Must work on Linux, macOS, and Windows without platform-specific code paths where possible.
5. **Privacy-First** -- No telemetry, no phone-home, no cloud calls unless the user explicitly configures an external embedding provider.

## Memory (MemoryMesh)

MemoryMesh is configured as an MCP tool in this project. You MUST use it proactively -- it is the project's own product and dogfooding it is essential.

### When to `recall`

- **Start of every conversation**: Call `recall` with a summary of the user's request to check for relevant prior context, decisions, patterns, or past mistakes.
- **Before making architectural decisions**: Recall to check if this was decided before.
- **When debugging**: Recall to check if this problem or error was encountered previously.
- **When unsure about conventions**: Recall to check if there's a stored preference or pattern.

### When to `remember`

- **After completing a task**: Store key decisions, patterns discovered, and architectural choices made.
- **When the user teaches you something**: Immediately remember it (scope: global for preferences, project for project-specific facts).
- **After fixing a non-trivial bug**: Remember the root cause and fix so it's not repeated.
- **When discovering undocumented patterns**: Store conventions found in the codebase.
- **After a multi-step investigation**: Remember the conclusion so future sessions don't repeat the work.

### What to remember

- Architectural decisions and their rationale
- Bug fixes, root causes, and solutions that took multiple attempts
- User preferences confirmed during work
- File patterns and conventions discovered
- Implementation approaches that worked (or didn't)
- Test strategies and edge cases found

### What NOT to remember

- Trivial single-use facts (e.g., "ran tests, they passed")
- Information already written in this CLAUDE.md file
- Temporary state or in-progress work details
- Verbatim code snippets (store the insight, not the code)

### Scope guidance

- Use `scope: "project"` for project-specific decisions, architecture, and patterns.
- Use `scope: "global"` for user preferences, identity, and cross-project facts.

### Priority

- **Prefer MemoryMesh over auto-memory files** for persistent knowledge storage. MemoryMesh is the product we are building -- using it validates the product and builds a useful knowledge base.

## Code Conventions

- **Type hints** are required on all public functions and methods.
- **Docstrings** are required on all public classes, methods, and functions. Use Google-style docstrings.
- **Dataclasses** are preferred over plain dicts for structured data.
- **No global mutable state.** All state lives in class instances.
- **License:** MIT. All source files should be compatible with this license.
- **Formatting:** Enforced by ruff. Run `make format` before committing.
- **Testing:** All new features and bug fixes must include tests. Use pytest.
