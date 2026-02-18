"""Tests for the hybrid dual-store architecture.

Covers scope validation, dual-store remember/recall/forget, store isolation,
project root detection, and legacy migration.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from memorymesh import MemoryMesh
from memorymesh.memory import (
    GLOBAL_SCOPE,
    PROJECT_SCOPE,
    Memory,
    validate_scope,
)
from memorymesh.store import (
    detect_project_root,
    migrate_legacy_db,
)

# ------------------------------------------------------------------
# TestScope
# ------------------------------------------------------------------


class TestScope:
    """Scope constants and validation."""

    def test_validate_scope_project(self):
        """'project' is a valid scope."""
        validate_scope("project")  # should not raise

    def test_validate_scope_global(self):
        """'global' is a valid scope."""
        validate_scope("global")  # should not raise

    def test_validate_scope_invalid(self):
        """An invalid scope raises ValueError."""
        with pytest.raises(ValueError, match="Invalid scope"):
            validate_scope("local")

    def test_memory_scope_default(self):
        """Memory.scope defaults to 'project'."""
        mem = Memory(text="test")
        assert mem.scope == PROJECT_SCOPE

    def test_memory_scope_global(self):
        """Memory can be created with scope='global'."""
        mem = Memory(text="test", scope=GLOBAL_SCOPE)
        assert mem.scope == GLOBAL_SCOPE

    def test_memory_scope_invalid(self):
        """Memory with invalid scope raises ValueError."""
        with pytest.raises(ValueError, match="Invalid scope"):
            Memory(text="test", scope="invalid")

    def test_scope_survives_to_dict(self):
        """scope is included in to_dict() output."""
        mem = Memory(text="test", scope=GLOBAL_SCOPE)
        d = mem.to_dict()
        assert d["scope"] == GLOBAL_SCOPE

    def test_scope_survives_from_dict(self):
        """scope round-trips through to_dict/from_dict."""
        mem = Memory(text="test", scope=GLOBAL_SCOPE)
        d = mem.to_dict()
        restored = Memory.from_dict(d)
        assert restored.scope == GLOBAL_SCOPE

    def test_scope_defaults_in_from_dict(self):
        """from_dict without scope key defaults to 'project'."""
        d = {
            "text": "legacy",
            "id": "abc123",
            "created_at": "2025-01-15T10:00:00+00:00",
            "updated_at": "2025-01-15T10:00:00+00:00",
            "access_count": 0,
            "importance": 0.5,
            "decay_rate": 0.01,
            "embedding": None,
            "metadata": {},
        }
        mem = Memory.from_dict(d)
        assert mem.scope == PROJECT_SCOPE


# ------------------------------------------------------------------
# TestDualStoreRemember
# ------------------------------------------------------------------


class TestDualStoreRemember:
    """remember() routes to the correct store based on scope."""

    def test_remember_default_project(self, tmp_path):
        """Default remember() writes to the project store."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("project fact")
        assert mesh.count(scope=PROJECT_SCOPE) == 1
        assert mesh.count(scope=GLOBAL_SCOPE) == 0

    def test_remember_global(self, tmp_path):
        """remember(scope='global') writes to the global store."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("user prefers dark mode", scope=GLOBAL_SCOPE)
        assert mesh.count(scope=PROJECT_SCOPE) == 0
        assert mesh.count(scope=GLOBAL_SCOPE) == 1

    def test_remember_both_scopes(self, tmp_path):
        """Memories in different scopes are isolated."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("project fact", scope=PROJECT_SCOPE)
        mesh.remember("global fact", scope=GLOBAL_SCOPE)
        assert mesh.count(scope=PROJECT_SCOPE) == 1
        assert mesh.count(scope=GLOBAL_SCOPE) == 1
        assert mesh.count() == 2


# ------------------------------------------------------------------
# TestDualStoreRecall
# ------------------------------------------------------------------


