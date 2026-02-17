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

Ollama must be running before MemoryMesh can use it for embeddings:

```bash
ollama serve                              # start in a terminal
ollama pull nomic-embed-text              # download the model (once)
```

If you installed Ollama via Homebrew, it may already be running as a service (`brew services info ollama`). If `ollama serve` says "address already in use", Ollama is already running and you're good to go.

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

---

[Back to README](../README.md)
