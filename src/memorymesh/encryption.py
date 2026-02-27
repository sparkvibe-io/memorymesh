"""Application-level encryption for MemoryMesh storage at rest.

Provides optional encryption of sensitive memory fields (text and metadata)
before they are persisted to SQLite.  Uses only Python standard library
modules -- no external cryptography packages are required.

**Security note:** This module provides protection against casual inspection
of database files at rest (e.g. someone browsing your filesystem).  It is
NOT a substitute for full-disk encryption or a battle-tested cryptographic
library.  The cipher uses HMAC-SHA256 in CTR mode for confidentiality and
HMAC-SHA256 for authentication -- both are standard constructions, but this
implementation has not been independently audited.

Typical usage::

    from memorymesh import MemoryMesh

    mem = MemoryMesh(path="project.db", encryption_key="my secret passphrase")
    mem.remember("sensitive data")
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import struct
from typing import Any

from .memory import Memory
from .store import MemoryStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SALT_LENGTH = 16  # 128-bit salt
_KEY_LENGTH = 32  # 256-bit derived key
_IV_LENGTH = 16  # 128-bit initialisation vector
_TAG_LENGTH = 32  # 256-bit HMAC-SHA256 tag
_PBKDF2_ITERATIONS = 100_000  # OWASP-recommended minimum for PBKDF2-SHA256

# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit encryption key from a password and salt.

    Uses PBKDF2-HMAC-SHA256 with 100,000 iterations (OWASP recommended
    minimum).

    Args:
        password: The user-provided passphrase.
        salt: A random 16-byte salt.  Must be stored alongside the
            encrypted data so the same key can be derived later.

    Returns:
        A 32-byte (256-bit) derived key.
    """
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=_KEY_LENGTH,
    )


# ---------------------------------------------------------------------------
# Authenticated encryption (HMAC-SHA256 CTR mode)
# ---------------------------------------------------------------------------


def _keystream_block(key: bytes, iv: bytes, counter: int) -> bytes:
    """Generate a 32-byte keystream block using HMAC-SHA256 in CTR mode.

    Args:
        key: The 32-byte encryption key.
        iv: The 16-byte initialisation vector.
        counter: Block counter (0-indexed).

    Returns:
        A 32-byte keystream block.
    """
    # CTR input = IV || counter (big-endian 4 bytes)
    ctr_input = iv + struct.pack(">I", counter)
    return hmac.new(key, ctr_input, hashlib.sha256).digest()


def _xor_bytes(data: bytes, keystream: bytes) -> bytes:
    """XOR *data* with *keystream* (must be at least as long as *data*)."""
    return bytes(a ^ b for a, b in zip(data, keystream))


def encrypt_field(plaintext: str, key: bytes) -> str:
    """Encrypt a string field with authenticated encryption.

    The scheme:
        1. Generate a random 16-byte IV.
        2. Generate keystream via HMAC-SHA256 in CTR mode.
        3. XOR plaintext bytes with the keystream to produce ciphertext.
        4. Compute an HMAC-SHA256 tag over ``IV || ciphertext``.
        5. Return ``base64(IV || ciphertext || tag)``.

    Args:
        plaintext: The string to encrypt.
        key: The 32-byte encryption key from :func:`derive_key`.

    Returns:
        A base64-encoded string containing ``IV + ciphertext + HMAC tag``.
    """
    plaintext_bytes = plaintext.encode("utf-8")
    iv = os.urandom(_IV_LENGTH)

    # Generate keystream and encrypt.
    ciphertext = bytearray()
    offset = 0
    counter = 0
    while offset < len(plaintext_bytes):
        block = _keystream_block(key, iv, counter)
        chunk = plaintext_bytes[offset : offset + len(block)]
        ciphertext.extend(_xor_bytes(chunk, block))
        offset += len(block)
        counter += 1

    ciphertext_bytes = bytes(ciphertext)

    # Compute authentication tag over IV || ciphertext.
    tag = hmac.new(key, iv + ciphertext_bytes, hashlib.sha256).digest()

    return base64.b64encode(iv + ciphertext_bytes + tag).decode("ascii")


