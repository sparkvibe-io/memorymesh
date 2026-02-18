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

__version__ = "3.0.0"

from .auto_importance import score_importance
from .categories import (
    CATEGORY_SCOPE_MAP,
    GLOBAL_CATEGORIES,
    PROJECT_CATEGORIES,
    VALID_CATEGORIES,
    auto_categorize,
    scope_for_category,
    validate_category,
)
from .compaction import CompactionResult, compact
from .contradiction import ConflictMode, find_contradictions
from .core import MemoryMesh
from .embeddings import (
    EmbeddingProvider,
    LocalEmbedding,
    NoopEmbedding,
    OllamaEmbedding,
    OpenAIEmbedding,
    create_embedding_provider,
)
from .encryption import EncryptedMemoryStore, decrypt_field, derive_key, encrypt_field
from .formats import (
    FormatAdapter,
    create_format_adapter,
    get_all_adapters,
    get_format_names,
    get_installed_adapters,
    sync_from_format,
    sync_to_all,
    sync_to_format,
)
from .html_export import generate_html
from .mcp_server import MemoryMeshMCPServer
from .memory import GLOBAL_SCOPE, PROJECT_SCOPE, Memory, validate_scope
from .privacy import check_for_secrets, redact_secrets
from .relevance import RelevanceEngine, RelevanceWeights
from .report import generate_report
from .review import ReviewIssue, ReviewResult, review_memories
from .store import MemoryStore, detect_project_root
from .sync import sync_from_memory_md, sync_to_memory_md

__all__ = [
    # Auto-importance
    "score_importance",
    # Categories
    "CATEGORY_SCOPE_MAP",
    "VALID_CATEGORIES",
    "GLOBAL_CATEGORIES",
    "PROJECT_CATEGORIES",
    "auto_categorize",
    "scope_for_category",
    "validate_category",
    # Compaction
    "compact",
    "CompactionResult",
    # Contradiction detection
    "ConflictMode",
    "find_contradictions",
    # Encryption
    "EncryptedMemoryStore",
    "derive_key",
    "encrypt_field",
    "decrypt_field",
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
    "detect_project_root",
    # Embeddings
    "EmbeddingProvider",
    "LocalEmbedding",
    "OllamaEmbedding",
    "OpenAIEmbedding",
    "NoopEmbedding",
    "create_embedding_provider",
    # HTML Export
    "generate_html",
    # Sync (legacy)
    "sync_to_memory_md",
    "sync_from_memory_md",
    # Formats (multi-format sync)
    "FormatAdapter",
    "create_format_adapter",
    "get_all_adapters",
    "get_installed_adapters",
    "get_format_names",
    "sync_to_format",
    "sync_from_format",
    "sync_to_all",
    # Report
    "generate_report",
    # Privacy
    "check_for_secrets",
    "redact_secrets",
    # Review
    "ReviewIssue",
    "ReviewResult",
    "review_memories",
    # Relevance
    "RelevanceEngine",
    "RelevanceWeights",
    # Metadata
    "__version__",
]
