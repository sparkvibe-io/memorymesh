# Configuration

Everything you need to configure MemoryMesh: embedding providers, storage paths, encryption, and relevance tuning.

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

### Using Ollama

#### What is Ollama?

Ollama is a free, open-source application that runs AI models locally on your machine. Think of it like a local server -- it runs in the background and applications connect to it over HTTP. MemoryMesh uses Ollama for one specific purpose: converting text into numerical vectors (embeddings) that enable semantic search.

Without Ollama (or another embedding provider), MemoryMesh falls back to keyword matching -- `recall("testing")` will only find memories containing the exact word "testing". With Ollama, MemoryMesh understands meaning -- `recall("testing")` finds memories about "pytest", "unit tests", "test coverage", and "CI pipeline" because they are semantically related.

#### How it works

```
┌──────────────────┐         HTTP (localhost:11434)        ┌──────────────────┐
│   Your AI Tool   │                                       │                  │
│  (Claude Code,   │                                       │     Ollama       │
│   Gemini CLI,    │                                       │  (background     │
│   Cursor, etc.)  │                                       │   service)       │
│        │         │                                       │                  │
│   MemoryMesh     │  ───── "embed this text" ──────────>  │  nomic-embed-    │
│   (MCP server)   │  <──── [0.02, -0.15, 0.89, ...] ───  │  text model      │
│                  │         768 numbers back               │                  │
└──────────────────┘                                       └──────────────────┘
         │
    SQLite DB
  (memories.db)
```

1. When you call `remember("User prefers dark mode")`, MemoryMesh sends the text to Ollama
2. Ollama runs the embedding model and returns a vector of 768 numbers representing the meaning
3. MemoryMesh stores the text + vector in SQLite
4. When you call `recall("theme preferences")`, MemoryMesh embeds the query and finds stored memories with similar vectors
5. This is why `recall("theme preferences")` finds "User prefers dark mode" even though no words match

#### Step 1: Install Ollama

Ollama is a separate application. Install it first:

**macOS:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from [ollama.com/download](https://ollama.com/download).

#### Step 2: Start Ollama

Ollama runs as a background service on port 11434. You start it once and it stays running.

```bash
# Start Ollama (runs in the background)
ollama serve
```

**Already running?** If you see "address already in use", Ollama is already running. This is fine -- on macOS with Homebrew it often auto-starts.

```bash
# Check if Ollama is running
brew services info ollama       # macOS (Homebrew)
curl http://localhost:11434     # Any OS -- should return "Ollama is running"
```

#### Step 3: Pull the embedding model

Download the embedding model that MemoryMesh will use. This is a one-time download (~274MB):

```bash
ollama pull nomic-embed-text
```

**What is `nomic-embed-text`?** It is an *embedding model*, not a chat model. It does one thing: convert text into a vector of 768 numbers that capture semantic meaning. Similar texts produce similar vectors. This is what powers MemoryMesh's semantic search.

| Embedding Model | Dimensions | Size | Quality | Speed |
|---|---|---|---|---|
| `nomic-embed-text` | 768 | 274MB | Very good | Fast |
| `all-minilm` | 384 | 46MB | Good | Very fast |
| `mxbai-embed-large` | 1024 | 670MB | Best | Slower |

`nomic-embed-text` is the recommended default -- good quality, reasonable size, fast. You can use a different model by passing `ollama_model="model-name"`.

#### Step 4: Install and configure MemoryMesh

```bash
# Install MemoryMesh (Ollama support uses only stdlib -- no extra deps needed)
pip install memorymesh
```

**Important:** You do NOT need a special install for Ollama support. `pip install memorymesh` is sufficient because MemoryMesh communicates with Ollama via HTTP using Python's built-in `urllib` -- no extra packages required.

**As a Python library:**
```python
from memorymesh import MemoryMesh

memory = MemoryMesh(
    embedding="ollama",
    ollama_model="nomic-embed-text",           # default
    # ollama_base_url="http://localhost:11434", # default, change if Ollama is on another machine
)
```

**As an MCP server** (for Claude Code, Gemini CLI, Cursor, etc.):
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

#### Step 5: Verify it works

```bash
# Quick test
python -c "
from memorymesh import MemoryMesh
m = MemoryMesh(embedding='ollama')
m.remember('User prefers Python and dark mode')
results = m.recall('programming language preferences')
print(results[0].text if results else 'No results')
m.close()
"
```

If you see "User prefers Python and dark mode", semantic search is working.

#### FAQ

**Q: Does Ollama need to be running in the same terminal as MemoryMesh?**
No. Ollama is a background service. Once started, it listens on port 11434. MemoryMesh connects to it via HTTP from any process. You can run `pip install`, `memorymesh-mcp`, and your AI tools in any terminal.

**Q: Does Ollama use my GPU?**
Yes, if available. Ollama automatically uses your GPU (CUDA on Linux/Windows, Metal on macOS) for faster inference. The embedding model is small enough that CPU is also fast (~10ms per embedding).

**Q: Can I use Ollama on a remote server?**
Yes. Set `ollama_base_url="http://your-server:11434"` or `MEMORYMESH_OLLAMA_BASE_URL` env var. MemoryMesh will connect to the remote Ollama instance.

**Q: What if Ollama is not running when MemoryMesh starts?**
MemoryMesh gracefully falls back to keyword-only search. Your memories are still stored and recalled, just without semantic matching. Start Ollama and the next `recall()` will use embeddings automatically.

## Constructor Options

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

    # Encryption (optional)
    # encryption_key="my-secret-key",     # Encrypt text and metadata at rest

    # Relevance tuning (optional)
    # relevance_weights=RelevanceWeights(
    #     semantic=0.5,
    #     recency=0.2,
    #     importance=0.2,
    #     frequency=0.1,
    # ),
)
```

## Encrypted Storage

MemoryMesh can encrypt memory text and metadata at rest. Pass an `encryption_key` to the constructor:

```python
memory = MemoryMesh(
    path=".memorymesh/memories.db",
    encryption_key="my-secret-passphrase",
)

