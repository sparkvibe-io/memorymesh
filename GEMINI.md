
## MemoryMesh Synced Memories

> Synced from MemoryMesh. Last synced: 2026-02-17 01:52 UTC

### Product-Vision

- Krishna's product vision (2026-02-17): MemoryMesh should be the RAM/ROM of AI -- lives locally, persists locally, completely free. Key strategic questions raised: (1) Why SQLite not RAG? (2) Why not .md files? (3) Why structured storage for unstructured data? These questions should inform architecture decisions -- MemoryMesh should embrace unstructured text as first-class, not force structure. The .md export is the human-readable view; SQLite is the engine underneath, like how browsers store bookmarks in SQLite but display them as a list. <!-- memorymesh:importance=1.00 -->

### Architecture-Rationale

- Architecture rationale: SQLite is the engine, .md is the view. MemoryMesh IS local RAG (embed → store → vector similarity → rank), just without external vector DBs. Text is unstructured (free-form anything), metadata is structured (importance, timestamps, access counts, embeddings). sync module bridges SQLite↔.md for tool interop. Vision: RAM/ROM of AI -- lives locally, persists locally, completely free. No Pinecone/Weaviate needed at memory scale (hundreds-thousands, not millions). <!-- memorymesh:importance=1.00 -->

### Architecture

- MemoryMesh is 'The SQLite of AI Memory' -- an embeddable, zero-dependency Python library for persistent AI memory. Public API: remember(), recall(), forget(), forget_all(). Core entry point is src/memorymesh/core.py. <!-- memorymesh:importance=1.00 -->
- Hybrid dual-store architecture: project store at <project-root>/.memorymesh/memories.db for project-specific memories, global store at ~/.memorymesh/global.db for user preferences and cross-project facts. recall() searches both by default, forget_all() only clears project scope by default. <!-- memorymesh:importance=0.90 -->
- Schema migration system implemented (2026-02-16): src/memorymesh/migrations.py uses PRAGMA user_version for versioning. Three cases: fresh DB gets _FULL_SCHEMA + stamp LATEST_VERSION; pre-migration DB (table exists, user_version=0) stamps v1 then applies pending; previously migrated applies version > current. MIGRATIONS list is additive-only. store.py no longer has inline DDL -- calls ensure_schema() in __init__, exposes schema_version property. 9 tests in tests/test_migrations.py. Future migrations: add Migration(version=N, ...) to MIGRATIONS and update _FULL_SCHEMA. <!-- memorymesh:importance=0.90 -->
- Key source files: core.py (main API ~380 lines), store.py (SQLite backend ~430 lines), embeddings.py (pluggable providers ~470 lines), relevance.py (scoring engine ~240 lines), mcp_server.py (MCP JSON-RPC server ~780 lines), memory.py (Memory dataclass ~160 lines). <!-- memorymesh:importance=0.80 -->

### User_Identity

- Krishna / SparkVibe (hello@sparkvibe.io) -- wants MemoryMesh usable by ANYONE, any OS, any LLM, no API keys needed. Mission: serve humanity, reduce costs, open source everything. <!-- memorymesh:importance=1.00 -->

### Product-Strategy

- Strategic analysis: MEMORY.md's killer advantage is "always on" -- content auto-injected into every prompt. MemoryMesh's knowledge is locked behind a tool call. Key strategies to win: (1) become the backend FOR auto-memory via memorymesh sync, (2) MCP prompts/list for auto-context injection, (3) one-command setup with memorymesh init, (4) multi-LLM memory sharing as unique value prop. Don't compete with MEMORY.md -- complement and eventually replace it. <!-- memorymesh:importance=1.00 -->

### Product-Insight

- Key lesson: LLMs don't use MCP tools proactively unless explicitly instructed in the system prompt (CLAUDE.md). Tool availability alone is insufficient -- CLAUDE.md must contain mandatory instructions about when to recall and when to remember. Added a "Memory (MemoryMesh)" section to CLAUDE.md with specific triggers for recall/remember usage. <!-- memorymesh:importance=1.00 -->

### Implementation-State

