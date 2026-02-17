"""Schema migration system for MemoryMesh.

Uses SQLite's built-in ``PRAGMA user_version`` to track schema versions.
Migrations are additive-only -- no destructive changes are ever applied.

Usage::

    from memorymesh.migrations import ensure_schema

    conn = sqlite3.connect("memories.db")
    version = ensure_schema(conn)
"""

from __future__ import annotations

import logging
import sqlite3
from typing import NamedTuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Migration definition
# ---------------------------------------------------------------------------


class Migration(NamedTuple):
    """A single schema migration step.

    Attributes:
        version: The target schema version after this migration.
        description: Human-readable description of the change.
        statements: SQL statements to execute.  May be empty for the
            initial version (which just stamps an existing schema).
    """

    version: int
    description: str
    statements: list[str]


# ---------------------------------------------------------------------------
# Full schema (for fresh installs)
# ---------------------------------------------------------------------------

_FULL_SCHEMA: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS memories (
        id             TEXT PRIMARY KEY,
        text           TEXT    NOT NULL,
        metadata_json  TEXT    NOT NULL DEFAULT '{}',
        embedding_blob BLOB,
        created_at     TEXT    NOT NULL,
        updated_at     TEXT    NOT NULL,
        access_count   INTEGER NOT NULL DEFAULT 0,
        importance     REAL    NOT NULL DEFAULT 0.5,
        decay_rate     REAL    NOT NULL DEFAULT 0.01
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memories_importance
    ON memories (importance DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memories_updated_at
    ON memories (updated_at DESC);
    """,
]

# ---------------------------------------------------------------------------
# Migration list (incremental upgrades)
# ---------------------------------------------------------------------------

MIGRATIONS: list[Migration] = [
    Migration(
        version=1,
        description="Initial schema (v0.1.0)",
        statements=[],  # Schema already exists for both fresh and pre-migration DBs
    ),
]

LATEST_VERSION: int = MIGRATIONS[-1].version


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Read the current schema version from the database.

    Args:
        conn: An open SQLite connection.

    Returns:
        The ``user_version`` PRAGMA value (``0`` if never set).
    """
    cur = conn.execute("PRAGMA user_version")
    row = cur.fetchone()
    return row[0] if row else 0


def ensure_schema(conn: sqlite3.Connection) -> int:
    """Ensure the database schema is up to date.

    Handles three cases:

    1. **Fresh database** -- no ``memories`` table exists and
       ``user_version`` is ``0``.  Executes the full schema DDL and stamps
       the database at :data:`LATEST_VERSION`.
    2. **Pre-migration database** -- the ``memories`` table exists but
       ``user_version`` is ``0`` (created before the migration system).
       Stamps as version 1, then applies any pending migrations.
    3. **Previously migrated database** -- applies only migrations whose
       version exceeds the current ``user_version``.

    Each migration runs inside a transaction.  If a migration fails, the
    version is **not** bumped and the next call will retry.

    Args:
        conn: An open SQLite connection.

    Returns:
        The schema version after all migrations have been applied.
    """
    current = get_schema_version(conn)

    # Case 3b: downgraded library -- version higher than we know about
    if current > LATEST_VERSION:
        logger.warning(
            "Database schema version (%d) is newer than the library supports (%d). "
            "Skipping migrations. Consider upgrading MemoryMesh.",
            current,
            LATEST_VERSION,
        )
        return current

    # Case 1: Fresh database
    if not _table_exists(conn, "memories") and current == 0:
        logger.debug("Fresh database detected -- creating schema at version %d", LATEST_VERSION)
        for stmt in _FULL_SCHEMA:
            conn.execute(stmt)
        conn.execute(f"PRAGMA user_version = {LATEST_VERSION}")
        conn.commit()
        return LATEST_VERSION

    # Case 2: Pre-migration database (table exists, version 0)
    if current == 0:
        logger.debug("Pre-migration database detected -- stamping as version 1")
        current = 1
        conn.execute(f"PRAGMA user_version = {current}")
        conn.commit()

    # Case 3: Apply pending migrations
    for migration in MIGRATIONS:
        if migration.version <= current:
            continue
        logger.info(
            "Applying migration v%d: %s", migration.version, migration.description
        )
        try:
            for stmt in migration.statements:
                conn.execute(stmt)
            conn.execute(f"PRAGMA user_version = {migration.version}")
            conn.commit()
            current = migration.version
        except Exception:
            conn.rollback()
            logger.exception("Migration v%d failed -- rolling back", migration.version)
            raise

    return current


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check whether a table exists in the database.

    Args:
        conn: An open SQLite connection.
        table_name: The table name to look for.

    Returns:
        ``True`` if the table exists, ``False`` otherwise.
    """
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None