class TestDualStoreRecall:
    """recall() queries one or both stores."""

    def test_recall_both(self, tmp_path):
        """recall(scope=None) searches both stores."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("Python is great", scope=PROJECT_SCOPE)
        mesh.remember("Python is my favourite", scope=GLOBAL_SCOPE)

        results = mesh.recall("Python")
        assert len(results) == 2
        scopes = {m.scope for m in results}
        assert scopes == {PROJECT_SCOPE, GLOBAL_SCOPE}

    def test_recall_project_only(self, tmp_path):
        """recall(scope='project') only returns project memories."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("project note", scope=PROJECT_SCOPE)
        mesh.remember("global note", scope=GLOBAL_SCOPE)

        results = mesh.recall("note", scope=PROJECT_SCOPE)
        assert all(m.scope == PROJECT_SCOPE for m in results)

    def test_recall_global_only(self, tmp_path):
        """recall(scope='global') only returns global memories."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("project note", scope=PROJECT_SCOPE)
        mesh.remember("global note", scope=GLOBAL_SCOPE)

        results = mesh.recall("note", scope=GLOBAL_SCOPE)
        assert all(m.scope == GLOBAL_SCOPE for m in results)

    def test_recall_tags_scope(self, tmp_path):
        """Recalled memories have the correct scope tag."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("fact alpha", scope=PROJECT_SCOPE)
        mesh.remember("fact beta", scope=GLOBAL_SCOPE)

        results = mesh.recall("fact")
        for mem in results:
            if "alpha" in mem.text:
                assert mem.scope == PROJECT_SCOPE
            elif "beta" in mem.text:
                assert mem.scope == GLOBAL_SCOPE


# ------------------------------------------------------------------
# TestDualStoreForget
# ------------------------------------------------------------------


class TestDualStoreForget:
    """forget() and forget_all() respect scope boundaries."""

    def test_forget_checks_both(self, tmp_path):
        """forget() finds a memory regardless of which store it is in."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        pid = mesh.remember("project", scope=PROJECT_SCOPE)
        gid = mesh.remember("global", scope=GLOBAL_SCOPE)

        assert mesh.forget(pid) is True
        assert mesh.forget(gid) is True
        assert mesh.count() == 0

    def test_forget_all_project(self, tmp_path):
        """forget_all('project') only clears the project store."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("project", scope=PROJECT_SCOPE)
        mesh.remember("global", scope=GLOBAL_SCOPE)

        deleted = mesh.forget_all(scope=PROJECT_SCOPE)
        assert deleted == 1
        assert mesh.count(scope=PROJECT_SCOPE) == 0
        assert mesh.count(scope=GLOBAL_SCOPE) == 1

    def test_forget_all_global(self, tmp_path):
        """forget_all('global') only clears the global store."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("project", scope=PROJECT_SCOPE)
        mesh.remember("global", scope=GLOBAL_SCOPE)

        deleted = mesh.forget_all(scope=GLOBAL_SCOPE)
        assert deleted == 1
        assert mesh.count(scope=PROJECT_SCOPE) == 1
        assert mesh.count(scope=GLOBAL_SCOPE) == 0


# ------------------------------------------------------------------
# TestDualStoreIsolation
# ------------------------------------------------------------------


class TestDualStoreIsolation:
    """Two MemoryMesh instances share global but have isolated projects."""

    def test_project_isolation_shared_global(self, tmp_path):
        """Different project paths are isolated; global is shared."""
        global_db = str(tmp_path / "global.db")

        mesh_a = MemoryMesh(
            path=str(tmp_path / "a" / "project.db"),
            global_path=global_db,
            embedding="none",
        )
        mesh_b = MemoryMesh(
            path=str(tmp_path / "b" / "project.db"),
            global_path=global_db,
            embedding="none",
        )

        mesh_a.remember("project A fact", scope=PROJECT_SCOPE)
        mesh_b.remember("project B fact", scope=PROJECT_SCOPE)
        mesh_a.remember("shared user pref", scope=GLOBAL_SCOPE)

        # Project stores are isolated.
        assert mesh_a.count(scope=PROJECT_SCOPE) == 1
        assert mesh_b.count(scope=PROJECT_SCOPE) == 1

        # Global store is shared.
        assert mesh_a.count(scope=GLOBAL_SCOPE) == 1
        assert mesh_b.count(scope=GLOBAL_SCOPE) == 1

        # A's recall of project scope doesn't return B's project memory.
        results_a = mesh_a.recall("fact", scope=PROJECT_SCOPE)
        assert all("A" in m.text for m in results_a)

        mesh_a.close()
        mesh_b.close()


# ------------------------------------------------------------------
# TestDualStoreCount
# ------------------------------------------------------------------


class TestDualStoreCount:
    """count() with scope parameter."""

    def test_count_scoped(self, tmp_path):
        """count(scope=...) returns the correct per-scope count."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("p1", scope=PROJECT_SCOPE)
        mesh.remember("p2", scope=PROJECT_SCOPE)
        mesh.remember("g1", scope=GLOBAL_SCOPE)

        assert mesh.count(scope=PROJECT_SCOPE) == 2
        assert mesh.count(scope=GLOBAL_SCOPE) == 1
        assert mesh.count() == 3