- Implementation state (2026-02-17): Phase 1 complete - CLI viewer (list/search/show/stats/export), HTML export, init cmd, sync (Claude MEMORY.md), report, MCP prompts/list. 159 tests passing, 3 skipped, ruff clean. New files: cli.py, html_export.py, init_cmd.py, sync.py, report.py, docs/strategy.md. All wired into cli.py with 8 subcommands. pyproject.toml has memorymesh entry point. Next: multi-format sync (formats/ package with FormatAdapter ABC). <!-- memorymesh:importance=0.95 -->
- Multi-format sync implemented (2026-02-17): FormatAdapter ABC in src/memorymesh/formats/__init__.py with registry pattern (@register_format decorator, create_format_adapter factory). Three adapters: ClaudeAdapter (formats/claude.py, MEMORY.md with [importance:] prefix), CodexAdapter (formats/codex.py, AGENTS.md with HTML comment importance), GeminiAdapter (formats/gemini.py, GEMINI.md with HTML comment importance). sync.py is now a backward-compatible shim delegating to ClaudeAdapter. CLI: sync --format claude|codex|gemini|all, formats subcommand, init --only flag. 231 tests passing (72 new format tests). Key fix: _ensure_adapters_loaded uses _ALL_LOADED flag not registry emptiness check (sync.py imports ClaudeAdapter early). <!-- memorymesh:importance=0.95 -->

### Multi-Format-Sync-Plan

- Multi-format sync plan: FormatAdapter ABC pattern (mirrors EmbeddingProvider). New package src/memorymesh/formats/ with __init__.py (ABC, registry, factory), _shared.py (normalise, is_duplicate, grouping), claude.py (refactored from sync.py), codex.py (AGENTS.md), gemini.py (GEMINI.md). sync.py becomes backward-compatible shim. CLI gets --format flag on sync subcommand. Each adapter exports native format (no MemoryMesh markup visible to tool), uses HTML comments for importance round-trip. Section-based writing preserves user content. <!-- memorymesh:importance=0.95 -->
- Format adapter implementation details: ClaudeAdapter keeps [importance: X.XX] prefix. CodexAdapter and GeminiAdapter use clean markdown bullets with HTML comments for round-trip importance preservation. Section-based export writes only to ## MemoryMesh Synced Memories section, preserving user-authored content above/below. Auto-detection: Claude ~/.claude/ dir, Codex ~/.codex/ dir, Gemini ~/.gemini/ dir. CLI: memorymesh sync --format claude|codex|gemini|all, memorymesh init --only codex, memorymesh formats (list installed). <!-- memorymesh:importance=0.85 -->

### Release-Planning

- PyPI publishing is on the to-do list for when we go public (estimated a few days out, after implementation is complete). Package is ready to publish: pyproject.toml configured, README has absolute GitHub links for PyPI rendering. Version 0.1.0. Consider TestPyPI first to preview README rendering before committing the version number on real PyPI. <!-- memorymesh:importance=0.90 -->

### Multi-Format-Research

