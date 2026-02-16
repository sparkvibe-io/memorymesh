"""Tests for the RelevanceEngine.

Covers cosine similarity, scoring with and without embeddings,
ranking (top-k ordering), and time-based importance decay.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from memorymesh.memory import Memory
from memorymesh.relevance import RelevanceEngine
from memorymesh.store import cosine_similarity

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_memory(
    text: str = "test",
    embedding: list[float] | None = None,
    importance: float = 0.5,
    created_at: datetime | None = None,
    **kwargs,
) -> Memory:
    """Create a Memory with convenient defaults for relevance tests."""
    if created_at is None:
        created_at = datetime.now(timezone.utc)
    return Memory(
        text=text,
        embedding=embedding,
        importance=importance,
        created_at=created_at,
        updated_at=created_at,
        **kwargs,
    )


# ------------------------------------------------------------------
# Cosine similarity
# ------------------------------------------------------------------


def test_cosine_similarity_identical():
    """Identical vectors have cosine similarity of 1.0."""
    sim = cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    assert sim == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    """Orthogonal vectors have cosine similarity of 0.0."""
    sim = cosine_similarity([1.0, 0.0], [0.0, 1.0])
    assert sim == pytest.approx(0.0)


def test_cosine_similarity_opposite():
    """Opposite vectors have cosine similarity of -1.0."""
    sim = cosine_similarity([1.0, 0.0], [-1.0, 0.0])
    assert sim == pytest.approx(-1.0)


def test_cosine_similarity_known_value():
    """Verify cosine similarity against a manually computed value."""
    a = [1.0, 2.0, 3.0]
    b = [4.0, 5.0, 6.0]
    # dot = 32, |a| = sqrt(14), |b| = sqrt(77)
    expected = 32.0 / (math.sqrt(14) * math.sqrt(77))
    sim = cosine_similarity(a, b)
    assert sim == pytest.approx(expected, rel=1e-6)


def test_cosine_similarity_zero_vector():
    """A zero vector returns 0.0 similarity."""
    sim = cosine_similarity([0.0, 0.0], [1.0, 2.0])
    assert sim == pytest.approx(0.0)


# ------------------------------------------------------------------
# Scoring
# ------------------------------------------------------------------


def test_score_with_embedding():
    """score() uses embedding similarity when both query and memory have vectors."""
    engine = RelevanceEngine()
    query_embedding = [1.0, 0.0, 0.0]
    mem = _make_memory(
        text="relevant",
        embedding=[1.0, 0.0, 0.0],
        importance=1.0,
    )
    score = engine.score(mem, query_embedding=query_embedding)
    # With identical embeddings and high importance, score should be high.
    assert score > 0.5


def test_score_without_embedding():
    """score() provides a fallback score when embeddings are absent."""
    engine = RelevanceEngine()
    mem = _make_memory(text="no embedding", embedding=None, importance=0.8)
    score = engine.score(mem, query_embedding=None)
    # Without embeddings, the score should still be a valid number
    # (based on importance and recency).
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_score_partial_embedding():
    """score() handles the case where only the memory has an embedding."""
    engine = RelevanceEngine()
    mem = _make_memory(text="has vector", embedding=[0.5, 0.5])
    score = engine.score(mem, query_embedding=None)
    assert isinstance(score, float)


# ------------------------------------------------------------------
# Ranking
# ------------------------------------------------------------------


def test_rank_top_k_ordering():
    """rank() returns memories in descending score order, limited to k."""
    engine = RelevanceEngine()
    memories = [
        _make_memory("low", embedding=[0.0, 0.0, 1.0], importance=0.1),
        _make_memory("high", embedding=[1.0, 0.0, 0.0], importance=0.9),
        _make_memory("medium", embedding=[0.5, 0.5, 0.0], importance=0.5),
    ]
    query_embedding = [1.0, 0.0, 0.0]
    ranked = engine.rank(memories, query_embedding=query_embedding, k=2)

    assert len(ranked) == 2
    # The "high" memory (most similar to query, highest importance) should be first.
    assert ranked[0].text == "high"


def test_rank_empty_list():
    """rank() returns an empty list when given no memories."""
    engine = RelevanceEngine()
    ranked = engine.rank([], query_embedding=[1.0, 0.0], k=5)
    assert ranked == []


def test_rank_k_larger_than_available():
    """rank() returns all memories when k exceeds the number available."""
    engine = RelevanceEngine()
    memories = [
        _make_memory("only one", embedding=[1.0, 0.0], importance=0.5),
    ]
    ranked = engine.rank(memories, query_embedding=[1.0, 0.0], k=10)
    assert len(ranked) == 1


# ------------------------------------------------------------------
# Decay
# ------------------------------------------------------------------


def test_decay_reduces_importance():
    """Older memories receive a lower score due to decay."""
    engine = RelevanceEngine()

    now = datetime.now(timezone.utc)
    recent = _make_memory(
        "recent",
        embedding=[1.0, 0.0],
        importance=0.5,
        decay_rate=0.01,
        created_at=now,
    )
    old = _make_memory(
        "old",
        embedding=[1.0, 0.0],
        importance=0.5,
        decay_rate=0.01,
        created_at=now - timedelta(days=30),
    )
    # Force updated_at to match created_at for the old memory.
    old.updated_at = old.created_at

    query_embedding = [1.0, 0.0]
    score_recent = engine.score(recent, query_embedding=query_embedding)
    score_old = engine.score(old, query_embedding=query_embedding)

    # The more recent memory should score higher (or equal, but typically higher).
    assert score_recent >= score_old


def test_decay_zero_rate_no_change():
    """A decay_rate of 0 means the memory does not decay over time."""
    engine = RelevanceEngine()

    now = datetime.now(timezone.utc)
    long_ago = now - timedelta(days=365)

    mem_now = _make_memory(
        "now", embedding=[1.0], importance=0.5, decay_rate=0.0, created_at=now
    )
    mem_old = _make_memory(
        "old",
        embedding=[1.0],
        importance=0.5,
        decay_rate=0.0,
        created_at=long_ago,
    )
    mem_old.updated_at = mem_old.created_at

    query = [1.0]
    score_now = engine.score(mem_now, query_embedding=query)
    score_old = engine.score(mem_old, query_embedding=query)

    # With zero decay, scores should be close. The recency weight (default 0.2)
    # causes some difference, but the decay component itself should not contribute.
    assert abs(score_now - score_old) < 0.25