# ------------------------------------------------------------------
# TestDualStoreGet
# ------------------------------------------------------------------


class TestDualStoreGet:
    """get() checks both stores."""

    def test_get_from_project(self, tmp_path):
        """get() finds a memory in the project store."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mid = mesh.remember("project item", scope=PROJECT_SCOPE)
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == PROJECT_SCOPE

    def test_get_from_global(self, tmp_path):
        """get() finds a memory in the global store."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mid = mesh.remember("global item", scope=GLOBAL_SCOPE)
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == GLOBAL_SCOPE


# ------------------------------------------------------------------
# TestDualStoreList
# ------------------------------------------------------------------


class TestDualStoreList:
    """list() with scope parameter."""

    def test_list_merged(self, tmp_path):
        """list(scope=None) returns memories from both stores."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("project", scope=PROJECT_SCOPE)
        mesh.remember("global", scope=GLOBAL_SCOPE)

        all_mems = mesh.list(limit=10)
        assert len(all_mems) == 2
        scopes = {m.scope for m in all_mems}
        assert scopes == {PROJECT_SCOPE, GLOBAL_SCOPE}

    def test_list_project_only(self, tmp_path):
        """list(scope='project') returns only project memories."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("project", scope=PROJECT_SCOPE)
        mesh.remember("global", scope=GLOBAL_SCOPE)

        mems = mesh.list(scope=PROJECT_SCOPE)
        assert len(mems) == 1
        assert mems[0].scope == PROJECT_SCOPE


# ------------------------------------------------------------------
# TestProjectDetection
# ------------------------------------------------------------------


class TestProjectDetection:
    """detect_project_root() heuristics."""

    def test_detect_from_mcp_roots(self, tmp_path):
        """Picks up the first file:// URI from roots."""
        # Use Path.as_uri() for correct file URIs on all platforms
        # (e.g. file:///C:/Users/... on Windows, file:///tmp/... on Unix).
        roots = [{"uri": Path(tmp_path).as_uri()}]
        assert detect_project_root(roots) == os.path.realpath(str(tmp_path))

    def test_detect_from_env(self, tmp_path, monkeypatch):
        """Falls back to MEMORYMESH_PROJECT_ROOT env var."""
        monkeypatch.setenv("MEMORYMESH_PROJECT_ROOT", str(tmp_path))
        assert detect_project_root(None) == os.path.realpath(str(tmp_path))

    def test_detect_from_cwd_git(self, tmp_path, monkeypatch):
        """Detects a project root when CWD has a .git directory."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)
        assert detect_project_root(None) == os.path.realpath(str(tmp_path))

    def test_detect_none(self, tmp_path, monkeypatch):
        """Returns None when no project signals are present."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)
        assert detect_project_root(None) is None


# ------------------------------------------------------------------
# TestLegacyMigration
# ------------------------------------------------------------------


