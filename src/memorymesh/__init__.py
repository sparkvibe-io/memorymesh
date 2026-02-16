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

Memory is stored locally in SQLite databases.  By default a global store
lives at ``~/.memorymesh/global.db`` and an optional project-scoped store
can be created per project.  No external server is needed.
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
from .mcp_server import MemoryMeshMCPServer
from .memory import GLOBAL_SCOPE, PROJECT_SCOPE, Memory, validate_scope
from .relevance import RelevanceEngine, RelevanceWeights
from .store import MemoryStore

__all__ = [
    # Core
    "MemoryMesh",
    # MCP Server
    "MemoryMeshMCPServer",
    # Data model
    "Memory",
    # Scope constants
    "PROJECT_SCOPE",
    "GLOBAL_SCOPE",
    "validate_scope",
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
