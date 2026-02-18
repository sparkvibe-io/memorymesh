"""Tests for the encryption module.

Covers key derivation, encrypt/decrypt round-trips, tamper detection,
EncryptedMemoryStore integration, and backward compatibility.
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
from collections.abc import Generator

import pytest

from memorymesh.encryption import (
    EncryptedMemoryStore,
    _ensure_meta_table,
    _get_or_create_salt,
    decrypt_field,
    derive_key,
    encrypt_field,
)
from memorymesh.memory import Memory
from memorymesh.store import MemoryStore

# ------------------------------------------------------------------
# Key derivation
# ------------------------------------------------------------------


class TestDeriveKey:
    """Tests for PBKDF2 key derivation."""

    def test_consistent_output(self) -> None:
        """Same password + salt always produces the same key."""
        salt = b"\x00" * 16
        key1 = derive_key("my secret", salt)
        key2 = derive_key("my secret", salt)
        assert key1 == key2

    def test_key_length(self) -> None:
        """Derived key is exactly 32 bytes (256 bits)."""
        salt = os.urandom(16)
        key = derive_key("password", salt)
        assert len(key) == 32

    def test_different_passwords_different_keys(self) -> None:
        """Different passwords produce different keys."""
        salt = os.urandom(16)
        key1 = derive_key("password1", salt)
        key2 = derive_key("password2", salt)
        assert key1 != key2

    def test_different_salts_different_keys(self) -> None:
        """Same password with different salts produces different keys."""
        key1 = derive_key("password", b"\x00" * 16)
        key2 = derive_key("password", b"\xff" * 16)
        assert key1 != key2

    def test_empty_password(self) -> None:
        """Empty password still produces a valid 32-byte key."""
        salt = os.urandom(16)
        key = derive_key("", salt)
        assert len(key) == 32

    def test_unicode_password(self) -> None:
        """Unicode passwords work correctly."""
        salt = os.urandom(16)
        key = derive_key("\u00e9\u00e0\u00fc\U0001f600", salt)
        assert len(key) == 32


# ------------------------------------------------------------------
# Encrypt / decrypt round-trip
# ------------------------------------------------------------------


class TestEncryptDecrypt:
    """Tests for the encrypt_field / decrypt_field functions."""

    @pytest.fixture
    def key(self) -> bytes:
        return derive_key("test password", b"\x01" * 16)

    def test_round_trip_basic(self, key: bytes) -> None:
        """Encrypting then decrypting returns the original text."""
        plaintext = "Hello, World!"
        ciphertext = encrypt_field(plaintext, key)
        assert decrypt_field(ciphertext, key) == plaintext

    def test_round_trip_empty_string(self, key: bytes) -> None:
        """Empty strings can be encrypted and decrypted."""
        ciphertext = encrypt_field("", key)
        assert decrypt_field(ciphertext, key) == ""

    def test_round_trip_long_text(self, key: bytes) -> None:
        """Long text (multiple keystream blocks) round-trips correctly."""
        plaintext = "A" * 10_000
        ciphertext = encrypt_field(plaintext, key)
        assert decrypt_field(ciphertext, key) == plaintext

    def test_round_trip_unicode(self, key: bytes) -> None:
        """Unicode text (multi-byte UTF-8) round-trips correctly."""
        plaintext = "\u65e5\u672c\u8a9e\u30c6\u30b9\u30c8 \U0001f600 caf\u00e9"
        ciphertext = encrypt_field(plaintext, key)
        assert decrypt_field(ciphertext, key) == plaintext

    def test_round_trip_json(self, key: bytes) -> None:
        """JSON strings (metadata) round-trip correctly."""
        data = {"key": "value", "nested": {"a": [1, 2, 3]}}
        plaintext = json.dumps(data)
        ciphertext = encrypt_field(plaintext, key)
        assert json.loads(decrypt_field(ciphertext, key)) == data

    def test_ciphertext_is_base64(self, key: bytes) -> None:
        """Output is valid base64."""
        ciphertext = encrypt_field("test", key)
        # Should not raise
        base64.b64decode(ciphertext)

    def test_ciphertext_differs_from_plaintext(self, key: bytes) -> None:
        """Ciphertext is not the same as the plaintext."""
        plaintext = "sensitive data"
        ciphertext = encrypt_field(plaintext, key)
        # The base64 output should not contain the plaintext
        assert plaintext not in ciphertext
        # The raw bytes should also differ
        raw = base64.b64decode(ciphertext)
        assert plaintext.encode("utf-8") not in raw

    def test_different_ivs_per_encryption(self, key: bytes) -> None:
        """Each encryption produces a different ciphertext (random IV)."""
        plaintext = "same text"
        c1 = encrypt_field(plaintext, key)
        c2 = encrypt_field(plaintext, key)
        assert c1 != c2
        # But both decrypt to the same thing
        assert decrypt_field(c1, key) == plaintext
        assert decrypt_field(c2, key) == plaintext


# ------------------------------------------------------------------
# Tamper detection
# ------------------------------------------------------------------


class TestTamperDetection:
    """Tests that tampering with ciphertext is detected."""

    @pytest.fixture
    def key(self) -> bytes:
        return derive_key("tamper test", b"\x02" * 16)

    def test_tampered_ciphertext_fails(self, key: bytes) -> None:
        """Flipping a byte in the ciphertext portion fails authentication."""
        ciphertext_b64 = encrypt_field("secret", key)
        raw = bytearray(base64.b64decode(ciphertext_b64))
        # Flip a byte in the ciphertext portion (between IV and tag).
        if len(raw) > 16 + 32:
            raw[17] ^= 0xFF
        modified = base64.b64encode(bytes(raw)).decode("ascii")
        with pytest.raises(ValueError, match="Authentication failed"):
            decrypt_field(modified, key)

    def test_tampered_tag_fails(self, key: bytes) -> None:
        """Flipping a byte in the HMAC tag fails authentication."""
        ciphertext_b64 = encrypt_field("secret", key)
        raw = bytearray(base64.b64decode(ciphertext_b64))
        # Flip last byte (part of the tag).
        raw[-1] ^= 0xFF
        modified = base64.b64encode(bytes(raw)).decode("ascii")
        with pytest.raises(ValueError, match="Authentication failed"):
            decrypt_field(modified, key)

    def test_tampered_iv_fails(self, key: bytes) -> None:
        """Flipping a byte in the IV fails authentication."""
        ciphertext_b64 = encrypt_field("secret", key)
        raw = bytearray(base64.b64decode(ciphertext_b64))
        raw[0] ^= 0xFF
        modified = base64.b64encode(bytes(raw)).decode("ascii")
        with pytest.raises(ValueError, match="Authentication failed"):
            decrypt_field(modified, key)

    def test_truncated_ciphertext_fails(self, key: bytes) -> None:
        """Truncated ciphertext is detected."""
        ciphertext_b64 = encrypt_field("secret", key)
        raw = base64.b64decode(ciphertext_b64)
        # Truncate to just the IV.
        truncated = base64.b64encode(raw[:10]).decode("ascii")
        with pytest.raises(ValueError, match="too short"):
            decrypt_field(truncated, key)

    def test_wrong_key_fails(self, key: bytes) -> None:
        """Decrypting with a different key fails authentication."""
        ciphertext_b64 = encrypt_field("secret", key)
        wrong_key = derive_key("wrong password", b"\x02" * 16)
        with pytest.raises(ValueError, match="Authentication failed"):
            decrypt_field(ciphertext_b64, wrong_key)


# ------------------------------------------------------------------
# Salt storage
# ------------------------------------------------------------------


class TestSaltStorage:
    """Tests for the memorymesh_meta salt persistence."""

    def test_salt_created_on_first_use(self, tmp_path) -> None:
        """A random salt is created and stored on first use."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        salt = _get_or_create_salt(conn)
        assert isinstance(salt, bytes)
        assert len(salt) == 16
        conn.close()

    def test_salt_persists_across_connections(self, tmp_path) -> None:
        """The same salt is returned after reopening the database."""
        db_path = tmp_path / "test.db"
        conn1 = sqlite3.connect(str(db_path))
        salt1 = _get_or_create_salt(conn1)
        conn1.close()

        conn2 = sqlite3.connect(str(db_path))
        _ensure_meta_table(conn2)
        salt2 = _get_or_create_salt(conn2)
        conn2.close()

        assert salt1 == salt2

    def test_meta_table_idempotent(self, tmp_path) -> None:
        """Creating the meta table multiple times does not error."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        _ensure_meta_table(conn)
        _ensure_meta_table(conn)  # second call should be a no-op
        conn.close()


# ------------------------------------------------------------------
# EncryptedMemoryStore
# ------------------------------------------------------------------


class TestEncryptedMemoryStore:
    """Tests for the EncryptedMemoryStore wrapper."""

    @pytest.fixture
    def store(self, tmp_path) -> Generator[EncryptedMemoryStore, None, None]:
        """Create an EncryptedMemoryStore backed by a temp directory."""
        raw_store = MemoryStore(path=tmp_path / "encrypted.db")
        s = EncryptedMemoryStore(raw_store, "test-password-123")
        yield s
        s.close()

    @pytest.fixture
    def raw_store(self, tmp_path) -> Generator[MemoryStore, None, None]:
        """Create a raw (unencrypted) MemoryStore for comparison."""
        s = MemoryStore(path=tmp_path / "encrypted.db")
        yield s
        s.close()

    def test_save_and_get_round_trip(self, store) -> None:
        """Saving and getting a memory returns the original content."""
        mem = Memory(text="Remember this secret fact", metadata={"tag": "secret"})
        store.save(mem)

        retrieved = store.get(mem.id)
        assert retrieved is not None
        assert retrieved.text == "Remember this secret fact"
        assert retrieved.metadata == {"tag": "secret"}

    def test_raw_db_content_is_encrypted(self, tmp_path) -> None:
        """The raw database content should NOT contain plaintext."""
        db_path = tmp_path / "enc_check.db"
        raw_store = MemoryStore(path=db_path)
        enc_store = EncryptedMemoryStore(raw_store, "password")

        secret_text = "This is a very secret message that must not appear in plaintext"
        mem = Memory(text=secret_text, metadata={"key": "value"})
        enc_store.save(mem)
        enc_store.close()

        # Read the raw database and check the text field.
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT text, metadata_json FROM memories WHERE id = ?", (mem.id,))
        row = cur.fetchone()
        conn.close()

        assert row is not None
        raw_text = row[0]
        raw_meta = row[1]

        # The raw text should be base64-encoded ciphertext, not the original.
        assert secret_text not in raw_text
        assert "value" not in raw_meta
        # Should look like base64.
        base64.b64decode(raw_text)

    def test_list_all_decrypts(self, store) -> None:
        """list_all returns decrypted memories."""
        mem1 = Memory(text="First memory")
        mem2 = Memory(text="Second memory")
        store.save(mem1)
        store.save(mem2)

        results = store.list_all()
        texts = {m.text for m in results}
        assert "First memory" in texts
        assert "Second memory" in texts

    def test_get_all_with_embeddings(self, store) -> None:
        """get_all_with_embeddings returns decrypted memories."""
        mem = Memory(text="Embedded memory", embedding=[0.1, 0.2, 0.3])
        store.save(mem)

        results = store.get_all_with_embeddings()
        assert len(results) == 1
        assert results[0].text == "Embedded memory"
        assert results[0].embedding is not None

    def test_get_by_session(self, store) -> None:
        """get_by_session returns decrypted memories."""
        mem = Memory(text="Session memory", session_id="sess-1")
        store.save(mem)

        results = store.get_by_session("sess-1")
        assert len(results) == 1
        assert results[0].text == "Session memory"

    def test_search_by_text_returns_empty(self, store) -> None:
        """search_by_text returns empty (encrypted text can't be LIKE-searched)."""
        mem = Memory(text="Findable text")
        store.save(mem)

        results = store.search_by_text("Findable")
        assert results == []

    def test_delete(self, store) -> None:
        """Deleting works through the encrypted wrapper."""
        mem = Memory(text="To be deleted")
        store.save(mem)
        assert store.delete(mem.id)
        assert store.get(mem.id) is None

    def test_count(self, store) -> None:
        """count() works through the encrypted wrapper."""
        assert store.count() == 0
        store.save(Memory(text="One"))
        assert store.count() == 1

    def test_clear(self, store) -> None:
        """clear() works through the encrypted wrapper."""
        store.save(Memory(text="One"))
        store.save(Memory(text="Two"))
        deleted = store.clear()
        assert deleted == 2
        assert store.count() == 0

    def test_update_access(self, store) -> None:
        """update_access works through the encrypted wrapper."""
        mem = Memory(text="Access me")
        store.save(mem)
        store.update_access(mem.id)
        retrieved = store.get(mem.id)
        assert retrieved is not None
        assert retrieved.access_count == 1

    def test_get_time_range(self, store) -> None:
        """get_time_range works through the encrypted wrapper."""
        store.save(Memory(text="Timestamped"))
        oldest, newest = store.get_time_range()
        assert oldest is not None
        assert newest is not None

    def test_list_sessions(self, store) -> None:
        """list_sessions works through the encrypted wrapper."""
        store.save(Memory(text="In session", session_id="s1"))
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "s1"

    def test_path_property(self, store) -> None:
        """_path property is delegated to the wrapped store."""
        assert store._path.endswith("encrypted.db")

    def test_schema_version_property(self, store) -> None:
        """schema_version property is delegated."""
        assert isinstance(store.schema_version, int)

    def test_context_manager(self, tmp_path) -> None:
        """EncryptedMemoryStore can be used as a context manager."""
        raw = MemoryStore(path=tmp_path / "ctx.db")
        with EncryptedMemoryStore(raw, "pass") as store:
            store.save(Memory(text="Context managed"))
            assert store.count() == 1


# ------------------------------------------------------------------
# Integration with MemoryMesh
# ------------------------------------------------------------------


class TestMemoryMeshEncryption:
    """Integration tests: MemoryMesh(encryption_key=...)."""

    def test_remember_and_recall_encrypted(self, tmp_path) -> None:
        """remember() + get() work with encryption enabled."""
        from memorymesh.core import MemoryMesh

        project_db = tmp_path / "project" / "memories.db"
        global_db = tmp_path / "global" / "global.db"

        mesh = MemoryMesh(
            path=project_db,
            global_path=global_db,
            embedding="none",
            encryption_key="super-secret",
        )

        mid = mesh.remember("Encrypted fact", scope="project")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.text == "Encrypted fact"

        mesh.close()

    def test_raw_db_not_readable_via_memorymesh(self, tmp_path) -> None:
        """Raw database written with encryption cannot be read without the key."""
        from memorymesh.core import MemoryMesh

        project_db = tmp_path / "project" / "memories.db"
        global_db = tmp_path / "global" / "global.db"

        mesh = MemoryMesh(
            path=project_db,
            global_path=global_db,
            embedding="none",
            encryption_key="secret",
        )
        mid = mesh.remember("Top secret info", scope="project")
        mesh.close()

        # Open the raw DB and verify plaintext is not present.
        conn = sqlite3.connect(str(project_db))
        cur = conn.execute("SELECT text FROM memories WHERE id = ?", (mid,))
        row = cur.fetchone()
        conn.close()

        assert row is not None
        assert "Top secret info" not in row[0]

    def test_no_encryption_key_no_encryption(self, tmp_path) -> None:
        """When encryption_key is None, data is stored in plaintext (backward compat)."""
        from memorymesh.core import MemoryMesh

        project_db = tmp_path / "project" / "memories.db"
        global_db = tmp_path / "global" / "global.db"

        mesh = MemoryMesh(
            path=project_db,
            global_path=global_db,
            embedding="none",
        )
        mid = mesh.remember("Plaintext fact", scope="project")
        mesh.close()

        # Raw DB should contain the plaintext.
        conn = sqlite3.connect(str(project_db))
        cur = conn.execute("SELECT text FROM memories WHERE id = ?", (mid,))
        row = cur.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "Plaintext fact"

    def test_global_store_also_encrypted(self, tmp_path) -> None:
        """Global store is encrypted when encryption_key is provided."""
        from memorymesh.core import MemoryMesh

        global_db = tmp_path / "global" / "global.db"

        mesh = MemoryMesh(
            global_path=global_db,
            embedding="none",
            encryption_key="key123",
        )
        mid = mesh.remember("Global secret", scope="global")
        mesh.close()

        conn = sqlite3.connect(str(global_db))
        cur = conn.execute("SELECT text FROM memories WHERE id = ?", (mid,))
        row = cur.fetchone()
        conn.close()

        assert row is not None
        assert "Global secret" not in row[0]

    def test_forget_with_encryption(self, tmp_path) -> None:
        """forget() works correctly with encryption enabled."""
        from memorymesh.core import MemoryMesh

        project_db = tmp_path / "project" / "memories.db"
        global_db = tmp_path / "global" / "global.db"

        mesh = MemoryMesh(
            path=project_db,
            global_path=global_db,
            embedding="none",
            encryption_key="pass",
        )
        mid = mesh.remember("Forget me", scope="project")
        assert mesh.forget(mid)
        assert mesh.get(mid) is None
        mesh.close()

    def test_forget_all_with_encryption(self, tmp_path) -> None:
        """forget_all() works correctly with encryption enabled."""
        from memorymesh.core import MemoryMesh

        project_db = tmp_path / "project" / "memories.db"
        global_db = tmp_path / "global" / "global.db"

        mesh = MemoryMesh(
            path=project_db,
            global_path=global_db,
            embedding="none",
            encryption_key="pass",
        )
        mesh.remember("One", scope="project")
        mesh.remember("Two", scope="project")
        deleted = mesh.forget_all(scope="project")
        assert deleted == 2
        assert mesh.count(scope="project") == 0
        mesh.close()

    def test_list_with_encryption(self, tmp_path) -> None:
        """list() returns decrypted memories."""
        from memorymesh.core import MemoryMesh

        project_db = tmp_path / "project" / "memories.db"
        global_db = tmp_path / "global" / "global.db"

        mesh = MemoryMesh(
            path=project_db,
            global_path=global_db,
            embedding="none",
            encryption_key="pass",
        )
        mesh.remember("Listed secret", scope="project")
        mems = mesh.list(scope="project")
        assert len(mems) == 1
        assert mems[0].text == "Listed secret"
        mesh.close()

    def test_metadata_round_trip(self, tmp_path) -> None:
        """Metadata is encrypted and decrypted correctly."""
        from memorymesh.core import MemoryMesh

        project_db = tmp_path / "project" / "memories.db"
        global_db = tmp_path / "global" / "global.db"

        mesh = MemoryMesh(
            path=project_db,
            global_path=global_db,
            embedding="none",
            encryption_key="pass",
        )
        mid = mesh.remember(
            "With metadata",
            metadata={"source": "test", "tags": ["a", "b"]},
            scope="project",
        )
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.metadata == {"source": "test", "tags": ["a", "b"]}
        mesh.close()
