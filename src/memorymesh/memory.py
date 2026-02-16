"""Memory data model for MemoryMesh.

Defines the core Memory dataclass used throughout the library to represent
a single unit of stored knowledge.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _new_id() -> str:
    """Generate a new unique memory identifier."""
    return uuid.uuid4().hex


@dataclass
class Memory:
    """A single unit of memory stored in MemoryMesh.

    Attributes:
        id: Unique identifier (hex UUID). Auto-generated if not provided.
        text: The textual content of the memory.
        metadata: Arbitrary key-value metadata attached to this memory.
        embedding: Vector embedding of the text, or ``None`` if not yet computed.
        created_at: Timestamp when the memory was first stored (UTC).
        updated_at: Timestamp of the most recent update (UTC).
        access_count: Number of times this memory has been recalled.
        importance: User-assigned importance score in the range ``[0, 1]``.
        decay_rate: Rate at which importance decays over time.  Higher values
            cause faster forgetting.  ``0`` means the memory never decays.
    """

    text: str
    id: str = field(default_factory=_new_id)
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    access_count: int = 0
    importance: float = 0.5
    decay_rate: float = 0.01

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Validate field values after initialisation."""
        if not self.text:
            raise ValueError("Memory text must not be empty.")
        self.importance = max(0.0, min(1.0, float(self.importance)))
        self.decay_rate = max(0.0, float(self.decay_rate))

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the memory to a plain dictionary.

        Datetimes are converted to ISO-8601 strings and the embedding is
        included as-is (list of floats or ``None``).

        Returns:
            A JSON-safe dictionary representation of this memory.
        """
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        """Reconstruct a Memory from a dictionary.

        Accepts the output of :meth:`to_dict` as well as raw database rows
        where datetimes are stored as ISO-8601 strings.

        Args:
            data: Dictionary with memory fields.

        Returns:
            A new :class:`Memory` instance.
        """
        d = dict(data)  # shallow copy so we don't mutate the caller's dict

        for key in ("created_at", "updated_at"):
            val = d.get(key)
            if isinstance(val, str):
                d[key] = datetime.fromisoformat(val)

        # Handle metadata stored as JSON string (from DB rows).
        meta = d.get("metadata")
        if isinstance(meta, str):
            d["metadata"] = json.loads(meta)

        return cls(**d)

    def to_json(self) -> str:
        """Serialise the memory to a JSON string.

        Returns:
            A compact JSON string.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> Memory:
        """Reconstruct a Memory from a JSON string.

        Args:
            raw: A JSON string produced by :meth:`to_json`.

        Returns:
            A new :class:`Memory` instance.
        """
        return cls.from_dict(json.loads(raw))

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        preview = self.text[:60] + ("..." if len(self.text) > 60 else "")
        return (
            f"Memory(id={self.id!r}, text={preview!r}, "
            f"importance={self.importance:.2f}, "
            f"access_count={self.access_count})"
        )
