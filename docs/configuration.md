# Configuration

Everything you need to configure MemoryMesh: embedding providers, storage paths, and relevance tuning.

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

[Back to README](../README.md)
