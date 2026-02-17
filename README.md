# MemoryMesh - The SQLite of AI Memory

<!-- Badges -->
[![PyPI version](https://img.shields.io/pypi/v/memorymesh.svg)](https://pypi.org/project/memorymesh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/memorymesh.svg)](https://pypi.org/project/memorymesh/)
[![CI](https://github.com/sparkvibe-io/memorymesh/actions/workflows/ci.yml/badge.svg)](https://github.com/sparkvibe-io/memorymesh/actions/workflows/ci.yml)

**MemoryMesh** is an embeddable AI memory library with zero required dependencies that gives any LLM application persistent, intelligent memory. Install it with `pip install memorymesh` and add long-term memory to your AI agents in three lines of code. It works with ANY LLM -- Claude, GPT, Gemini, Llama, Ollama, Mistral, and more. Runs everywhere Python runs (Linux, macOS, Windows). All data stays on your machine by default. No servers, no APIs, no cloud accounts required. Privacy-first by design.

---

## Why MemoryMesh?

Every AI application needs memory, but existing solutions come with heavy trade-offs:

| Solution | Approach | Trade-off |
|---|---|---|
| **Mem0** | SaaS / managed service | Requires cloud account, data leaves your machine, ongoing costs |
| **Letta / MemGPT** | Full agent framework | Heavy framework lock-in, complex setup, opinionated architecture |
| **Zep** | Memory server | Requires PostgreSQL, Docker, server infrastructure |
| **MemoryMesh** | **Embeddable library** | **Zero dependencies. Just SQLite. Works anywhere.** |

MemoryMesh takes a fundamentally different approach. Like SQLite revolutionized embedded databases, MemoryMesh brings the same philosophy to AI memory: a simple, reliable, embeddable library that just works. No infrastructure. No lock-in. No surprises.

---

## Quick Start

```python
from memorymesh import MemoryMesh

memory = MemoryMesh()
memory.remember("User prefers Python and dark mode")
results = memory.recall("What does the user prefer?")
```

That is it. Three lines to give your AI application persistent, semantic memory.

---

## How MemoryMesh Saves You Money

Without memory, every AI interaction requires re-sending the full conversation history. As conversations grow, so do your token costs -- linearly, every single turn.

**MemoryMesh flips this model.** Instead of sending thousands of tokens of raw conversation history, you recall only the top-k most relevant memories (typically 3-5 short passages) and inject them as context. The conversation itself stays short.

### Token cost comparison: 20-turn conversation

| Turn | Without Memory (full history) | With MemoryMesh (recall top-5) |
|------|-------------------------------|-------------------------------|
| 1    | ~250 tokens                   | ~250 tokens                   |
| 5    | ~1,500 tokens                 | ~400 tokens                   |
| 10   | ~4,000 tokens                 | ~400 tokens                   |
| 20   | ~10,000 tokens                | ~450 tokens                   |
| 50   | ~30,000 tokens                | ~500 tokens                   |

*Estimates based on typical conversational turns of ~250 tokens each, with MemoryMesh recalling 5 relevant memories (~50 tokens each) per turn.*

### How it works

1. **Store** -- After each interaction, `remember()` the key facts (not the full conversation).
2. **Recall** -- Before the next interaction, `recall()` retrieves only the most relevant memories ranked by semantic similarity, recency, and importance.
3. **Inject** -- Pass the recalled memories as system context to your LLM. The full conversation history is never needed.

**The result:** Your input token count stays roughly constant regardless of how long the conversation has been going. At $3/million input tokens (Claude Sonnet pricing), a 50-turn conversation costs ~$0.09 without memory vs. ~$0.0015 with MemoryMesh -- a **60x reduction**.

This is not just a cost saving. It also means your application stays within context window limits, responds faster (fewer tokens to process), and retrieves only what is actually relevant instead of forcing the LLM to sift through thousands of tokens of conversational noise.

---

## Installation

```bash
# Base installation (no external dependencies, uses built-in keyword matching)
pip install memorymesh

# With local embeddings (sentence-transformers, runs entirely on your machine)
pip install memorymesh[local]

# With Ollama embeddings (connect to a local Ollama instance)
pip install memorymesh[ollama]

# With OpenAI embeddings
pip install memorymesh[openai]

# Everything
pip install memorymesh[all]
```

---

## Features

- **Simple API** -- `remember()`, `recall()`, `forget()`. That is the core interface. No boilerplate, no configuration ceremony.
- **SQLite-Based** -- All memory is stored in SQLite files. No database servers, no migrations, no infrastructure.
- **Framework-Agnostic** -- Works with any LLM, any framework, any architecture. Use it with LangChain, LlamaIndex, raw API calls, or your own custom setup.
- **Pluggable Embeddings** -- Choose the embedding provider that fits your needs: local models, Ollama, OpenAI, or plain keyword matching with zero dependencies.
- **Time-Based Decay** -- Memories naturally fade over time, just like human memory. Recent and frequently accessed memories are ranked higher.
- **Privacy-First** -- All data stays on your machine by default. No telemetry, no cloud calls, no data collection. You own your data.
- **Cross-Platform** -- Runs on Linux, macOS, and Windows. Anywhere Python runs, MemoryMesh runs.
- **MCP Support** -- Expose memory as an MCP (Model Context Protocol) server for seamless integration with AI assistants.
- **Multi-Tool Sync** -- Sync memories to Claude Code, OpenAI Codex CLI, and Google Gemini CLI simultaneously. Your knowledge follows you across tools.
- **CLI** -- Inspect, search, export, and manage memories from the terminal. No Python code required.

---

## Works with Any LLM

MemoryMesh is not tied to any specific LLM provider. It works as a memory layer alongside whatever model you use:

```python
from memorymesh import MemoryMesh

memory = MemoryMesh()

# Store memories from any source
memory.remember("User is a senior Python developer")
memory.remember("User is building a healthcare startup")
memory.remember("User prefers concise explanations")

# Recall relevant context before calling ANY LLM
context = memory.recall("What do I know about this user?")

# Use with Claude
response = claude_client.messages.create(
    model="claude-sonnet-4-20250514",
    system=f"User context: {context}",
    messages=[{"role": "user", "content": "Help me design an API"}],
)

# Or GPT
response = openai_client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": f"User context: {context}"},
        {"role": "user", "content": "Help me design an API"},
    ],
)

# Or Ollama, Gemini, Mistral, Llama, or literally anything else
```

---

## Embedding Providers

MemoryMesh supports multiple embedding backends. Choose the one that fits your constraints:

| Provider | Install | Requires | Best For |
|---|---|---|---|
| `none` | `pip install memorymesh` | Nothing | Getting started, keyword-based matching |
| `local` (default) | `pip install memorymesh[local]` | ~500MB model download | Privacy-sensitive apps, offline use |
| `ollama` | `pip install memorymesh[ollama]` | Running Ollama instance | Local semantic search, GPU acceleration |
| `openai` | `pip install memorymesh[openai]` | OpenAI API key | Highest quality embeddings |

```python
# Use local embeddings (runs on your machine, no API calls) -- this is the default
memory = MemoryMesh(embedding="local")

# Use Ollama (connect to local Ollama server)
memory = MemoryMesh(embedding="ollama", ollama_model="nomic-embed-text")

# Use OpenAI embeddings
memory = MemoryMesh(embedding="openai", openai_api_key="sk-...")

# No embeddings (pure keyword matching, zero dependencies)
memory = MemoryMesh(embedding="none")
```

---

## Configuration

```python
from memorymesh import MemoryMesh

memory = MemoryMesh(
    # Storage (dual-store)
    path=".memorymesh/memories.db",       # Project-specific database (optional)
    global_path="~/.memorymesh/global.db", # User-wide global database

    # Embeddings
    embedding="local",                    # "none", "local", "ollama", "openai"

    # Embedding provider options (passed as **kwargs)
    # ollama_model="nomic-embed-text",    # Ollama model name
    # ollama_base_url="http://localhost:11434",
    # openai_api_key="sk-...",            # OpenAI API key
    # local_model="all-MiniLM-L6-v2",    # sentence-transformers model
    # local_device="cpu",                 # PyTorch device

    # Relevance tuning (optional)
    # relevance_weights=RelevanceWeights(
    #     semantic=0.5,
    #     recency=0.2,
    #     importance=0.2,
    #     frequency=0.1,
    # ),
)
```

---

## MCP Server (Claude Code, Cursor, Windsurf)

MemoryMesh includes a built-in MCP (Model Context Protocol) server that lets AI assistants use your memory directly as a tool. **No API keys required** for the default setup.

### Claude Code

Add to your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "memorymesh": {
      "command": "memorymesh-mcp"
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "memorymesh": {
      "command": "memorymesh-mcp"
    }
  }
}
```

### Cursor / Windsurf

Add to your MCP settings (`.cursor/mcp.json` or equivalent):

```json
{
  "mcpServers": {
    "memorymesh": {
      "command": "memorymesh-mcp"
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MEMORYMESH_PATH` | Auto-detected | Path to the project SQLite database |
| `MEMORYMESH_GLOBAL_PATH` | `~/.memorymesh/global.db` | Path to the global SQLite database |
| `MEMORYMESH_PROJECT_ROOT` | Auto-detected | Project root directory |
| `MEMORYMESH_EMBEDDING` | `none` | Embedding provider (`none`, `local`, `ollama`, `openai`) |
| `MEMORYMESH_OLLAMA_MODEL` | `nomic-embed-text` | Ollama model name |
| `OPENAI_API_KEY` | -- | Required only when using `openai` embeddings |

### Hybrid Memory Architecture

The MCP server uses a **hybrid dual-store** architecture that separates project-specific and global memories:

```
~/.memorymesh/
  global.db                    <- user preferences, identity, cross-project facts

<project-root>/.memorymesh/
  memories.db                  <- project-specific memories, decisions, patterns
```

The project root is automatically detected from MCP client roots, the `MEMORYMESH_PROJECT_ROOT` environment variable, or the current working directory (if it contains `.git` or `pyproject.toml`).

All tools accept an optional `scope` parameter (`"project"` or `"global"`):
- `remember(scope="project")` -- stores in the project database (default)
- `remember(scope="global")` -- stores in the user-wide database
- `recall()` -- searches both databases by default
- `forget_all(scope="project")` -- only clears project memories (default; global is protected)

### Available Tools

Once connected, your AI assistant gains these tools:

- **`remember`** -- Store facts, preferences, and decisions (supports `scope`)
- **`recall`** -- Search memories by natural language query (supports `scope`)
- **`forget`** -- Delete a specific memory by ID (searches both stores)
- **`forget_all`** -- Delete all memories in a scope (defaults to project)
- **`memory_stats`** -- View memory count and timestamps (supports `scope`)

No API keys are needed for the default setup. The MCP server uses keyword matching out of the box. Add an embedding provider for semantic search.

---

## Teaching Your AI to Use MemoryMesh

Installing the MCP server gives your AI assistant the *ability* to use memory. But LLMs do not use tools proactively unless you tell them to. You need to add instructions to your AI tool's configuration file explaining **when** and **how** to use MemoryMesh.

The fastest way to set everything up is:

```bash
memorymesh init
```

This auto-detects which AI tools you have installed and configures all of them. You can also target a single tool:

```bash
memorymesh init --only claude
memorymesh init --only codex
memorymesh init --only gemini
```

Below is what each tool needs and the exact text to add if you prefer to do it manually.

### Claude Code

Add a `## Memory (MemoryMesh)` section to your project's `CLAUDE.md`:

```markdown
## Memory (MemoryMesh)

MemoryMesh is configured as an MCP tool in this project. You MUST use it
proactively -- it provides persistent memory across conversations.

### When to `recall`

- **Start of every conversation**: Call `recall` with a summary of the user's
  request to check for relevant prior context.
- **Before making architectural decisions**: Check if this was decided before.
- **When debugging**: Check if this problem was encountered previously.

### When to `remember`

- **After completing a task**: Store key decisions, patterns discovered, and
  architectural choices.
- **When the user teaches you something**: Immediately remember it.
- **After fixing a non-trivial bug**: Remember the root cause and fix.
- **When discovering undocumented patterns**: Store conventions found in the
  codebase.

### Scope guidance

- Use `scope: "project"` for project-specific decisions, architecture, and
  patterns.
- Use `scope: "global"` for user preferences, identity, and cross-project
  facts.
```

### OpenAI Codex CLI

Add a `## Memory (MemoryMesh)` section to your project's `AGENTS.md`:

```markdown
## Memory (MemoryMesh)

MemoryMesh is configured as an MCP tool. Use it proactively for persistent
memory across sessions.

- At the start of every task, call `recall` with a summary of the request.
- After completing work, call `remember` to store key decisions and patterns.
- Use `scope: "project"` for project-specific facts, `scope: "global"` for
  user preferences.
```

### Google Gemini CLI

Add a `## Memory (MemoryMesh)` section to your project's `GEMINI.md`:

```markdown
## Memory (MemoryMesh)

MemoryMesh is configured as an MCP tool. Use it proactively for persistent
memory across sessions.

- At the start of every task, call `recall` with a summary of the request.
- After completing work, call `remember` to store key decisions and patterns.
- Use `scope: "project"` for project-specific facts, `scope: "global"` for
  user preferences.
```

### Generic / Other MCP-Compatible Tools

For any tool that supports MCP:

1. Add the MCP server config (see [MCP Server](#mcp-server-claude-code-cursor-windsurf) above).
2. Add instructions to the tool's system prompt or configuration file telling it to call `recall` at the start of conversations and `remember` after completing work.

---

## Multi-Tool Memory Sync

MemoryMesh stores all memories in SQLite. The sync feature exports them to the markdown files that each AI tool reads natively, so your knowledge follows you across tools.

```bash
# Export to Claude Code's MEMORY.md
memorymesh sync --to auto --format claude

# Export to Codex CLI's AGENTS.md
memorymesh sync --to auto --format codex

# Export to Gemini CLI's GEMINI.md
memorymesh sync --to auto --format gemini

# Export to ALL detected tools at once
memorymesh sync --to auto --format all

# Import memories FROM a markdown file back into MemoryMesh
memorymesh sync --from AGENTS.md --format codex

# List which tools are detected on your system
memorymesh formats
```

How it works:

- Each tool gets its own **format adapter** that outputs native markdown (no MemoryMesh-specific markup visible to the tool).
- Exports write only to a `## MemoryMesh Synced Memories` section, preserving any content you wrote yourself.
- Importance scores round-trip via invisible HTML comments, so re-importing preserves priority.
- Use `--to auto` to let MemoryMesh detect the correct file path for each tool.

---

## CLI Reference

The `memorymesh` CLI lets you inspect, manage, and sync your memory stores from the terminal.

| Command | Description |
|---|---|
| `memorymesh list` | List stored memories (table or JSON) |
| `memorymesh search <query>` | Search memories by keyword |
| `memorymesh show <id>` | Show full detail for a memory (supports partial IDs) |
| `memorymesh stats` | Show memory count, oldest/newest timestamps |
| `memorymesh export` | Export memories to JSON or HTML |
| `memorymesh init` | Set up MemoryMesh for a project (MCP config + tool configs) |
| `memorymesh sync` | Sync memories to/from AI tool markdown files |
| `memorymesh formats` | List known format adapters and install status |
| `memorymesh report` | Generate a memory analytics report |

Most commands accept `--scope project|global|all` to filter by store. Run `memorymesh <command> --help` for full options.

---

## API Reference

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

Context manager support:

```python
with MemoryMesh() as memory:
    memory.remember("User prefers TypeScript")
    results = memory.recall("programming language")
# Database connection is cleanly closed
```

---

## Architecture

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

---

## FAQ

### Why SQLite, not plain .md files?

SQLite is the engine. Markdown is the view. This is the same pattern browsers use -- they store bookmarks in SQLite but display them as a list.

Plain markdown files cannot do: vector similarity search, importance scoring, access counting, time-based decay, metadata filtering, or atomic transactions. MemoryMesh uses SQLite for all of that, and syncs a readable snapshot to `.md` files for tools that need them.

### Why not a full RAG / vector database (Pinecone, Weaviate)?

MemoryMesh already IS local RAG. It embeds text, stores vectors, computes cosine similarity, and ranks results -- all in-process, all local. For AI memory scale (hundreds to low thousands of memories), SQLite with in-process similarity is faster and simpler than a separate database server. Zero infrastructure, zero cost, zero network latency.

### Why structured storage for unstructured data?

The text is unstructured -- `remember("whatever you want")` accepts any free-form string. The metadata is structured: importance scores, timestamps, access counts, decay rates, embeddings. The structure is invisible plumbing that makes recall smart. You never see it unless you want to.

### What does "semantic search" mean?

Instead of matching exact keywords, semantic search understands meaning. Searching "How do we handle auth?" finds memories about authentication even if they never contain the word "auth." This requires an embedding provider (local, Ollama, or OpenAI). Without one, MemoryMesh falls back to keyword matching, which still works well for most use cases.

### What is the difference between standalone and with Ollama?

**Standalone** (`embedding="none"`) uses keyword matching -- fast, zero dependencies, good for most use cases. **With Ollama** (`embedding="ollama"`) you get semantic search via a local model -- better recall accuracy, still fully local, no API keys. Ollama runs on your machine just like MemoryMesh.

### Do I need an API key?

No. The base install works with zero dependencies and zero API keys. Ollama embeddings are also free and local. Only OpenAI embeddings require an API key.

### Can I use MemoryMesh with multiple AI tools at once?

Yes. MemoryMesh stores memories in SQLite and can sync to Claude Code (`MEMORY.md`), Codex CLI (`AGENTS.md`), and Gemini CLI (`GEMINI.md`) simultaneously. Run `memorymesh sync --to auto --format all` and your knowledge follows you across tools.

---

## Roadmap

### v0.1 -- MVP (Current)
- Core `remember()` / `recall()` / `forget()` API
- SQLite-based persistent storage
- Pluggable embedding providers (none, local, ollama, openai)
- Time-based memory decay
- Relevance scoring (semantic + recency + importance + frequency)
- MCP server for AI assistant integration (Claude Code, Cursor, Windsurf)
- Security hardening (input limits, path validation, error sanitization)
- Multi-tool memory sync (Claude, Codex, Gemini) with format adapters
- CLI viewer and management tool (`memorymesh list`, `search`, `stats`, `sync`, etc.)

### v1.0 -- Production Ready
- Episodic memory (conversation-aware recall)
- Auto-importance scoring (detect and prioritize key information)
- Encrypted storage at rest
- Memory compaction and summarization
- Comprehensive benchmarks

### v2.0 -- Advanced
- Graph-based memory relationships
- Multi-device sync
- Plugin system for custom relevance strategies
- Streaming recall for large memory sets

---

## Contributing

We welcome contributions from everyone. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to get started.

---

## License

MIT License. See [LICENSE](LICENSE) for the full text.

---

## Built for Humanity

MemoryMesh is part of the [SparkVibe](https://github.com/sparkvibe-io) open-source AI initiative. We believe that foundational AI tools should be free, open, and accessible to everyone -- not locked behind paywalls, cloud subscriptions, or proprietary platforms.

Our mission is to reduce the cost and complexity of building AI applications, so that developers everywhere -- whether at a startup, a research lab, a nonprofit, or learning on their own -- can build intelligent systems without barriers.

If AI is going to shape the future, the tools that power it should belong to all of us.
