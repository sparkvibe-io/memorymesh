"""Contradiction detection for MemoryMesh.

When a new memory is stored, checks for existing memories that may
contradict or conflict with the new content.  Uses embedding similarity
(when available) or keyword overlap to find candidates.

Uses **only the Python standard library** -- no external dependencies.
"""

from __future__ import annotations

import enum

from .memory import Memory
from .store import MemoryStore, cosine_similarity


class ConflictMode(enum.Enum):
    """How to handle detected contradictions.

    Attributes:
        KEEP_BOTH: Store the new memory alongside existing ones (default).
            Flags the contradiction in metadata.
        UPDATE: Replace the most similar existing memory with the new text.
        SKIP: Do not store the new memory if a contradiction is found.
    """

    KEEP_BOTH = "keep_both"
    UPDATE = "update"
    SKIP = "skip"


def find_contradictions(
    text: str,
    embedding: list[float] | None,
    store: MemoryStore,
    threshold: float = 0.75,
    max_candidates: int = 5,
) -> list[tuple[Memory, float]]:
    """Find existing memories that may contradict the new text.

    Strategy:
        1. If embeddings are available, retrieve all memories with embeddings,
           compute cosine similarity, and filter those above *threshold*.
        2. If no embeddings, fall back to keyword search for candidates.
        3. Return candidates sorted by similarity (descending).

    Args:
        text: The new memory text to check against existing memories.
        embedding: The embedding vector for the new text, or ``None``
            if embeddings are not available.
        store: The :class:`MemoryStore` to search for existing memories.
        threshold: Minimum similarity score to consider a memory as a
            potential contradiction. Default: 0.75.
        max_candidates: Maximum number of contradictions to return.

    Returns:
        A list of ``(memory, similarity_score)`` tuples, sorted by
        similarity descending. Empty if no contradictions found.
    """
    candidates: list[tuple[Memory, float]] = []

    if embedding:
        # Vector-based search
        all_with_emb = store.get_all_with_embeddings(limit=10_000)
        for mem in all_with_emb:
            if mem.embedding:
                try:
                    sim = cosine_similarity(embedding, mem.embedding)
                except ValueError:
                    continue
                if sim >= threshold:
                    candidates.append((mem, sim))
    else:
        # Keyword fallback -- use first few significant words as queries
        words = text.split()[:10]
        if words:
            keyword_query = " ".join(words[:5])
            hits = store.search_by_text(keyword_query, limit=max_candidates * 2)
            for mem in hits:
                # Use a simple word overlap ratio as similarity proxy
                sim = _word_overlap(text, mem.text)
                if sim >= threshold:
                    candidates.append((mem, sim))

    # Sort by similarity descending and limit
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:max_candidates]


def _word_overlap(text_a: str, text_b: str) -> float:
    """Compute word-level Jaccard similarity between two texts.

    Args:
        text_a: First text.
        text_b: Second text.

    Returns:
        Similarity score in ``[0.0, 1.0]``.
    """
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)
