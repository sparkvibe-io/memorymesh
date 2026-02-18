"""Shared fixtures for MemoryMesh evaluation tests."""

from __future__ import annotations

import pytest

from memorymesh import MemoryMesh


@pytest.fixture
def eval_mesh(tmp_path):
    """Create a MemoryMesh with embedding='none' for evaluation tests."""
    proj_db = str(tmp_path / "eval_project" / "memories.db")
    glob_db = str(tmp_path / "eval_global" / "global.db")
    mesh = MemoryMesh(path=proj_db, global_path=glob_db, embedding="none")
    yield mesh
    mesh.close()


@pytest.fixture
def populated_mesh(eval_mesh):
    """Mesh pre-populated with a diverse set of memories for testing."""
    # User preferences (global)
    eval_mesh.remember("User prefers dark mode in all applications", scope="global", importance=0.8)
    eval_mesh.remember(
        "User always uses TypeScript over JavaScript", scope="global", importance=0.9
    )
    eval_mesh.remember(
        "User prefers tabs over spaces for indentation", scope="global", importance=0.7
    )
    eval_mesh.remember("User likes functional programming style", scope="global", importance=0.75)
    eval_mesh.remember("User prefers pytest over unittest", scope="global", importance=0.8)

    # Architecture decisions (project)
    eval_mesh.remember(
        "Decided to use SQLite for storage backend", scope="project", importance=0.95
    )
    eval_mesh.remember(
        "Architecture uses dual-store pattern: project + global", scope="project", importance=0.9
    )
    eval_mesh.remember(
        "Embedding providers are pluggable via factory pattern", scope="project", importance=0.85
    )
    eval_mesh.remember("MCP server uses JSON-RPC over stdio", scope="project", importance=0.8)
    eval_mesh.remember(
        "All state lives in class instances, no global mutable state",
        scope="project",
        importance=0.7,
    )

    # Mistakes learned
    eval_mesh.remember(
        "Bug: forgot to escape LIKE wildcards in search queries", scope="project", importance=0.8
    )
    eval_mesh.remember(
        "Mistake: used global state for database connections, caused threading issues",
        scope="global",
        importance=0.85,
    )

    # Technical context
    eval_mesh.remember(
        "Python 3.9+ required for union type syntax", scope="project", importance=0.6
    )
    eval_mesh.remember("Ruff used for linting and formatting", scope="project", importance=0.5)
    eval_mesh.remember(
        "Version 2.0.0 released with categories and session support",
        scope="project",
        importance=0.7,
    )

    # Mixed importance
    eval_mesh.remember("Server runs on port 8765 by default", scope="project", importance=0.4)
    eval_mesh.remember(
        "Maximum memory text length is 100K characters", scope="project", importance=0.3
    )
    eval_mesh.remember("WAL journal mode used for SQLite", scope="project", importance=0.5)
    eval_mesh.remember("Cosine similarity computed in pure Python", scope="project", importance=0.4)
    eval_mesh.remember(
        "Embeddings stored as binary blobs for space efficiency", scope="project", importance=0.6
    )

    return eval_mesh


def precision_at_k(retrieved: list, relevant: set, k: int) -> float:
    """Compute precision@k.

    Args:
        retrieved: List of retrieved item IDs.
        relevant: Set of relevant item IDs.
        k: Number of top results to consider.

    Returns:
        Precision@k score between 0.0 and 1.0.
    """
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(top_k)


def recall_at_k(retrieved: list, relevant: set, k: int) -> float:
    """Compute recall@k.

    Args:
        retrieved: List of retrieved item IDs.
        relevant: Set of relevant item IDs.
        k: Number of top results to consider.

    Returns:
        Recall@k score between 0.0 and 1.0.
    """
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(relevant)


def mean_reciprocal_rank(retrieved: list, relevant: set) -> float:
    """Compute mean reciprocal rank (MRR).

    Args:
        retrieved: List of retrieved item IDs.
        relevant: Set of relevant item IDs.

    Returns:
        MRR score between 0.0 and 1.0.
    """
    for i, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / i
    return 0.0
