"""MemoryMesh -- The SQLite of AI Memory.

An embeddable, zero-dependency AI memory library that any application can
integrate in three lines of code.

Quick start::

    from memorymesh import MemoryMesh

    mem = MemoryMesh()
    mem.remember("The user prefers dark mode.")
    results = mem.recall("What theme does the user like?")

The library is framework-agnostic and works with any LLM backend -- Claude,
GPT, Gemini, Llama, Ollama, or your own custom model.

Memory is stored locally in a SQLite database (default location:
``~/.memorymesh/memories.db``).  No external server is needed.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .core import MemoryMesh
from .embeddings import (
    EmbeddingProvider,
    LocalEmbedding,
    NoopEmbedding,
    OllamaEmbedding,
    OpenAIEmbedding,
    create_embedding_provider,
)
from .memory import Memory
from .relevance import RelevanceEngine, RelevanceWeights
from .store import MemoryStore

__all__ = [
    # Core
    "MemoryMesh",
    # Data model
    "Memory",
    # Storage
    "MemoryStore",
    # Embeddings
    "EmbeddingProvider",
    "LocalEmbedding",
    "OllamaEmbedding",
    "OpenAIEmbedding",
    "NoopEmbedding",
    "create_embedding_provider",
    # Relevance
    "RelevanceEngine",
    "RelevanceWeights",
    # Metadata
    "__version__",
]
