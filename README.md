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
- **SQLite-Based** -- All memory is stored in SQLite files. No database servers, no infrastructure. Automatic schema migrations keep existing databases up to date.
- **Framework-Agnostic** -- Works with any LLM, any framework, any architecture. Use it with LangChain, LlamaIndex, raw API calls, or your own custom setup.
- **Pluggable Embeddings** -- Choose the embedding provider that fits your needs: local models, Ollama, OpenAI, or plain keyword matching with zero dependencies.
- **Time-Based Decay** -- Memories naturally fade over time, just like human memory. Recent and frequently accessed memories are ranked higher.
- **Auto-Importance Scoring** -- Automatically detect and prioritize key information. MemoryMesh analyzes text for keywords, structure, and specificity to assign importance scores without manual tuning.
- **Episodic Memory** -- Group memories by conversation session. Recall with session context for better continuity across multi-turn interactions.
- **Memory Compaction** -- Detect and merge similar or redundant memories to keep your store lean. Reduces noise and improves recall accuracy over time.
- **Encrypted Storage** -- Optionally encrypt memory text and metadata at rest. All data stays protected on disk using application-level encryption with zero external dependencies.
- **Privacy-First** -- All data stays on your machine by default. No telemetry, no cloud calls, no data collection. You own your data.
- **Cross-Platform** -- Runs on Linux, macOS, and Windows. Anywhere Python runs, MemoryMesh runs.
- **MCP Support** -- Expose memory as an MCP (Model Context Protocol) server for seamless integration with AI assistants.
- **Multi-Tool Sync** -- Sync memories to Claude Code, OpenAI Codex CLI, and Google Gemini CLI simultaneously. Your knowledge follows you across tools.
- **Memory Categories** -- Automatic categorization with scope routing. Preferences and guardrails go to global scope; decisions and patterns stay in the project. MemoryMesh decides where memories belong.
- **Session Start** -- Structured context retrieval at the beginning of every AI session. Returns user profile, guardrails, common mistakes, and project context in one call.
- **Auto-Compaction** -- Transparent deduplication that runs automatically during normal use. Like SQLite's auto-vacuum, you never need to think about it.
- **CLI** -- Inspect, search, export, compact, and manage memories from the terminal. No Python code required.
- **Pin Support** -- Pin critical memories so they never decay and always rank at the top. Use for guardrails and non-negotiable rules.
- **Privacy Guard** -- Automatically detect secrets (API keys, tokens, passwords) before storing. Optionally redact them with `redact=True`.
- **Contradiction Detection** -- Catch conflicting facts when storing new memories. Choose to keep both, update, or skip.
- **Retrieval Filters** -- Filter recall by category, minimum importance, time range, or metadata key-value pairs.
- **Web Dashboard** -- Browse and search all your memories in a local web UI (`memorymesh ui`).
- **Evaluation Suite** -- Built-in tests for recall quality and adversarial robustness.

---

## What's New in v3

- **Pin support** -- `remember("critical rule", pin=True)` sets importance to 1.0 with zero decay.
- **Privacy guard** -- Detects API keys, GitHub tokens, JWTs, AWS keys, passwords, and more. Use `redact=True` to auto-redact before storing.
- **Contradiction detection** -- `on_conflict="update"` replaces contradicting memories; `"skip"` discards the new one; `"keep_both"` flags it.
- **Retrieval filters** -- `recall(query, category="decision", min_importance=0.7, time_range=(...), metadata_filter={...})`.
- **Web dashboard** -- `memorymesh ui` launches a local browser-based memory viewer.
- **Evaluation suite** -- 32 tests covering recall quality, adversarial inputs, scope isolation, and importance ranking.

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

## Roadmap

We are currently on **v3.0 -- Intelligent Memory**. Next up:

### v4.0 -- Adaptive Memory
- Smart sync -- export top-N most relevant memories, not all
- Auto-remember via hooks/triggers -- no system prompt instructions needed
- Graph-based memory relationships
- Plugin system for custom relevance strategies

### v5.0 -- Anticipatory Intelligence
- Question and behavioral learning across sessions
- Proactive anticipation -- AI that knows what you need before you ask
- Multi-device sync
- Cross-session episodic continuity

See the [full roadmap](https://github.com/sparkvibe-io/memorymesh/blob/main/ROADMAP.md) for version history and completed milestones.

---

## Contributing

We welcome contributions from everyone. See [CONTRIBUTING.md](https://github.com/sparkvibe-io/memorymesh/blob/main/CONTRIBUTING.md) for guidelines on how to get started.

---

## License

MIT License. See [LICENSE](https://github.com/sparkvibe-io/memorymesh/blob/main/LICENSE) for the full text.

---

## Built for Humanity

MemoryMesh is part of the [SparkVibe](https://github.com/sparkvibe-io) open-source AI initiative. We believe that foundational AI tools should be free, open, and accessible to everyone -- not locked behind paywalls, cloud subscriptions, or proprietary platforms.

Our mission is to reduce the cost and complexity of building AI applications, so that developers everywhere -- whether at a startup, a research lab, a nonprofit, or learning on their own -- can build intelligent systems without barriers.

If AI is going to shape the future, the tools that power it should belong to all of us.
