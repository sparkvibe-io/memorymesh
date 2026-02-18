"""SQLite storage backend for MemoryMesh.

Provides durable, thread-safe persistence of :class:`Memory` objects in a
local SQLite database.  No external server is required.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import sqlite3
import struct
import threading
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from .memory import Memory

# ---------------------------------------------------------------------------
# Default database location
# ---------------------------------------------------------------------------

_DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".memorymesh")
_DEFAULT_DB = os.path.join(_DEFAULT_DIR, "memories.db")

_DEFAULT_GLOBAL_DIR = _DEFAULT_DIR
_DEFAULT_GLOBAL_DB = os.path.join(_DEFAULT_GLOBAL_DIR, "global.db")
_LEGACY_DB = _DEFAULT_DB


def detect_project_root(roots: list[dict[str, Any]] | None = None) -> str | None:
    """Detect the project root directory.

    Priority:
        1. First URI in *roots* (from the MCP ``initialize`` request).
        2. ``MEMORYMESH_PROJECT_ROOT`` environment variable.
        3. Current working directory (if it contains a ``.git`` directory
           or a ``pyproject.toml`` file, indicating it is a project root).
        4. ``None`` -- no project root detected.

    Args:
        roots: The ``roots`` list from the MCP ``initialize`` params.

    Returns:
        An absolute directory path, or ``None``.
    """
    # 1. MCP roots
    if roots:
        uri = roots[0].get("uri", "")
        if uri.startswith("file://"):
            parsed = urlparse(uri)
            # url2pathname handles platform-specific conversion
            # (e.g. /C:/Users/... → C:\Users\... on Windows).
            path = url2pathname(unquote(parsed.path))
            if os.path.isdir(path):
                return os.path.realpath(path)

    # 2. Environment variable
    env_root = os.environ.get("MEMORYMESH_PROJECT_ROOT")
    if env_root and os.path.isdir(env_root):
        return os.path.realpath(env_root)

    # 3. CWD heuristic
    cwd = os.getcwd()
    if os.path.isdir(os.path.join(cwd, ".git")) or os.path.isfile(
        os.path.join(cwd, "pyproject.toml")
    ):
        return os.path.realpath(cwd)

    return None


def migrate_legacy_db() -> bool:
    """Migrate the legacy ``memories.db`` to ``global.db`` (one-time).

    If ``global.db`` does not exist but the legacy ``memories.db`` does,
    rename it so that existing data becomes the global store.

    Returns:
        ``True`` if a migration was performed, ``False`` otherwise.
    """
    if os.path.exists(_LEGACY_DB) and not os.path.exists(_DEFAULT_GLOBAL_DB):
        os.makedirs(_DEFAULT_GLOBAL_DIR, mode=0o700, exist_ok=True)
        os.rename(_LEGACY_DB, _DEFAULT_GLOBAL_DB)
        return True
    return False


def _pack_embedding(embedding: list[float] | None) -> bytes | None:
    """Pack a list of floats into a compact binary blob (little-endian f32).

    Args:
        embedding: Vector of floats, or ``None``.

    Returns:
        Raw bytes suitable for SQLite BLOB storage, or ``None``.
    """
    if embedding is None or len(embedding) == 0:
        return None
    return struct.pack(f"<{len(embedding)}f", *embedding)


def _unpack_embedding(blob: bytes | None) -> list[float] | None:
    """Unpack a binary blob back into a list of floats.

    Args:
        blob: Raw bytes previously created by :func:`_pack_embedding`, or
            ``None``.

    Returns:
        A list of floats, or ``None``.
    """
    if blob is None:
        return None
    count = len(blob) // 4  # 4 bytes per float32
    return list(struct.unpack(f"<{count}f", blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors in pure Python.

    Falls back to this implementation when NumPy is not available.  When
    NumPy *is* available the caller may choose to use it instead for
    performance, but this function is always correct and has zero
    dependencies.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Cosine similarity in the range ``[-1, 1]``.  Returns ``0.0`` if
        either vector has zero magnitude.
    """
    if len(a) != len(b):
        raise ValueError(f"Vectors must be the same length (got {len(a)} and {len(b)}).")

    dot = 0.0
    mag_a = 0.0
    mag_b = 0.0
    for ai, bi in zip(a, b):
        dot += ai * bi
        mag_a += ai * ai
        mag_b += bi * bi

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return dot / (math.sqrt(mag_a) * math.sqrt(mag_b))


