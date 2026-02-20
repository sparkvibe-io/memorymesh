# MemoryMesh Feedback Report — Claude Code Agent (Power User)

**Date:** 2026-02-20
**Reporter:** Claude Code Agent (Opus 4.6) acting as primary user
**Context:** Building OpenSpek (Tauri + Rust + SolidJS app) across multiple sessions. User explicitly requested "use MemoryMesh." All 7 `remember()` calls failed. User asked "why are we not using memorymesh."
**MemoryMesh Version:** 3.0.0
**Config:** Ollama embeddings with `nomic-embed-text`, MCP server via Claude Code `settings.json`

---

## Executive Summary

MemoryMesh's architecture is sound — dual-store model, category-based auto-routing, contradiction detection, importance decay, pin support, and embedding fallback are all excellent. But the **zero-to-working gap** is too wide. As an AI agent, I installed it, configured it, and it silently failed on every call. I had no way to diagnose, no fallback, and no self-remediation path. For a tool meant to be used autonomously by AI agents, the gap between "installed" and "actually works" needs to be zero.

---

## The Situation

Claude Code was launched from `/Users/krishna/Development` (parent directory). The actual project is at `/Users/krishna/Development/OpenSpek` (a git repo). The MCP config was:

```json
"memorymesh": {
  "command": "/Users/krishna/Development/MemoryMesh/.venv/bin/memorymesh-mcp",
  "env": {
    "MEMORYMESH_EMBEDDING": "ollama",
    "MEMORYMESH_OLLAMA_MODEL": "nomic-embed-text"
  }
}
```

Ollama was running. MemoryMesh process was running. The MCP `initialize` handshake completed. Everything looked fine.

Then every `remember()` call returned:
```json
{"error": "No project database configured. Pass 'path' to MemoryMesh() or use scope='global'."}
```

Even `scope="global"` failed with the same error.

---

## Pain Points (Ordered by Severity)

### P0-1: Global Scope Also Fails (Possible Bug)

**What happened:** After project scope failed, I tried `scope="global"`. Same error. The code says global store is ALWAYS created (defaults to `~/.memorymesh/global.db`), so this should never fail.

**Possible causes:**
1. The double-initialization pattern threw away the global store during `initialize` and the second creation failed silently
2. Sibling tool call error cascade in Claude Code — when one parallel tool call fails, all siblings fail with `"Sibling tool call errored"`
3. The global store initialization itself failed (Ollama connection? directory permissions? sqlite issue?)

**Impact:** Complete blocker. The error message says "use scope='global'" as the workaround, but global also doesn't work. Dead end. No recourse for the agent.

**Suggested fix:**
- Ensure global store creation NEVER fails (wrap in try/except with a clear fallback)
- If global store fails, the error message should say WHY, not suggest "use global" when global is also broken
- Test: what happens if `~/.memorymesh/` doesn't exist and the parent is not writable?

---

### P0-2: Silent Failure During Initialization (No Health Signal)

**What happened:** MemoryMesh started, connected, completed the MCP handshake. At NO point did it tell me "project detection failed." I only discovered this on the first `remember()` call.

**Why it hurts:** As an AI agent, I can't "check" if MemoryMesh is healthy before using it. I assumed it was working because it connected successfully. The `initialize` response gives zero indication it's in degraded (global-only) mode.

**Suggested fixes:**
1. Add a `warnings` field to the `initialize` response:
   ```json
   {
     "serverInfo": {"name": "memorymesh", "version": "3.0.0"},
     "warnings": ["No project root detected. Project-scoped memories unavailable. Set MEMORYMESH_PATH or launch from a git repository."]
   }
   ```
2. Make `session_start` report store health (it currently returns user profile + guardrails but NOT store status)
3. Add a `health_check` / `status` tool (see P1-4 below)

---

### P1-1: Project Root Detection Too Rigid

**The detection chain:**
1. MCP roots from client
2. `MEMORYMESH_PROJECT_ROOT` env var
3. CWD with `.git` or `pyproject.toml`
4. `None` (fail)

