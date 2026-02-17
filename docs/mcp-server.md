# MCP Server

MemoryMesh includes a built-in MCP (Model Context Protocol) server that lets AI assistants use your memory directly as a tool. **No API keys required** for the default setup.

## Claude Code

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

## Claude Desktop

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

## Cursor / Windsurf

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

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MEMORYMESH_PATH` | Auto-detected | Path to the project SQLite database |
| `MEMORYMESH_GLOBAL_PATH` | `~/.memorymesh/global.db` | Path to the global SQLite database |
| `MEMORYMESH_PROJECT_ROOT` | Auto-detected | Project root directory |
| `MEMORYMESH_EMBEDDING` | `none` | Embedding provider (`none`, `local`, `ollama`, `openai`) |
| `MEMORYMESH_OLLAMA_MODEL` | `nomic-embed-text` | Ollama model name |
| `OPENAI_API_KEY` | -- | Required only when using `openai` embeddings |

### Enabling Semantic Search (Ollama)

By default, the MCP server uses keyword matching (`MEMORYMESH_EMBEDDING=none`). To enable semantic search, configure Ollama:

**Claude Code** (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "memorymesh": {
      "command": "memorymesh-mcp",
      "env": {
        "MEMORYMESH_EMBEDDING": "ollama",
        "MEMORYMESH_OLLAMA_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "memorymesh": {
      "command": "memorymesh-mcp",
      "env": {
        "MEMORYMESH_EMBEDDING": "ollama",
        "MEMORYMESH_OLLAMA_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

This requires Ollama to be running locally. See [Configuration > Using Ollama](configuration.md#using-ollama) for setup instructions.

## Hybrid Memory Architecture

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

## Available Tools

Once connected, your AI assistant gains these tools:

- **`remember`** -- Store facts, preferences, and decisions. Supports `scope`, `category` (auto-routes scope), and `auto_categorize` (detect category from text).
- **`recall`** -- Search memories by natural language query (supports `scope`)
- **`forget`** -- Delete a specific memory by ID (searches both stores)
- **`forget_all`** -- Delete all memories in a scope (defaults to project)
- **`memory_stats`** -- View memory count and timestamps (supports `scope`)
- **`session_start`** -- Retrieve structured context for the start of a new session. Returns user profile, guardrails, common mistakes, and project context. Call this at the beginning of every conversation.

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

### When to `session_start`

- **Start of every conversation**: Call `session_start` to load your user
  profile, guardrails, and project context.

### When to `recall`

- **Before making architectural decisions**: Check if this was decided before.
- **When debugging**: Check if this problem was encountered previously.
- **When unsure about conventions**: Check for stored patterns.

### When to `remember`

- **After completing a task**: Store key decisions and patterns.
  Use `category` to classify: `"decision"`, `"pattern"`, `"context"`.
- **When the user teaches you something**: Use `category: "preference"`
  or `category: "guardrail"` -- these auto-route to global scope.
- **After fixing a non-trivial bug**: Use `category: "mistake"`.

### Scope guidance

Categories auto-route scope. If not using categories:
- Use `scope: "project"` for project-specific decisions.
- Use `scope: "global"` for user preferences and identity.
```

### OpenAI Codex CLI

Add a `## Memory (MemoryMesh)` section to your project's `AGENTS.md`:

```markdown
## Memory (MemoryMesh)

MemoryMesh is configured as an MCP tool. Use it proactively for persistent
memory across sessions.

- At the start of every task, call `session_start` to load user profile,
  guardrails, and project context.
- Call `recall` before making decisions to check for prior context.
- After completing work, call `remember` with a `category` to store key
  decisions (`"decision"`), patterns (`"pattern"`), or context (`"context"`).
- Use `category: "preference"` or `category: "guardrail"` for user-level
  facts -- these auto-route to global scope.
```

### Google Gemini CLI

Add a `## Memory (MemoryMesh)` section to your project's `GEMINI.md`:

```markdown
## Memory (MemoryMesh)

MemoryMesh is configured as an MCP tool. Use it proactively for persistent
memory across sessions.

- At the start of every task, call `session_start` to load user profile,
  guardrails, and project context.
- Call `recall` before making decisions to check for prior context.
- After completing work, call `remember` with a `category` to store key
  decisions (`"decision"`), patterns (`"pattern"`), or context (`"context"`).
- Use `category: "preference"` or `category: "guardrail"` for user-level
  facts -- these auto-route to global scope.
```

### Generic / Other MCP-Compatible Tools

For any tool that supports MCP:

1. Add the MCP server config (see [MCP Server setup](#claude-code) above).
2. Add instructions to the tool's system prompt or configuration file telling it to call `recall` at the start of conversations and `remember` after completing work.

---

[Back to README](../README.md)