class MemoryStore:
    """Thread-safe SQLite storage for :class:`Memory` objects.

    Each instance manages a single SQLite database file.  The class uses
    per-thread connections to satisfy SQLite's threading constraints.

    Args:
        path: Path to the SQLite database file.  Parent directories are
            created automatically.  Defaults to
            ``~/.memorymesh/memories.db``.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        raw_path = str(path) if path is not None else _DEFAULT_DB
        # Canonicalise and resolve symlinks to prevent traversal attacks.
        self._path = os.path.realpath(os.path.expanduser(raw_path))
        self._local = threading.local()

        # Ensure parent directory exists with restrictive permissions.
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, mode=0o700, exist_ok=True)
            with contextlib.suppress(OSError):
                os.chmod(parent, 0o700)

        # Initialise schema via the migration system.
        from .migrations import ensure_schema

        conn = self._get_connection()
        self._schema_version = ensure_schema(conn)

    @property
    def schema_version(self) -> int:
        """The current schema version of this database.

        Returns:
            An integer representing the schema version.
        """
        return self._schema_version

    # ------------------------------------------------------------------
    # Connection management (per-thread)
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """Return (or create) a SQLite connection for the current thread."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._path)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager that yields a cursor and commits on success."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, memory: Memory) -> None:
        """Insert or replace a memory.

        If a memory with the same ``id`` already exists it is fully
        overwritten.

        Args:
            memory: The :class:`Memory` to persist.
        """
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO memories
                    (id, text, metadata_json, embedding_blob,
                     created_at, updated_at, access_count,
                     importance, decay_rate, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.text,
                    json.dumps(memory.metadata, ensure_ascii=False),
                    _pack_embedding(memory.embedding),
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                    memory.access_count,
                    memory.importance,
                    memory.decay_rate,
                    memory.session_id,
                ),
            )

    def get(self, memory_id: str) -> Memory | None:
        """Retrieve a single memory by its ID.

        Args:
            memory_id: The unique identifier of the memory.

        Returns:
            The :class:`Memory` if found, otherwise ``None``.
        """
        with self._cursor() as cur:
            cur.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_memory(row)

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by its ID.

        Args:
            memory_id: The unique identifier of the memory to remove.

        Returns:
            ``True`` if a row was deleted, ``False`` if the ID was not found.
        """
        with self._cursor() as cur:
            cur.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    def search_by_text(self, query: str, limit: int = 20) -> list[Memory]:
        """Search memories by substring match (case-insensitive).

        This is a simple ``LIKE`` search intended as a fallback when
        embeddings are not available.

        Args:
            query: The search string.
            limit: Maximum number of results.

        Returns:
            A list of matching :class:`Memory` objects ordered by recency.
        """
        # Escape LIKE wildcards so they are matched literally.
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM memories
                WHERE text LIKE ? ESCAPE '\\'
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (pattern, limit),
            )
            rows = cur.fetchall()
        return [self._row_to_memory(r) for r in rows]

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        """List memories with pagination.

        Args:
            limit: Maximum number of memories to return.
            offset: Number of rows to skip.

        Returns:
            A list of :class:`Memory` objects ordered by most recently
            updated first.
        """
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM memories
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get_all_with_embeddings(self, limit: int = 10_000) -> list[Memory]:
        """Return memories that have a non-NULL embedding.

        Used internally by the recall pipeline to perform vector search.

        Args:
            limit: Maximum number of memories to return. Defaults to 10,000
                to prevent loading excessively large datasets into memory.

        Returns:
            A list of :class:`Memory` objects that have embeddings.
        """
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM memories WHERE embedding_blob IS NOT NULL LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get_by_session(self, session_id: str, limit: int = 100) -> list[Memory]:
        """Retrieve all memories belonging to a specific session.

        Args:
            session_id: The session identifier to filter by.
            limit: Maximum number of results.

        Returns:
            A list of :class:`Memory` objects ordered by creation time.
        """
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM memories
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = cur.fetchall()
        return [self._row_to_memory(r) for r in rows]

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List distinct sessions with summary statistics.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            A list of dicts with keys ``session_id``, ``count``,
            ``first_at``, and ``last_at``, ordered by most recent
            session first.
        """
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT session_id,
                       COUNT(*) AS cnt,
                       MIN(created_at) AS first_at,
                       MAX(created_at) AS last_at
                FROM memories
                WHERE session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY last_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {
                "session_id": row["session_id"],
                "count": row["cnt"],
                "first_at": row["first_at"],
                "last_at": row["last_at"],
            }
            for row in rows
        ]

    def count(self) -> int:
        """Return the total number of stored memories.

        Returns:
            Row count as an integer.
        """
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memories")
            result = cur.fetchone()
        return result[0] if result else 0

    def get_time_range(self) -> tuple[str | None, str | None]:
        """Return the oldest and newest created_at timestamps.

        Uses a single efficient SQL query instead of loading all memories.

        Returns:
            A tuple of ``(oldest_iso, newest_iso)`` ISO-8601 strings,
            or ``(None, None)`` if the database is empty.
        """
        with self._cursor() as cur:
            cur.execute("SELECT MIN(created_at), MAX(created_at) FROM memories")
            row = cur.fetchone()
        if row is None or row[0] is None:
            return (None, None)
        return (row[0], row[1])

    def clear(self) -> int:
        """Delete **all** memories from the database.

        Returns:
            The number of rows deleted.
        """
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memories")
            total = cur.fetchone()[0]
            cur.execute("DELETE FROM memories")
        return total

    def update_access(self, memory_id: str) -> None:
        """Increment access_count and refresh updated_at for a memory.

        Args:
            memory_id: The unique identifier of the memory.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE memories
                SET access_count = access_count + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, memory_id),
            )

    def close(self) -> None:
        """Close the current thread's database connection, if open."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> Memory:
        """Convert a database row into a :class:`Memory` instance."""
        return Memory(
            id=row["id"],
            text=row["text"],
            metadata=json.loads(row["metadata_json"]),
            embedding=_unpack_embedding(row["embedding_blob"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            access_count=row["access_count"],
            importance=row["importance"],
            decay_rate=row["decay_rate"],
            session_id=row["session_id"],
        )

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> MemoryStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()

    def __repr__(self) -> str:  # pragma: no cover
        return f"MemoryStore(path={self._path!r})"