**Why all 4 failed:**
1. Claude Code was in `/Users/krishna/Development` (parent). MCP root sent was the parent, which has no `.git`.
2. `MEMORYMESH_PROJECT_ROOT` was not set.
3. CWD is `/Users/krishna/Development` — no `.git` here (repo is in the subdirectory).
4. Result: `None`. Silent failure.

**Real-world scenarios this misses:**
- User launches Claude Code from a workspace root containing multiple projects
- User is in a monorepo parent
- User `cd`s into a project AFTER launching Claude Code (CWD was captured at startup)
- Project uses `Cargo.toml`, `go.mod`, `package.json`, `.hg` instead of `.git` or `pyproject.toml`

**Suggested fixes:**
- Walk UP from CWD looking for `.memorymesh/` directories (like git finds `.git`)
- Walk DOWN one level checking subdirectories for `.git`
- Expand the marker file list: `.git`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `package.json`, `.hg`, `Makefile`
- Support multiple project roots (workspace mode)
- When detection fails, log a WARNING visible to the user/agent

---

### P1-2: Error Messages Don't Help the AI Agent Self-Remediate

**The error:**
```
No project database configured. Pass 'path' to MemoryMesh() or use scope='global'.
```

**Problems with this message (from an AI agent's perspective):**
- I can't "pass 'path' to MemoryMesh()" — I don't control the server constructor
- `scope='global'` also didn't work (see P0-1)
- Doesn't tell me WHERE to configure the path
- Doesn't tell me what detection was attempted and why it failed
- Doesn't suggest actionable steps for an MCP client

**Better error:**
```
No project database configured.
Detection attempted:
  - MCP roots: /Users/krishna/Development (no .git found)
  - MEMORYMESH_PROJECT_ROOT: not set
  - CWD: /Users/krishna/Development (no .git or pyproject.toml found)
Fix options:
  1. Set MEMORYMESH_PATH=/path/to/project/.memorymesh/memories.db in MCP server env config
  2. Set MEMORYMESH_PROJECT_ROOT=/path/to/project in MCP server env config
  3. Launch Claude Code from within a git repository
Fallback: Use scope='global' for user-wide memories (not project-specific).
```

---

### P1-3: No Runtime Project Path Configuration

If project detection fails, I'm stuck. I can see the project path (`/Users/krishna/Development/OpenSpek`) but I have no tool to tell MemoryMesh "use this path."

**What I need:**
```json
{
  "name": "configure_project",
  "params": {
    "path": "/Users/krishna/Development/OpenSpek"
  }
}
```

This would dynamically create the project store without requiring a server restart.

**Why this matters:** Restarting the MCP server means restarting the entire Claude Code session, which loses all conversation context. For multi-hour sessions building complex projects, this is extremely disruptive.

---

### P1-4: No Health Check / Diagnostic Tool

**What I need as an AI agent:** A way to ask "are you working?"

Currently:
- `remember` — fails if broken (discover the problem the hard way)
- `recall` — returns empty (looks like "no memories" not "I'm broken")
- `memory_stats` — errors when project store missing
- `session_start` — doesn't report store health

**Proposed `status` tool response:**
```json
{
  "project_store": {
    "status": "not_configured",
    "reason": "No project root detected",
    "attempted": ["MCP roots: /Users/krishna/Development", "CWD: no .git"]
  },
  "global_store": {
    "status": "ok",
    "path": "~/.memorymesh/global.db",
    "count": 42
  },
  "embedding": {
    "provider": "ollama",
    "model": "nomic-embed-text",
    "status": "connected"
  },
  "version": "3.0.0"
}
```

This would have immediately told me what was wrong and how to fix it.

---

### P2-1: Static Project Path in Global Config (Architecture Issue)

The fix I applied was hardcoding the path in `~/.claude/settings.json`:
```json
"MEMORYMESH_PATH": "/Users/krishna/Development/OpenSpek/.memorymesh/memories.db"
```

This is a **global** config. Now every Claude Code session, regardless of project, points to the OpenSpek database. When the user works on a different project tomorrow, memories go to the wrong database.

**Suggested fixes:**
- Support per-project config (`.claude/settings.local.json` or per-project MCP overrides)
- Make auto-detection reliable enough that static paths aren't needed
- Support a `configure_project` tool (see P1-3) for runtime correction

---

### P2-2: Double-Initialization Pattern is Fragile

**What the code does:**
1. `__init__()` → creates mesh #1 (global-only, no project root)
2. MCP `initialize` → closes mesh #1, creates mesh #2 (with project root from client)

**Issues:**
- Opens and immediately closes database connections (wasteful)
- If `initialize` has timing issues or client doesn't send roots, stuck with broken mesh #1
- Two code paths to debug
- "Which mesh am I talking to?" is non-obvious

**Suggested fix:** Lazy initialization — don't create the mesh until the first tool call, by which point `initialize` has already happened. Or: create once, add `set_project_root()` method to attach project store post-init.

---

### P2-3: `memorymesh init` Writes to Wrong Config Path

`memorymesh init` writes to `~/.claude/claude_code_config.json` (legacy). Current Claude Code uses `~/.claude/settings.json`. So `memorymesh init` doesn't configure anything for current installations.

---

### P3-1: MCP Server Default Embedding is "none" (Surprise)

Library default: `embedding="local"`. MCP server default: `embedding="none"`. Out-of-the-box, the MCP server does keyword-only search, which is much worse than semantic search. Users expecting library behavior get degraded recall quality without knowing it.

**Suggested fixes:**
- Match library default (`"local"`)
- Or prominently warn during setup: "Running without embeddings. Set MEMORYMESH_EMBEDDING for better recall."
- Or emit a startup log: "Embedding provider: none (keyword search only)"

---

### P3-2: `MEMORYMESH_DEBUG` Not Documented

This env var enables DEBUG logging but isn't in the docs or the environment variables table. When troubleshooting, users don't know it exists.

---

### P3-3: CWD Heuristic Only Checks `.git` and `pyproject.toml`

Many projects use:
- `Cargo.toml` (Rust — like OpenSpek)
- `go.mod` (Go)
- `package.json` (Node.js)
- `.hg` (Mercurial)
- `build.gradle` / `pom.xml` (Java)
- `CMakeLists.txt` (C/C++)

Only checking `.git` and `pyproject.toml` makes the heuristic Python/git-centric.

---

## What MemoryMesh Gets Right

- **Dual-store model** (project vs global) is architecturally correct
- **Category-based auto-routing** (preferences → global, decisions → project) is smart
- **Embedding fallback** — gracefully degrades to keyword search if Ollama is down, never crashes
- **Contradiction detection** and **near-duplicate detection** in `review_memories` are valuable
- **Importance scoring with time decay** is well-designed
- **Pin support** for permanent high-importance memories
- **Privacy guard** (`redact_secrets`) for API keys and tokens
- **`session_start`** concept for beginning-of-conversation context injection
- **Clean codebase** — zero TODO/FIXME comments, well-structured modules
- **Security limits** — message size caps, memory count limits, metadata size limits

The core product is excellent. The gap is in the **setup experience** and **failure communication**, especially for AI agent users who can't read logs or manually debug configurations.

---

## Recommended Fix Priority

1. **Add `status` / `health_check` tool** — immediate diagnostic capability
2. **Add `configure_project` tool** — runtime fix without restart
3. **Fix global scope fallback** — ensure it never fails
4. **Improve error messages** — include what was tried and actionable fix steps
5. **Add warnings to `initialize` response** — proactive failure communication
6. **Expand project detection markers** — support Cargo.toml, package.json, go.mod, etc.
7. **Fix `memorymesh init` config path** — write to `settings.json` not legacy path
8. **Document `MEMORYMESH_DEBUG`** — help users troubleshoot
9. **Consider lazy initialization** — avoid double-init pattern

---

*This feedback was generated during a real development session where MemoryMesh was the intended persistent memory layer for a multi-session project. The pain points are from actual usage, not hypothetical scenarios.*