# Memories are encrypted before writing to SQLite
memory.remember("Sensitive API key: sk-abc123")

# Decrypted transparently on recall
results = memory.recall("API key")
```

How it works:

- A key is derived from your passphrase using PBKDF2-HMAC-SHA256.
- The `text` and `metadata` fields are encrypted before storage and decrypted on read.
- IDs, timestamps, importance, and embeddings are **not** encrypted (needed for queries and indexing).
- A random salt is stored in the database and reused across sessions.
- Uses only Python standard library (`hashlib`, `hmac`, `os`) -- zero external dependencies.

This protects against casual inspection of the database file on disk. It is not a substitute for full-disk encryption for highly sensitive data.

## Auto-Importance Scoring

Instead of manually setting importance on every `remember()` call, let MemoryMesh score it automatically:

```python
# Manual importance (default behavior)
memory.remember("User prefers dark mode", importance=0.7)

# Auto-scored importance based on text analysis
memory.remember("Critical security decision: use JWT with RS256", auto_importance=True)
```

The auto-scorer analyzes text using four heuristic signals:

| Signal | Weight | What it detects |
|---|---|---|
| Keywords | 35% | Decision words ("critical", "always", "security") boost; tentative words ("maybe", "temporary") reduce |
| Specificity | 30% | File paths, version numbers, proper nouns, URLs indicate high-value information |
| Structure | 20% | Code patterns (backticks, function names, imports) suggest technical decisions |
| Length | 15% | Very short texts score lower; detailed texts score higher |

The output is clamped to `[0.0, 1.0]` with a baseline of `0.5`.

## Memory Categories

MemoryMesh v2.0 introduces automatic memory categorization. When you set a category, the scope is automatically routed:

```python
# Category determines scope automatically
memory.remember("I prefer dark mode", category="preference")        # -> global
memory.remember("Never auto-commit", category="guardrail")          # -> global
memory.remember("Chose SQLite over Postgres", category="decision")  # -> project

# Or let MemoryMesh detect the category from text
memory.remember("I always use black for formatting", auto_categorize=True)
# Detected as "preference" -> stored in global scope
```

| Category | Auto-Scope | Description |
|---|---|---|
| `preference` | global | User coding style, tool preferences |
| `guardrail` | global | Rules AI must follow |
| `mistake` | global | Past mistakes to avoid |
| `personality` | global | User character traits |
| `question` | global | Recurring questions/concerns |
| `decision` | project | Architecture/design decisions |
| `pattern` | project | Code patterns and conventions |
| `context` | project | Project-specific facts |
| `session_summary` | project | Auto-generated session summaries |

When `auto_categorize=True`, MemoryMesh also enables `auto_importance=True` automatically.

## Session Start

Retrieve structured context at the beginning of every AI session:

```python
context = memory.session_start(project_context="working on auth module")

