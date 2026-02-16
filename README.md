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

## Roadmap

### v0.1 -- MVP (Current)
- Core `remember()` / `recall()` / `forget()` API
- SQLite-based persistent storage
- Pluggable embedding providers (none, local, ollama, openai)
- Time-based memory decay
- Relevance scoring (semantic + recency + importance + frequency)
- MCP server for AI assistant integration (Claude Code, Cursor, Windsurf)
- Security hardening (input limits, path validation, error sanitization)

### v1.0 -- Production Ready
- Episodic memory (conversation-aware recall)
- Auto-importance scoring (detect and prioritize key information)
- Encrypted storage at rest
- Memory compaction and summarization
- Comprehensive benchmarks

### v2.0 -- Advanced
- Graph-based memory relationships
- Multi-device sync
- Memory import/export
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