- AI coding agent memory format research (2026-02): All 8 major tools use Markdown. Claude Code: CLAUDE.md + ~/.claude/projects/*/memory/MEMORY.md (200-line limit). OpenAI Codex: AGENTS.md at project root + ~/.codex/AGENTS.md (32KB limit). Gemini CLI: GEMINI.md + ~/.gemini/GEMINI.md (auto-appends under ## Gemini Added Memories). GitHub Copilot: .github/copilot-instructions.md + .instructions.md with YAML frontmatter (applyTo globs), also reads AGENTS.md/CLAUDE.md/GEMINI.md cross-tool. Cursor: .cursor/rules/*.mdc with YAML frontmatter. Windsurf: .windsurf/rules/*.md (6K chars/file, 12K total). Aider: CONVENTIONS.md via .aider.conf.yml. Amazon Q: .amazonq/rules/*.md + memory-bank/ (product.md, structure.md, tech.md, guidelines.md). <!-- memorymesh:importance=0.90 -->

### Api_Surface

- Full MemoryMesh public API: remember(text, metadata, importance, decay_rate, scope) -> str, recall(query, k=5, min_relevance=0.0, scope=None) -> list[Memory], forget(memory_id) -> bool, forget_all(scope='project') -> int, count(scope=None) -> int, list(limit=10, offset=0, scope=None) -> list[Memory], search(text, k=5) -> list[Memory] (alias for recall), get(memory_id) -> Memory|None, get_time_range(scope=None) -> tuple, close() -> None. Also supports context manager (with statement). <!-- memorymesh:importance=0.90 -->

### Product_Vision

- User's goal: provide the simplest, extremely useful solution for people who use LLMs for coding, documentation, and research. MemoryMesh should be the memory layer that makes every AI conversation smarter. <!-- memorymesh:importance=0.90 -->

### User_Setup

- User has Claude Max account (no API credits). Prefers MCP server approach where Claude calls MemoryMesh as a tool -- no API keys needed. Has Ollama installed locally with nomic-embed-text model. <!-- memorymesh:importance=0.90 -->

### Mcp_Server

- MCP server entry point: memorymesh-mcp (installed at .venv/bin/memorymesh-mcp). Configured in ~/.claude.json under mcpServers. Uses env vars: MEMORYMESH_EMBEDDING, MEMORYMESH_OLLAMA_MODEL, MEMORYMESH_PATH, MEMORYMESH_GLOBAL_PATH. Server reads JSON-RPC from stdin, writes to stdout. All logging goes to stderr. <!-- memorymesh:importance=0.90 -->

### Embeddings

- Four embedding modes: 'none' (keyword-only, zero dependencies), 'ollama' (local semantic search via Ollama), 'local' (sentence-transformers), 'openai' (OpenAI API). Default in Python API is 'local', default in MCP server is 'none'. Ollama mode uses nomic-embed-text model. <!-- memorymesh:importance=0.90 -->
- Keyword-only mode ('none') matches exact words only -- 'testing' won't find 'pytest'. Ollama mode understands semantic similarity -- 'testing' finds 'pytest', 'security' finds 'JWT authentication'. For coding/research users, Ollama mode is significantly more useful. <!-- memorymesh:importance=0.80 -->

### Implementation

- Phase 1 CLI + HTML export implemented (2026-02-16). New files: cli.py (list/search/show/stats/export subcommands), html_export.py (self-contained HTML wiki with dark mode, search, scope filters). Entry point: `memorymesh` command via pyproject.toml. _detect_project_root() extracted from mcp_server.py to store.py as detect_project_root(). Tests: 126 pass, 3 skipped. 39 new tests added (21 CLI + 18 HTML export). <!-- memorymesh:importance=0.85 -->

### Recall_Pipeline

- recall() pipeline: (1) embed query via _safe_embed, (2) gather candidates from project+global stores (vector search via get_all_with_embeddings + keyword fallback via search_by_text LIKE), (3) deduplicate by memory id, (4) apply time-based decay, (5) rank by composite score (semantic+recency+importance+frequency), (6) update access_count and updated_at for returned memories. If embedding fails, gracefully falls back to keyword-only search without crashing. <!-- memorymesh:importance=0.85 -->

### Sqlite_Schema

- SQLite table schema: CREATE TABLE memories (id TEXT PRIMARY KEY, text TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', embedding_blob BLOB, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, access_count INTEGER NOT NULL DEFAULT 0, importance REAL NOT NULL DEFAULT 0.5, decay_rate REAL NOT NULL DEFAULT 0.01). Indexes: idx_memories_importance (importance DESC), idx_memories_updated_at (updated_at DESC). Uses WAL journal mode, foreign_keys=ON, per-thread connections via threading.local(). <!-- memorymesh:importance=0.85 -->

### Data_Model

- Memory dataclass fields: id (uuid4 hex), text (required, non-empty), metadata (dict, default {}), embedding (list[float]|None), created_at (UTC datetime), updated_at (UTC datetime), access_count (int, default 0), importance (float 0-1, default 0.5, clamped), decay_rate (float >=0, default 0.01), scope ('project'|'global', set dynamically by core layer, NOT persisted in DB). Has to_dict/from_dict/to_json/from_json serialization methods. <!-- memorymesh:importance=0.85 -->

### Mcp_Tools_Detail

- MCP server exposes 5 tools: remember (text, metadata?, importance?, scope?), recall (query, k?, scope?), forget (memory_id), forget_all (scope?), memory_stats (scope?). Server detects project root from: (1) MCP roots URI, (2) MEMORYMESH_PROJECT_ROOT env var, (3) CWD if it has .git or pyproject.toml. On initialize, recreates MemoryMesh with project-aware paths. Entry point: 'memorymesh-mcp' console script (pyproject.toml [project.scripts]). <!-- memorymesh:importance=0.80 -->

### Relevance_Scoring

- RelevanceWeights defaults: semantic=0.5, recency=0.2, importance=0.2, frequency=0.1. Score formula: weighted(cosine_sim_shifted_0_1, exp_recency_decay, importance, normalized_access_count) / total_weight. Recency: exp(-days_since / max_recency_days), max_recency_days=30. Frequency: min(access_count / max_access_count, 1.0), max_access_count=100. Time decay: new_importance = importance * exp(-decay_rate * days_since_update). <!-- memorymesh:importance=0.80 -->

### Development

- Development setup: Python 3.9+ required, venv at .venv/ in project root. Commands: 'make test' or 'pytest tests/', 'make lint' (ruff), 'make format', 'make typecheck' (mypy), 'make all'. 87 tests passing, 3 skipped (external deps requiring ollama/openai/sentence-transformers). <!-- memorymesh:importance=0.80 -->

### Embedding_Providers_Detail

- Embedding provider details: LocalEmbedding uses all-MiniLM-L6-v2 (384-dim), lazy-loaded. OllamaEmbedding calls /api/embed endpoint with urllib (no httpx), supports batch via input list. OpenAIEmbedding uses text-embedding-3-small (1536-dim), requires API key. NoopEmbedding returns empty list. Factory: create_embedding_provider('name', **kwargs). Aliases: 'local'/'sentence-transformers', 'ollama', 'openai', 'none'/'noop'. Security: blocks cloud metadata endpoints (169.254.169.254), warns on non-localhost HTTP. <!-- memorymesh:importance=0.75 -->

### Packaging

- Packaging: hatchling build system, pip install memorymesh (base: zero deps), pip install memorymesh[ollama] (also zero extra deps -- uses stdlib urllib!), pip install memorymesh[local] (adds sentence-transformers + torch), pip install memorymesh[openai] (adds openai>=1.0), pip install memorymesh[all] (everything), pip install memorymesh[dev] (pytest, ruff, mypy). Ruff config: target py39, line-length 100. Mypy: strict (disallow_untyped_defs). <!-- memorymesh:importance=0.70 -->

### Store_Internals

- Store search_by_text uses LIKE with proper wildcard escaping (case-insensitive substring match). get_all_with_embeddings has 10K row limit to prevent OOM. Embeddings packed as binary blobs via struct.pack('<Nf', *floats) -- 4x more space efficient than JSON. update_access increments access_count and refreshes updated_at. Directory permissions set to 0o700 for security. Path traversal prevented via os.path.realpath. <!-- memorymesh:importance=0.70 -->

### Security

- Security audit completed: 26 findings addressed. MCP server has limits: MAX_TEXT_LENGTH=100K chars, MAX_METADATA_SIZE=10K bytes, MAX_MESSAGE_SIZE=1M bytes, MAX_BATCH_SIZE=50, MAX_MEMORY_COUNT=100K. Embeddings stored as binary blobs (struct.pack float32). SQLite uses WAL mode and thread-safe connections. <!-- memorymesh:importance=0.70 -->

### Repository

- Repository: github.com/sparkvibe-io/memorymesh.git, branch: main, version: v0.1.0 MVP. Build system: hatchling. Optional deps groups: [local], [ollama], [openai], [all], [dev]. CI: GitHub Actions testing Python 3.9-3.13 on ubuntu/macos/windows. <!-- memorymesh:importance=0.70 -->

### Code_Conventions

- Code conventions: type hints on all public functions, Google-style docstrings, dataclasses over dicts, no global mutable state, MIT license, ruff for formatting, pytest for testing. All new features/fixes must include tests. <!-- memorymesh:importance=0.70 -->

### Design_Principles

- Design principles: (1) Simplicity -- obvious API, (2) Zero external dependencies for base install, (3) Framework-agnostic -- never depend on LangChain/LlamaIndex, (4) Cross-platform -- Linux/macOS/Windows, (5) Privacy-first -- no telemetry, no cloud calls unless user configures external providers. <!-- memorymesh:importance=0.70 -->

### Public_Api_Exports

- Public exports from memorymesh package (__init__.py __all__): MemoryMesh, MemoryMeshMCPServer, Memory, PROJECT_SCOPE, GLOBAL_SCOPE, validate_scope, MemoryStore, EmbeddingProvider, LocalEmbedding, OllamaEmbedding, OpenAIEmbedding, NoopEmbedding, create_embedding_provider, RelevanceEngine, RelevanceWeights, __version__. Version: '0.1.0'. <!-- memorymesh:importance=0.65 -->

### Cli

- CLI suppresses library logging by setting memorymesh logger to WARNING level at the top of main(). Without this, MemoryMesh core logs (INFO level) clutter CLI output on stderr. <!-- memorymesh:importance=0.60 -->

### Local_Setup

- No system python command on this machine -- must use .venv/bin/python or activate venv. Ollama is installed via Homebrew: 'brew services start ollama' to run. <!-- memorymesh:importance=0.60 -->
