# Getting Started

Get MemoryMesh running in under 60 seconds.

## Installation

=== "Base (zero dependencies)"

    ```bash
    pip install memorymesh
    ```

    Uses keyword matching for recall. No external dependencies at all.

=== "With Ollama (semantic search)"

    ```bash
    pip install memorymesh
    ollama pull nomic-embed-text
    ```

    Ollama support uses Python's built-in `urllib` -- no extra packages needed. See [Ollama setup](configuration.md#using-ollama) for details.

=== "With local embeddings"

    ```bash
    pip install "memorymesh[local]"
    ```

    Uses `sentence-transformers` for fully offline semantic search. Downloads a ~500MB model on first use.

=== "With OpenAI embeddings"

    ```bash
    pip install "memorymesh[openai]"
    ```

    Requires an OpenAI API key. Highest quality embeddings.

## Quick Start

### As a Python Library

```python
from memorymesh import MemoryMesh

# Create a memory instance (stores in SQLite, fully local)
memory = MemoryMesh(embedding="none")  # or "ollama", "local", "openai"

# Store memories
memory.remember("User is a senior Python developer")
memory.remember("User prefers dark mode and concise explanations")
memory.remember("Project uses SQLite for storage")

# Recall relevant memories
results = memory.recall("What does the user prefer?")
for mem in results:
    print(mem.text)

# Clean up
memory.close()
```

### As an MCP Server (for AI Assistants)

MemoryMesh includes a built-in MCP server that gives AI assistants persistent memory.

**1. Install MemoryMesh:**

```bash
pip install memorymesh
```

**2. Configure your AI tool:**

=== "Claude Code"

    Add to `~/.claude/settings.json`:

    ```json
    {
      "mcpServers": {
        "memorymesh": {
          "command": "memorymesh-mcp"
        }
      }
    }
    ```

=== "Claude Desktop"

    Add to `claude_desktop_config.json`:

    ```json
    {
      "mcpServers": {
        "memorymesh": {
          "command": "memorymesh-mcp"
        }
      }
    }
    ```

=== "Gemini CLI"

    Add to your Gemini CLI MCP settings:

    ```json
    {
      "mcpServers": {
        "memorymesh": {
          "command": "memorymesh-mcp"
        }
      }
    }
    ```

=== "OpenAI Codex CLI"

    Add to your Codex CLI MCP settings:

    ```json
    {
      "mcpServers": {
        "memorymesh": {
          "command": "memorymesh-mcp"
        }
      }
    }
    ```

=== "Cursor / Windsurf"

    Add to `.cursor/mcp.json` or equivalent:

    ```json
    {
      "mcpServers": {
        "memorymesh": {
          "command": "memorymesh-mcp"
        }
      }
    }
    ```

**3. Or use the auto-setup command:**

```bash
memorymesh init
```

This auto-detects your installed AI tools and configures all of them.

!!! tip "Recommended: Enable Semantic Search with Ollama"
    By default, the MCP server uses keyword matching -- `recall("testing")` only finds memories containing the exact word "testing". **We strongly recommend adding Ollama** for semantic search, which understands meaning -- `recall("testing")` finds memories about "pytest", "unit tests", and "CI pipeline". Setup takes 2 minutes:

    ```bash
    brew install ollama          # macOS (or curl install on Linux)
    ollama pull nomic-embed-text # one-time ~274MB download
    ```

    Then add `"env": { "MEMORYMESH_EMBEDDING": "ollama" }` to your MCP config. See [full Ollama setup](configuration.md#using-ollama).

## Core Concepts

### Dual-Store Architecture

MemoryMesh uses two SQLite databases:

```
~/.memorymesh/
  global.db                  # User preferences, identity, cross-project facts

<your-project>/.memorymesh/
  memories.db                # Project-specific decisions, patterns, context
```

- **Global store** -- shared across all projects. User preferences, guardrails, personality.
- **Project store** -- isolated per project. Architecture decisions, code patterns, project context.

`recall()` searches both stores by default and merges results.

### Memory Categories

MemoryMesh automatically routes memories to the correct store based on category:

```python
# These go to the global store automatically
memory.remember("I prefer dark mode", category="preference")
memory.remember("Never auto-commit", category="guardrail")

# These stay in the project store
memory.remember("Chose JWT for auth", category="decision")
memory.remember("Uses Google-style docstrings", category="pattern")

# Or let MemoryMesh detect the category from text
memory.remember("I always use black for formatting", auto_categorize=True)
```

| Category | Store | What it captures |
|---|---|---|
| `preference` | Global | Coding style, tool preferences |
| `guardrail` | Global | Rules the AI must follow |
| `mistake` | Global | Past errors to avoid |
| `personality` | Global | User traits and identity |
| `question` | Global | Recurring concerns |
| `decision` | Project | Architecture and design choices |
| `pattern` | Project | Code conventions |
| `context` | Project | Project-specific facts |
| `session_summary` | Project | Conversation summaries |

### Relevance Scoring

When you call `recall()`, MemoryMesh ranks results using four signals:

| Signal | Weight | Description |
|---|---|---|
| Semantic similarity | 50% | How closely the query matches the memory's meaning |
| Recency | 20% | More recent memories score higher |
| Importance | 20% | Higher-importance memories score higher |
| Frequency | 10% | Frequently accessed memories score higher |

Memories also decay over time, just like human memory. Important, frequently-used memories persist; stale, low-importance ones fade naturally.

## Next Steps

- [Configuration](configuration.md) -- Embedding providers, Ollama setup, encryption, tuning
- [MCP Server](mcp-server.md) -- Full MCP setup guide for AI assistants
- [API Reference](api.md) -- Complete Python API documentation
- [CLI Reference](cli.md) -- Terminal commands for managing memories
