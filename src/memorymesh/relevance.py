"""Relevance scoring and time-based decay engine for MemoryMesh.

Combines multiple signals -- semantic similarity, recency, importance, and
access frequency -- into a single relevance score that determines which
memories surface during recall.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .memory import Memory
from .store import cosine_similarity


@dataclass
class RelevanceWeights:
    """Weights that control how each signal contributes to the final score.

    All weights should be non-negative.  They do not need to sum to 1;
    the engine normalises them internally.

    Attributes:
        semantic: Weight for cosine similarity between query and memory
            embeddings.
        recency: Weight for how recently the memory was accessed or
            updated.
        importance: Weight for the memory's importance score.
        frequency: Weight for how often the memory has been accessed.
    """

    semantic: float = 0.5
    recency: float = 0.2
    importance: float = 0.2
    frequency: float = 0.1

    def total(self) -> float:
        """Return the sum of all weights."""
        return self.semantic + self.recency + self.importance + self.frequency


class RelevanceEngine:
    """Scores, ranks, and decays memories.

    Args:
        weights: A :class:`RelevanceWeights` instance controlling the
            relative importance of each scoring signal.
        max_recency_days: Number of days after which the recency signal
            reaches its minimum.  Memories older than this still receive
            a small recency score.
        max_access_count: Access count at which the frequency signal
            saturates.  Prevents extremely popular memories from
            dominating results.
    """

    def __init__(
        self,
        weights: RelevanceWeights | None = None,
        max_recency_days: float = 30.0,
        max_access_count: int = 100,
    ) -> None:
        self.weights = weights or RelevanceWeights()
        self.max_recency_days = max(1.0, max_recency_days)
        self.max_access_count = max(1, max_access_count)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score(
        self,
        memory: Memory,
        query_embedding: list[float] | None = None,
        now: datetime | None = None,
    ) -> float:
        """Compute a composite relevance score for a single memory.

        The score is a weighted combination of:

        1. **Semantic similarity** -- cosine similarity between the
           query embedding and the memory's embedding.
        2. **Recency** -- exponential decay based on the time since the
           memory was last updated.
        3. **Importance** -- the memory's stored importance value.
        4. **Frequency** -- normalised access count.

        Args:
            memory: The memory to score.
            query_embedding: The embedding of the recall query.  If
                ``None`` or empty, the semantic component is set to 0.
            now: The current time.  Defaults to UTC now.

        Returns:
            A float in approximately ``[0, 1]``, though values slightly
            above 1 are possible depending on weight configuration.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        w = self.weights
        total_weight = w.total()
        if total_weight == 0:
            return 0.0

        # 1. Semantic similarity ----------------------------------------
        sem_score = 0.0
        if (
            query_embedding
            and memory.embedding
            and len(query_embedding) == len(memory.embedding)
        ):
            raw = cosine_similarity(query_embedding, memory.embedding)
            # Shift from [-1, 1] to [0, 1]
            sem_score = (raw + 1.0) / 2.0

        # 2. Recency ----------------------------------------------------
        updated = memory.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        delta_seconds = max(0.0, (now - updated).total_seconds())
        days_since = delta_seconds / 86400.0
        recency_score = math.exp(-days_since / self.max_recency_days)

        # 3. Importance -------------------------------------------------
        importance_score = memory.importance  # already in [0, 1]

        # 4. Access frequency -------------------------------------------
        freq_score = min(memory.access_count / self.max_access_count, 1.0)

        # Weighted combination ------------------------------------------
        combined = (
            w.semantic * sem_score
            + w.recency * recency_score
            + w.importance * importance_score
            + w.frequency * freq_score
        ) / total_weight

        return combined

    # ------------------------------------------------------------------
    # Decay
    # ------------------------------------------------------------------

    def apply_decay(
        self,
        memories: Sequence[Memory],
        now: datetime | None = None,
    ) -> list[Memory]:
        """Apply time-based importance decay to a collection of memories.

        The decay formula is::

            new_importance = importance * exp(-decay_rate * days_since_update)

        Memories with ``decay_rate == 0`` are unaffected.

        This method **mutates** the ``importance`` and ``updated_at``
        fields of each memory in-place and also returns the list for
        convenience.

        Args:
            memories: Memories to decay.
            now: The current time.  Defaults to UTC now.

        Returns:
            The same list of memories with updated importance values.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        result: list[Memory] = []
        for mem in memories:
            updated = mem.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            delta_seconds = max(0.0, (now - updated).total_seconds())
            days = delta_seconds / 86400.0

            if mem.decay_rate > 0 and days > 0:
                mem.importance = mem.importance * math.exp(
                    -mem.decay_rate * days
                )
                # Clamp to [0, 1].
                mem.importance = max(0.0, min(1.0, mem.importance))

            result.append(mem)

        return result

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank(
        self,
        memories: Sequence[Memory],
        query_embedding: list[float] | None = None,
        k: int = 5,
        min_relevance: float = 0.0,
        now: datetime | None = None,
    ) -> list[Memory]:
        """Return the top-*k* most relevant memories.

        Memories are scored via :meth:`score`, filtered by
        *min_relevance*, sorted in descending order, and truncated to
        *k* results.

        Args:
            memories: Candidate memories to rank.
            query_embedding: Embedding of the recall query.
            k: Maximum number of results to return.
            min_relevance: Discard memories scoring below this threshold.
            now: The current time.

        Returns:
            Up to *k* memories sorted by descending relevance.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        scored: list[tuple[float, Memory]] = []
        for mem in memories:
            s = self.score(mem, query_embedding=query_embedding, now=now)
            if s >= min_relevance:
                scored.append((s, mem))

        # Sort descending by score, then by updated_at as tie-breaker.
        scored.sort(key=lambda pair: (pair[0], pair[1].updated_at), reverse=True)

        return [mem for _, mem in scored[:k]]

    def __repr__(self) -> str:  # pragma: no cover
        w = self.weights
        return (
            f"RelevanceEngine(semantic={w.semantic}, recency={w.recency}, "
            f"importance={w.importance}, frequency={w.frequency})"
        )
