"""Tests for the Memory dataclass.

Covers construction, default values, validation, and round-trip
serialization via to_dict / from_dict.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from memorymesh.memory import Memory

# ------------------------------------------------------------------
# Creation and defaults
# ------------------------------------------------------------------


def test_memory_creation():
    """A Memory can be created with just the required 'text' field."""
    mem = Memory(text="Hello, world!")
    assert mem.text == "Hello, world!"
    assert isinstance(mem.id, str)
    assert len(mem.id) == 32  # uuid4().hex is 32 hex chars


def test_memory_defaults():
    """Default values are sensible when only text is provided."""
    mem = Memory(text="Test defaults")

    # ID: non-empty hex string.
    assert len(mem.id) > 0
    int(mem.id, 16)  # valid hex

    # Timestamps: timezone-aware UTC datetimes.
    assert mem.created_at.tzinfo is not None
    assert mem.updated_at.tzinfo is not None

    # Importance defaults to 0.5.
    assert mem.importance == 0.5

    # Decay rate defaults to 0.01.
    assert mem.decay_rate == 0.01

    # Access count starts at 0.
    assert mem.access_count == 0

    # Metadata defaults to empty dict.
    assert mem.metadata == {}

    # Embedding defaults to None.
    assert mem.embedding is None


def test_memory_validation_empty_text():
    """An empty text string raises ValueError."""
    with pytest.raises(ValueError, match="text must not be empty"):
        Memory(text="")


def test_memory_importance_clamped():
    """Importance is clamped to [0, 1]."""
    low = Memory(text="low", importance=-0.5)
    assert low.importance == 0.0

    high = Memory(text="high", importance=1.5)
    assert high.importance == 1.0


def test_memory_decay_rate_non_negative():
    """Decay rate is clamped to non-negative values."""
    mem = Memory(text="test", decay_rate=-0.1)
    assert mem.decay_rate == 0.0


# ------------------------------------------------------------------
# Serialization: to_dict / from_dict
# ------------------------------------------------------------------


def test_memory_to_dict():
    """to_dict() produces a JSON-serializable dictionary."""
    mem = Memory(
        text="Serialize me",
        metadata={"key": "value"},
        importance=0.8,
    )
    d = mem.to_dict()

    assert d["text"] == "Serialize me"
    assert d["metadata"] == {"key": "value"}
    assert d["importance"] == 0.8
    assert d["id"] == mem.id

    # Datetimes should be ISO-8601 strings.
    assert isinstance(d["created_at"], str)
    assert isinstance(d["updated_at"], str)
    # Should be parseable back.
    datetime.fromisoformat(d["created_at"])
    datetime.fromisoformat(d["updated_at"])


def test_memory_from_dict():
    """from_dict() reconstructs a Memory from a to_dict() output."""
    original = Memory(
        text="Round trip",
        metadata={"version": 2},
        importance=0.7,
        access_count=3,
        embedding=[0.1, 0.2, 0.3],
    )
    d = original.to_dict()
    restored = Memory.from_dict(d)

    assert restored.id == original.id
    assert restored.text == original.text
    assert restored.metadata == original.metadata
    assert restored.importance == original.importance
    assert restored.access_count == original.access_count
    assert restored.embedding == pytest.approx(original.embedding)
    assert restored.created_at == original.created_at
    assert restored.updated_at == original.updated_at


def test_memory_from_dict_json_metadata():
    """from_dict() handles metadata stored as a JSON string (DB rows)."""
    d = {
        "text": "From DB",
        "id": "abc123",
        "metadata": '{"source": "db"}',
        "created_at": "2025-01-15T10:30:00+00:00",
        "updated_at": "2025-01-15T10:30:00+00:00",
        "access_count": 0,
        "importance": 0.5,
        "decay_rate": 0.01,
        "embedding": None,
    }
    mem = Memory.from_dict(d)
    assert mem.metadata == {"source": "db"}
    assert isinstance(mem.created_at, datetime)


def test_memory_json_round_trip():
    """to_json() and from_json() produce a faithful round trip."""
    original = Memory(text="JSON round trip", metadata={"a": 1})
    json_str = original.to_json()
    restored = Memory.from_json(json_str)

    assert restored.id == original.id
    assert restored.text == original.text
    assert restored.metadata == original.metadata