# Returns:
# {
#     "user_profile": ["Senior Python developer", "Prefers dark mode"],
#     "guardrails": ["Never auto-commit without asking"],
#     "common_mistakes": ["Forgot to run tests before pushing"],
#     "common_questions": ["Always asks about test coverage"],
#     "project_context": ["Uses SQLite for storage", "Google-style docstrings"],
#     "last_session": ["Implemented auth module, 15 tests added"],
# }
```

This is available as an MCP tool (`session_start`) that AI assistants can call at the beginning of every conversation.

## Auto-Compaction

MemoryMesh automatically detects and merges duplicate memories during normal operation. Every 50 `remember()` calls, a lightweight compaction pass runs in the background. This is like SQLite's auto-vacuum -- you never need to think about it.

```python
# Adjust the interval (default: 50)
memory.compact_interval = 100   # compact every 100 writes
memory.compact_interval = 0     # disable auto-compaction

# Manual compaction is still available
result = memory.compact(scope="project", dry_run=True)
print(f"Would merge {result.merged_count} duplicates")
```

## Pin Support

Pin critical memories so they never fade and always appear in recall results:

```python
memory.remember("NEVER auto-commit without asking the user", pin=True)
```

When `pin=True`:

- Importance is set to `1.0` (maximum).
- Decay rate is set to `0.0` (never fades).
- The metadata field `pinned: true` is set for identification.

Use pinning for guardrails, non-negotiable rules, and critical identity facts that should always influence the AI's behavior.

## Privacy Guard

MemoryMesh scans all text for potential secrets before storing. Detected patterns include:

| Pattern | Example |
|---|---|
| API keys | `sk-abc123...`, `pk-xyz...` |
| GitHub tokens | `ghp_...`, `gho_...` |
| Passwords | `password: mySecret` |
| Private keys | `-----BEGIN PRIVATE KEY-----` |
| JWT tokens | `eyJhbG...` |
| AWS access keys | `AKIA...` |
| Slack tokens | `xoxb-...` |

When secrets are detected, a warning is logged and metadata flags (`has_secrets_warning`, `detected_secret_types`) are added. To automatically redact secrets before storing:

```python
memory.remember("API key is sk-abc123456789", redact=True)
# Stored text: "API key is [REDACTED]"
```

You can also use the functions directly:

```python
from memorymesh.privacy import check_for_secrets, redact_secrets

secrets = check_for_secrets("my password: hunter2")
# ["password"]

clean = redact_secrets("token: sk-abc123456789")
# "token: [REDACTED]"
```

## Contradiction Detection

When storing a new memory, MemoryMesh can check for existing memories that contradict it. Control the behavior with the `on_conflict` parameter:

```python
# Default: store both, flag the contradiction in metadata
memory.remember("Use PostgreSQL for production", on_conflict="keep_both")

# Replace the most similar existing memory
memory.remember("Use PostgreSQL for production", on_conflict="update")

# Don't store if a contradiction is found
memory.remember("Use PostgreSQL for production", on_conflict="skip")
```

The three conflict modes:

| Mode | Behavior |
|---|---|
| `keep_both` | Store the new memory alongside existing ones. Adds `has_contradiction` flag to metadata. |
| `update` | Replace the most similar existing memory with the new text. |
| `skip` | Discard the new memory if a contradiction is found. Returns empty string. |

You can also find contradictions directly:

```python
from memorymesh.contradiction import find_contradictions, ConflictMode

# Find memories that may contradict new text
contradictions = find_contradictions(text, embedding, store, threshold=0.75)
# Returns: [(memory, similarity_score), ...]
```

## Retrieval Filters

`recall()` supports additional filters to narrow down results:

```python
results = memory.recall(
    "auth decisions",
    k=10,
    category="decision",           # Only return memories with this category
    min_importance=0.7,            # Only return memories with importance >= 0.7
    time_range=("2026-01-01", "2026-02-01"),  # Filter by creation date
    metadata_filter={"pinned": True},         # Match specific metadata keys
)
```

| Filter | Type | Description |
|---|---|---|
| `category` | `str` | Only return memories with this category in metadata |
| `min_importance` | `float` | Minimum importance threshold |
| `time_range` | `tuple[str, str]` | ISO-8601 date range `(start, end)` for creation time |
| `metadata_filter` | `dict` | Key-value pairs that must match in memory metadata |

Filters are applied before ranking, so they reduce the candidate set rather than post-filtering results.

---

[Back to Home](index.md)