def decrypt_field(ciphertext_b64: str, key: bytes) -> str:
    """Decrypt a field previously encrypted with :func:`encrypt_field`.

    Args:
        ciphertext_b64: The base64-encoded string from :func:`encrypt_field`.
        key: The same 32-byte key used for encryption.

    Returns:
        The decrypted plaintext string.

    Raises:
        ValueError: If the ciphertext is too short or the authentication
            tag does not match (indicating tampering or a wrong key).
    """
    raw = base64.b64decode(ciphertext_b64)

    if len(raw) < _IV_LENGTH + _TAG_LENGTH:
        raise ValueError("Ciphertext too short to contain IV and authentication tag.")

    iv = raw[:_IV_LENGTH]
    tag = raw[-_TAG_LENGTH:]
    ciphertext_bytes = raw[_IV_LENGTH:-_TAG_LENGTH]

    # Verify authentication tag BEFORE decrypting (encrypt-then-MAC).
    expected_tag = hmac.new(key, iv + ciphertext_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError(
            "Authentication failed: ciphertext has been tampered with or key is wrong."
        )

    # Decrypt via XOR with identical keystream.
    plaintext = bytearray()
    offset = 0
    counter = 0
    while offset < len(ciphertext_bytes):
        block = _keystream_block(key, iv, counter)
        chunk = ciphertext_bytes[offset : offset + len(block)]
        plaintext.extend(_xor_bytes(chunk, block))
        offset += len(block)
        counter += 1

    return bytes(plaintext).decode("utf-8")


# ---------------------------------------------------------------------------
# Meta table helpers (salt storage)
# ---------------------------------------------------------------------------

_META_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS memorymesh_meta (
    key   TEXT PRIMARY KEY,
    value BLOB NOT NULL
);
"""


def _ensure_meta_table(conn: sqlite3.Connection) -> None:
    """Create the ``memorymesh_meta`` table if it does not exist.

    Args:
        conn: An open SQLite connection.
    """
    conn.execute(_META_TABLE_DDL)
    conn.commit()


def _get_or_create_salt(conn: sqlite3.Connection) -> bytes:
    """Retrieve the encryption salt, creating one on first use.

    The salt is stored in the ``memorymesh_meta`` table under the key
    ``"encryption_salt"``.  If no salt exists yet, a random 16-byte salt
    is generated and persisted.

    Args:
        conn: An open SQLite connection.

    Returns:
        A 16-byte salt.
    """
    _ensure_meta_table(conn)

    cur = conn.execute(
        "SELECT value FROM memorymesh_meta WHERE key = ?",
        ("encryption_salt",),
    )
    row = cur.fetchone()
    if row is not None:
        return bytes(row[0])

    salt = os.urandom(_SALT_LENGTH)
    conn.execute(
        "INSERT INTO memorymesh_meta (key, value) VALUES (?, ?)",
        ("encryption_salt", salt),
    )
    conn.commit()
    return salt


# ---------------------------------------------------------------------------
# Encrypted store wrapper
# ---------------------------------------------------------------------------


class EncryptedMemoryStore:
    """A wrapper around :class:`MemoryStore` that encrypts fields at rest.

    Encrypts the ``text`` and ``metadata_json`` fields before writing and
    decrypts them after reading.  Other fields (``id``, timestamps,
    ``importance``, ``decay_rate``, ``access_count``, ``session_id``,
    ``embedding_blob``) are stored in plaintext so that queries and
    indexes still work.

    The encryption key is derived from a user-provided password using
    PBKDF2-HMAC-SHA256.  A random salt is generated on first use and
    stored in the ``memorymesh_meta`` table within the same database.

    Args:
        store: The underlying :class:`MemoryStore` to wrap.
        password: The passphrase to derive the encryption key from.
    """

    def __init__(self, store: MemoryStore, password: str) -> None:
        self._store = store
        # Derive encryption key using the store's database salt.
        conn = self._store._get_connection()
        salt = _get_or_create_salt(conn)
        self._key = derive_key(password, salt)

    # -- Expose path for compatibility with core.py -----------------------

    @property
    def _path(self) -> str:
        """Database file path (delegated to the wrapped store)."""
        return self._store._path

    @property
    def _local(self) -> Any:
        """Thread-local state (delegated to the wrapped store)."""
        return self._store._local

    @property
    def schema_version(self) -> int:
        """Schema version (delegated to the wrapped store)."""
        return self._store.schema_version

    # -- Write operations (encrypt before save) ---------------------------

    def save(self, memory: Memory) -> None:
        """Encrypt sensitive fields and persist the memory.

        Encrypts ``text`` and ``metadata`` (as JSON string), then saves
        via the underlying store.

        Args:
            memory: The :class:`Memory` to persist.
        """
        encrypted_mem = Memory(
            id=memory.id,
            text=encrypt_field(memory.text, self._key),
            metadata={
                "_encrypted": encrypt_field(
                    json.dumps(memory.metadata, ensure_ascii=False), self._key
                )
            },
            embedding=memory.embedding,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            access_count=memory.access_count,
            importance=memory.importance,
            decay_rate=memory.decay_rate,
            session_id=memory.session_id,
            scope=memory.scope,
        )
        self._store.save(encrypted_mem)

    # -- Read operations (decrypt after retrieval) ------------------------

    def _decrypt_memory(self, memory: Memory | None) -> Memory | None:
        """Decrypt sensitive fields of a retrieved memory.

        Args:
            memory: A :class:`Memory` read from the store, or ``None``.

        Returns:
            The memory with decrypted ``text`` and ``metadata``, or ``None``.
        """
        if memory is None:
            return None

        decrypted_text = decrypt_field(memory.text, self._key)
        encrypted_meta = memory.metadata.get("_encrypted")
        if encrypted_meta:
            decrypted_meta = json.loads(decrypt_field(encrypted_meta, self._key))
        else:
            # Not encrypted (e.g. created before encryption was enabled).
            decrypted_meta = memory.metadata

        return Memory(
            id=memory.id,
            text=decrypted_text,
            metadata=decrypted_meta,
            embedding=memory.embedding,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            access_count=memory.access_count,
            importance=memory.importance,
            decay_rate=memory.decay_rate,
            session_id=memory.session_id,
            scope=memory.scope,
        )

    def get(self, memory_id: str) -> Memory | None:
        """Retrieve and decrypt a single memory by ID.

        Args:
            memory_id: The unique identifier.

        Returns:
            The decrypted :class:`Memory`, or ``None``.
        """
        return self._decrypt_memory(self._store.get(memory_id))

    def search_by_text(self, query: str, limit: int = 20) -> list[Memory]:
        """Search by text substring.

        .. note::
            Because the ``text`` field is encrypted, LIKE-based substring
            matching will not find encrypted content.  This method returns
            an empty list when encryption is enabled.  Semantic search via
            embeddings still works normally.

        Args:
            query: The search string.
            limit: Maximum number of results.

        Returns:
            An empty list (encrypted text cannot be searched with LIKE).
        """
        # Encrypted text cannot be searched with LIKE.  Return empty list
        # so the caller falls back to embedding-based search.
        return []

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        """List and decrypt memories with pagination.

        Args:
            limit: Maximum number of memories to return.
            offset: Number of rows to skip.

        Returns:
            A list of decrypted :class:`Memory` objects.
        """
        mems = self._store.list_all(limit=limit, offset=offset)
        return [self._decrypt_memory(m) for m in mems]  # type: ignore[misc]

    def get_all_with_embeddings(self, limit: int = 10_000) -> list[Memory]:
        """Return decrypted memories that have embeddings.

        Args:
            limit: Maximum number of memories.

        Returns:
            A list of decrypted :class:`Memory` objects with embeddings.
        """
        mems = self._store.get_all_with_embeddings(limit=limit)
        return [self._decrypt_memory(m) for m in mems]  # type: ignore[misc]

    def get_by_session(self, session_id: str, limit: int = 100) -> list[Memory]:
        """Retrieve and decrypt all memories in a session.

        Args:
            session_id: The session identifier.
            limit: Maximum number of results.

        Returns:
            A list of decrypted :class:`Memory` objects.
        """
        mems = self._store.get_by_session(session_id, limit=limit)
        return [self._decrypt_memory(m) for m in mems]  # type: ignore[misc]

    def search_filtered(
        self,
        category: str | None = None,
        min_importance: float | None = None,
        time_range: tuple[str, str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10_000,
    ) -> list[Memory]:
        """Search with SQL-level filters and decrypt results.

        .. note::
            Metadata filtering operates on the *encrypted* metadata
            stored in the database.  Filters on custom metadata keys will
            not match encrypted content.  Category and importance filters
            work normally because those fields are stored in plaintext.

        Args:
            category: Filter by category in metadata.
            min_importance: Minimum importance threshold.
            time_range: Tuple of (start_iso, end_iso) for created_at range.
            metadata_filter: Dict of key-value pairs to match in metadata JSON.
            limit: Maximum results.

        Returns:
            Filtered list of decrypted :class:`Memory` objects.
        """
        mems = self._store.search_filtered(
            category=category,
            min_importance=min_importance,
            time_range=time_range,
            metadata_filter=metadata_filter,
            limit=limit,
        )
        return [self._decrypt_memory(m) for m in mems]  # type: ignore[misc]

    def update_fields(
        self,
        memory_id: str,
        text: str | None = None,
        importance: float | None = None,
        decay_rate: float | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> bool:
        """Update fields with encryption for sensitive data.

        If *text* is provided, it is encrypted before storing.  If
        *metadata* is provided, it is serialized to JSON, encrypted, and
        wrapped in ``{"_encrypted": ...}``.  Non-sensitive fields
        (importance, decay_rate, embedding) are delegated directly.

        Args:
            memory_id: The unique identifier of the memory to update.
            text: New text content (will be encrypted), or ``None``.
            importance: New importance score, or ``None``.
            decay_rate: New decay rate, or ``None``.
            metadata: New metadata dict (will be encrypted), or ``None``.
            embedding: New embedding vector, or ``None``.

        Returns:
            ``True`` if the row was updated, ``False`` if not found.
        """
        encrypted_text = encrypt_field(text, self._key) if text is not None else None
        encrypted_meta = None
        if metadata is not None:
            encrypted_meta = {
                "_encrypted": encrypt_field(
                    json.dumps(metadata, ensure_ascii=False), self._key
                )
            }

        return self._store.update_fields(
            memory_id=memory_id,
            text=encrypted_text,
            importance=importance,
            decay_rate=decay_rate,
            metadata=encrypted_meta,
            embedding=embedding,
        )

    # -- Delegate non-field-reading operations ----------------------------

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: The unique identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        return self._store.delete(memory_id)

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List distinct sessions.

        Args:
            limit: Maximum number of sessions.

        Returns:
            Session summary dicts.
        """
        return self._store.list_sessions(limit=limit)

    def count(self) -> int:
        """Return the total number of stored memories."""
        return self._store.count()

    def get_time_range(self) -> tuple[str | None, str | None]:
        """Return the oldest and newest timestamps."""
        return self._store.get_time_range()

    def clear(self) -> int:
        """Delete all memories."""
        return self._store.clear()

    def update_access(self, memory_id: str) -> None:
        """Increment access count for a memory.

        Args:
            memory_id: The unique identifier.
        """
        self._store.update_access(memory_id)

    def close(self) -> None:
        """Close the underlying store."""
        self._store.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Return the underlying SQLite connection (for meta table access)."""
        return self._store._get_connection()

    # -- Context manager --------------------------------------------------

    def __enter__(self) -> EncryptedMemoryStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()

    def __repr__(self) -> str:  # pragma: no cover
        return f"EncryptedMemoryStore(store={self._store!r})"
