# MemoryMesh - The SQLite of AI Memory

<!-- Badges -->
[![PyPI version](https://img.shields.io/pypi/v/memorymesh.svg)](https://pypi.org/project/memorymesh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/memorymesh.svg)](https://pypi.org/project/memorymesh/)
[![CI](https://github.com/sparkvibe-io/memorymesh/actions/workflows/ci.yml/badge.svg)](https://github.com/sparkvibe-io/memorymesh/actions/workflows/ci.yml)

**MemoryMesh** is an embeddable, zero-dependency AI memory library that gives any LLM application persistent, intelligent memory. Install it with `pip install memorymesh` and add long-term memory to your AI agents in three lines of code. It works with ANY LLM -- Claude, GPT, Gemini, Llama, Ollama, Mistral, and more. Runs everywhere Python runs (Linux, macOS, Windows). All data stays on your machine by default. No servers, no APIs, no cloud accounts required. Privacy-first by design.

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
- **SQLite-Based** -- All memory is stored in a single SQLite file. No database servers, no migrations, no infrastructure.
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
| `none` (default) | `pip install memorymesh` | Nothing | Getting started, keyword-based matching |
| `local` | `pip install memorymesh[local]` | ~500MB model download | Privacy-sensitive apps, offline use |
| `ollama` | `pip install memorymesh[ollama]` | Running Ollama instance | Local semantic search, GPU acceleration |
| `openai` | `pip install memorymesh[openai]` | OpenAI API key | Highest quality embeddings |

```python
# Use local embeddings (runs on your machine, no API calls)
memory = MemoryMesh(embedding_provider="local")

# Use Ollama (connect to local Ollama server)
memory = MemoryMesh(embedding_provider="ollama", embedding_model="nomic-embed-text")

# Use OpenAI embeddings
memory = MemoryMesh(embedding_provider="openai", openai_api_key="sk-...")

# No embeddings (pure keyword matching, zero dependencies)
memory = MemoryMesh(embedding_provider="none")
```

---

## Configuration

```python
from memorymesh import MemoryMesh

memory = MemoryMesh(
    # Storage
    db_path="~/.memorymesh/memory.db",   # Where to store the SQLite database
    namespace="default",                  # Isolate memories by namespace

    # Embeddings
    embedding_provider="local",           # "none", "local", "ollama", "openai"
    embedding_model=None,                 # Model name (provider-specific)

    # Relevance tuning
    decay_rate=0.01,                      # How fast memories fade (0 = never, 1 = fast)
    min_relevance=0.3,                    # Minimum relevance score to return results

    # Limits
    max_results=10,                       # Maximum number of results from recall()
)
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
|                 SQLite Database                       |
|              (single .db file)                       |
+-----------------------------------------------------+
```

---

## Roadmap

### v0.1 -- MVP (Current)
- Core `remember()` / `recall()` / `forget()` API
- SQLite-based persistent storage
- Pluggable embedding providers (none, local, ollama, openai)
- Time-based memory decay
- Namespace isolation
- Basic relevance scoring

### v1.0 -- Production Ready
- Episodic memory (conversation-aware recall)
- Auto-importance scoring (detect and prioritize key information)
- Encrypted storage at rest
- Memory compaction and summarization
- MCP server for AI assistant integration
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
