# MemoryMesh - The SQLite of AI Memory

<!-- mcp-name: io.github.sparkvibe-io/memorymesh -->

<!-- Badges -->
[![PyPI version](https://img.shields.io/pypi/v/memorymesh.svg)](https://pypi.org/project/memorymesh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/memorymesh.svg)](https://pypi.org/project/memorymesh/)
[![CI](https://github.com/sparkvibe-io/memorymesh/actions/workflows/ci.yml/badge.svg)](https://github.com/sparkvibe-io/memorymesh/actions/workflows/ci.yml)
[![Smithery](https://smithery.ai/badge/@sparkvibe-io/memorymesh)](https://smithery.ai/servers/sparkvibe-io/memorymesh)

**Give any LLM persistent memory in 3 lines of Python. Zero dependencies. Fully local.**

---

## The Problem

AI tools start every session with amnesia. Your preferences, decisions, past mistakes -- all gone. You repeat yourself. The AI re-discovers things you already told it. Context windows reset, and weeks of accumulated knowledge vanish.

MemoryMesh fixes this. Install once, and your AI remembers everything -- across sessions, across tools, across projects.

---

## Why MemoryMesh?

| Solution | Approach | Trade-off |
|---|---|---|
| **Mem0** | SaaS / managed service | Requires cloud account, data leaves your machine, ongoing costs |
| **Letta / MemGPT** | Full agent framework | Heavy framework lock-in, complex setup, opinionated architecture |
| **Zep** | Memory server | Requires PostgreSQL, Docker, server infrastructure |
| **MemoryMesh** | **Embeddable library** | **Zero dependencies. Just SQLite. Works anywhere.** |

Like SQLite revolutionized embedded databases, MemoryMesh brings the same philosophy to AI memory: simple, reliable, embeddable. No infrastructure. No lock-in. No surprises.

---

## MCP Quick Start

### Option 1: Try instantly (no install)

Connect to the hosted MemoryMesh server -- no local installation needed:

**Via Smithery:**
```bash
npx -y @smithery/cli install @sparkvibe-io/memorymesh --client claude
```

Or browse and connect at [smithery.ai/servers/sparkvibe-io/memorymesh](https://smithery.ai/servers/sparkvibe-io/memorymesh). Supports 20+ MCP clients including Claude Code, Cursor, Windsurf, and Cline.

### Option 2: Install locally (recommended for production)

Install once, then add the config to your tool of choice:

```bash
pip install memorymesh
```

**Claude Code** (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "memorymesh": {
      "command": "memorymesh-mcp"
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "memorymesh": {
      "command": "memorymesh-mcp"
    }
  }
}
```

**Gemini CLI** (`~/.gemini/settings.json`):

```json
{
  "mcpServers": {
    "memorymesh": {
      "command": "memorymesh-mcp"
    }
  }
}
```

Your AI now has persistent memory across sessions. Preferences, decisions, and patterns survive context window resets.

---

## Python Quick Start

```python
from memorymesh import MemoryMesh

memory = MemoryMesh()
memory.remember("User prefers Python and dark mode")
results = memory.recall("What does the user prefer?")
```

That is it. Three lines to give your AI application persistent, semantic memory.

```python
# Works with any LLM -- inject recalled context into your prompts
context = memory.recall("What do I know about this user?")

# Claude
response = claude_client.messages.create(
    model="claude-sonnet-4-20250514",
    system=f"User context: {context}",
    messages=[{"role": "user", "content": "Help me design an API"}],
)

# GPT
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

## How It Works

1. **Store** -- After each interaction, `remember()` the key facts, decisions, and patterns (not the full conversation).
2. **Recall** -- At the start of the next session, `recall()` retrieves only the most relevant memories ranked by semantic similarity, recency, and importance.
3. **Persist** -- Memories live in SQLite on your machine. They survive session restarts, tool switches, and context window resets.

### The real value

- **Cross-session persistence** -- Decisions made Monday are still known Friday.
- **Cross-tool memory** -- What you teach Claude stays available in Gemini, Codex, and Cursor.
- **Structured recall** -- Categories, importance scoring, time decay, and semantic search instead of brute-force history replay.
- **Privacy** -- Everything local. No cloud, no telemetry, no data leaves your machine.

---

## Installation

```bash
# Base installation (no external dependencies, uses built-in keyword matching)
pip install memorymesh

# With local embeddings (sentence-transformers, runs entirely on your machine)
pip install "memorymesh[local]"

# With Ollama embeddings (connect to a local Ollama instance)
pip install "memorymesh[ollama]"

# With OpenAI embeddings
pip install "memorymesh[openai]"

# Everything
pip install "memorymesh[all]"
```

---

## Features

- **Simple API** -- `remember()`, `recall()`, `forget()`. That is the core interface. No boilerplate, no configuration ceremony.
- **SQLite-Based** -- All memory stored in SQLite files. No database servers, no infrastructure. Automatic schema migrations.
- **Framework-Agnostic** -- Works with any LLM, any framework, any architecture. Use it with LangChain, LlamaIndex, raw API calls, or your own setup.
- **Pluggable Embeddings** -- Choose from local models, Ollama, OpenAI, or plain keyword matching with zero dependencies.
- **MCP Support** -- Built-in MCP server for seamless integration with Claude Code, Cursor, Gemini CLI, and other MCP-compatible tools.
- **Memory Categories** -- Automatic categorization with scope routing. Preferences go global; decisions stay in the project. MemoryMesh decides where memories belong.
- **Encrypted Storage** -- Optionally encrypt memory text and metadata at rest with zero external dependencies.
- **Privacy-First** -- All data stays on your machine. No telemetry, no cloud calls, no data collection. You own your data.
- **Auto-Compaction** -- Transparent deduplication that runs automatically during normal use. Like SQLite's auto-vacuum, you never need to think about it.
- **Cross-Platform** -- Runs on Linux, macOS, and Windows. Anywhere Python runs, MemoryMesh runs.

---

## What's New in v4

- **Smart Sync** -- Export the top-N most relevant memories to `.md` files, ranked by importance and recency. No more full dumps -- only what matters.
- **Configurable Relevance Weights** -- Tune recency, importance, and similarity weights via environment variables or constructor parameters.
- **EncryptedStore Completeness** -- `EncryptedMemoryStore` now supports `search_filtered` and `update_fields`, matching the full `MemoryStore` interface.
- **Security Hardening** -- SQL injection fix in `search_filtered` (strict allowlist for metadata keys) and explicit file permissions on database files.

---

## Roadmap

**v4.0 -- Invisible Memory** has shipped (v4.0.1). Smart Sync, configurable relevance weights, EncryptedStore completeness, and security hardening. Available on [PyPI](https://pypi.org/project/memorymesh/4.0.1/) and [GitHub](https://github.com/sparkvibe-io/memorymesh/releases/tag/v4.0.1).

**v5.0 -- Adaptive Memory** is next. Heuristic-based question frequency tracking, behavioral pattern detection, and multi-device sync via Syncthing/rsync. Lightweight and local -- no LLM-based anticipation, no cloud sync.

See the [full roadmap](https://github.com/sparkvibe-io/memorymesh/blob/main/ROADMAP.md) for details, strategic context, and completed milestones.

---

## Documentation

**Full documentation:** [**sparkvibe-io.github.io/memorymesh**](https://sparkvibe-io.github.io/memorymesh/)

| Guide | Description |
|---|---|
| **[Configuration](https://sparkvibe-io.github.io/memorymesh/configuration/)** | Embedding providers, Ollama setup, all constructor options |
| **[MCP Server](https://sparkvibe-io.github.io/memorymesh/mcp-server/)** | Setup for Claude Code, Cursor, Windsurf + teaching your AI to use memory |
| **[Multi-Tool Sync](https://sparkvibe-io.github.io/memorymesh/multi-tool-sync/)** | Sync memories across Claude, Codex, and Gemini CLI |
| **[CLI Reference](https://sparkvibe-io.github.io/memorymesh/cli/)** | Terminal commands for inspecting and managing memories |
| **[API Reference](https://sparkvibe-io.github.io/memorymesh/api/)** | Full Python API with all methods and parameters |
| **[Architecture](https://sparkvibe-io.github.io/memorymesh/architecture/)** | System design, dual-store pattern, and schema migrations |
| **[FAQ](https://sparkvibe-io.github.io/memorymesh/faq/)** | Common questions answered |
| **[Benchmarks](https://sparkvibe-io.github.io/memorymesh/benchmarks/)** | Performance numbers and how to run benchmarks |

---

## Available On

| Platform | Link |
|----------|------|
| **PyPI** | [pypi.org/project/memorymesh](https://pypi.org/project/memorymesh/) |
| **Smithery** | [smithery.ai/servers/sparkvibe-io/memorymesh](https://smithery.ai/servers/sparkvibe-io/memorymesh) |
| **GitHub** | [github.com/sparkvibe-io/memorymesh](https://github.com/sparkvibe-io/memorymesh) |

---

## Contributing

We welcome contributions from everyone. See [CONTRIBUTING.md](https://github.com/sparkvibe-io/memorymesh/blob/main/CONTRIBUTING.md) for guidelines on how to get started.

---

## License

MIT License. See [LICENSE](https://github.com/sparkvibe-io/memorymesh/blob/main/LICENSE) for the full text.

---

## Free. Forever. For Everyone.

MemoryMesh is part of the [SparkVibe](https://github.com/sparkvibe-io) open-source AI initiative. We believe that foundational AI tools should be free, open, and accessible to everyone -- not locked behind paywalls, cloud subscriptions, or proprietary platforms.

Our mission is to reduce the cost and complexity of building AI applications, so that developers everywhere -- whether at a startup, a research lab, a nonprofit, or learning on their own -- can build intelligent systems without barriers.

If AI is going to shape the future, the tools that power it should belong to all of us.