class TestLegacyMigration:
    """migrate_legacy_db() renames memories.db → global.db."""

    def test_migration_renames(self, tmp_path, monkeypatch):
        """Legacy memories.db is renamed to global.db."""
        legacy = tmp_path / "memories.db"
        global_db = tmp_path / "global.db"

        # Temporarily patch the module-level paths.
        monkeypatch.setattr(
            "memorymesh.store._LEGACY_DB",
            str(legacy),
        )
        monkeypatch.setattr(
            "memorymesh.store._DEFAULT_GLOBAL_DB",
            str(global_db),
        )
        monkeypatch.setattr(
            "memorymesh.store._DEFAULT_GLOBAL_DIR",
            str(tmp_path),
        )

        legacy.write_text("fake db content")
        assert migrate_legacy_db() is True
        assert not legacy.exists()
        assert global_db.exists()

    def test_migration_noop_when_global_exists(self, tmp_path, monkeypatch):
        """No migration when global.db already exists."""
        legacy = tmp_path / "memories.db"
        global_db = tmp_path / "global.db"

        monkeypatch.setattr(
            "memorymesh.store._LEGACY_DB",
            str(legacy),
        )
        monkeypatch.setattr(
            "memorymesh.store._DEFAULT_GLOBAL_DB",
            str(global_db),
        )

        legacy.write_text("old data")
        global_db.write_text("new data")

        assert migrate_legacy_db() is False
        # Both files still exist.
        assert legacy.exists()
        assert global_db.exists()

    def test_migration_noop_when_no_legacy(self, tmp_path, monkeypatch):
        """No migration when memories.db does not exist."""
        monkeypatch.setattr(
            "memorymesh.store._LEGACY_DB",
            str(tmp_path / "memories.db"),
        )
        monkeypatch.setattr(
            "memorymesh.store._DEFAULT_GLOBAL_DB",
            str(tmp_path / "global.db"),
        )

        assert migrate_legacy_db() is False


# ------------------------------------------------------------------
# TestNoProjectStore
# ------------------------------------------------------------------


class TestNoProjectStore:
    """MemoryMesh with path=None (global-only mode)."""

    def test_remember_project_raises(self, tmp_path):
        """remember(scope='project') raises when no project store."""
        mesh = MemoryMesh(
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        with pytest.raises(RuntimeError, match="No project database"):
            mesh.remember("test", scope=PROJECT_SCOPE)

    def test_remember_global_works(self, tmp_path):
        """remember(scope='global') works without a project store."""
        mesh = MemoryMesh(
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mid = mesh.remember("global memory", scope=GLOBAL_SCOPE)
        assert isinstance(mid, str)
        assert mesh.count() == 1

    def test_recall_works(self, tmp_path):
        """recall() works in global-only mode."""
        mesh = MemoryMesh(
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("user likes cats", scope=GLOBAL_SCOPE)
        results = mesh.recall("cats")
        assert len(results) >= 1
        assert results[0].scope == GLOBAL_SCOPE

    def test_forget_all_project_returns_zero(self, tmp_path):
        """forget_all('project') returns 0 when no project store."""
        mesh = MemoryMesh(
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        assert mesh.forget_all(scope=PROJECT_SCOPE) == 0

    def test_count_project_returns_zero(self, tmp_path):
        """count(scope='project') returns 0 when no project store."""
        mesh = MemoryMesh(
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        assert mesh.count(scope=PROJECT_SCOPE) == 0


# ------------------------------------------------------------------
# TestGetTimeRange
# ------------------------------------------------------------------


class TestGetTimeRange:
    """get_time_range() with scope parameter."""

    def test_time_range_combined(self, tmp_path):
        """get_time_range() merges both stores."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("project", scope=PROJECT_SCOPE)
        mesh.remember("global", scope=GLOBAL_SCOPE)

        oldest, newest = mesh.get_time_range()
        assert oldest is not None
        assert newest is not None

    def test_time_range_empty(self, tmp_path):
        """get_time_range() returns (None, None) when empty."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        assert mesh.get_time_range() == (None, None)

    def test_time_range_project_only(self, tmp_path):
        """get_time_range(scope='project') only considers project."""
        mesh = MemoryMesh(
            path=str(tmp_path / "project.db"),
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        mesh.remember("global only", scope=GLOBAL_SCOPE)
        assert mesh.get_time_range(scope=PROJECT_SCOPE) == (None, None)

    def test_time_range_no_project(self, tmp_path):
        """get_time_range(scope='project') returns (None, None) with no project store."""
        mesh = MemoryMesh(
            global_path=str(tmp_path / "global.db"),
            embedding="none",
        )
        assert mesh.get_time_range(scope=PROJECT_SCOPE) == (None, None)
