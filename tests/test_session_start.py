"""Tests for session_start() and category-aware remember()."""

from __future__ import annotations

import os

import pytest

from memorymesh import MemoryMesh


@pytest.fixture()
def mesh(tmp_path: str) -> MemoryMesh:
    """Create a MemoryMesh with both project and global stores."""
    project_db = os.path.join(str(tmp_path), "project", "memories.db")
    global_db = os.path.join(str(tmp_path), "global", "global.db")
    return MemoryMesh(path=project_db, global_path=global_db, embedding="none")


class TestCategoryRemember:
    """Test remember() with category parameter."""

    def test_explicit_category_routes_to_global(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("I prefer dark mode", category="preference")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "global"
        assert mem.metadata.get("category") == "preference"

    def test_explicit_category_routes_to_project(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Use SQLite for storage", category="decision")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "project"
        assert mem.metadata.get("category") == "decision"

    def test_category_overrides_explicit_scope(self, mesh: MemoryMesh) -> None:
        # Even though scope="project", category="preference" should route to global
        mid = mesh.remember(
            "I prefer Python",
            scope="project",
            category="preference",
        )
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "global"

    def test_invalid_category_raises(self, mesh: MemoryMesh) -> None:
        with pytest.raises(ValueError, match="Invalid category"):
            mesh.remember("test", category="nonexistent")

    def test_auto_categorize(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember(
            "Never push to main without code review",
            auto_categorize=True,
        )
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.metadata.get("category") == "guardrail"
        assert mem.scope == "global"

    def test_auto_categorize_enables_auto_importance(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember(
            "Critical security vulnerability in auth module",
            auto_categorize=True,
        )
        mem = mesh.get(mid)
        assert mem is not None
        # Auto-importance should produce a non-default score
        assert mem.importance != 0.5

    def test_category_stored_in_metadata(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Forgot to add tests", category="mistake")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.metadata["category"] == "mistake"

    def test_remember_without_category_still_works(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Just a regular memory")
        mem = mesh.get(mid)
        assert mem is not None
        assert "category" not in mem.metadata

    def test_existing_metadata_preserved(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember(
            "I prefer TypeScript",
            metadata={"source": "user"},
            category="preference",
        )
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.metadata["source"] == "user"
        assert mem.metadata["category"] == "preference"


class TestSessionStart:
    """Test session_start() method."""

    def test_empty_stores_return_empty_lists(self, mesh: MemoryMesh) -> None:
        result = mesh.session_start()
        assert isinstance(result, dict)
        assert result["user_profile"] == []
        assert result["guardrails"] == []
        assert result["common_mistakes"] == []
        assert result["common_questions"] == []
        assert result["project_context"] == []
        assert result["last_session"] == []

    def test_returns_all_expected_keys(self, mesh: MemoryMesh) -> None:
        result = mesh.session_start()
        expected_keys = {
            "user_profile", "guardrails", "common_mistakes",
            "common_questions", "project_context", "last_session",
        }
        assert set(result.keys()) == expected_keys

    def test_global_categories_populated(self, mesh: MemoryMesh) -> None:
        mesh.remember("I am a senior Python developer", category="personality")
        mesh.remember("I prefer dark mode", category="preference")
        mesh.remember("Never auto-commit", category="guardrail")
        mesh.remember("Forgot tests before pushing", category="mistake")
        mesh.remember("Why does the build fail?", category="question")

        result = mesh.session_start()
        assert len(result["user_profile"]) == 2  # personality + preference
        assert len(result["guardrails"]) == 1
        assert len(result["common_mistakes"]) == 1
        assert len(result["common_questions"]) == 1

    def test_project_categories_populated(self, mesh: MemoryMesh) -> None:
        mesh.remember("Use SQLite for storage", category="decision")
        mesh.remember("Google-style docstrings", category="pattern")
        mesh.remember("Entry point is core.py", category="context")

        result = mesh.session_start()
        # project_context merges context + decision + pattern
        assert len(result["project_context"]) == 3

    def test_session_summary_returns_latest(self, mesh: MemoryMesh) -> None:
        mesh.remember("First session: set up project", category="session_summary", importance=0.5)
        mesh.remember("Second session: added auth", category="session_summary", importance=0.9)

        result = mesh.session_start()
        # Should return only the most important session summary
        assert len(result["last_session"]) == 1
        assert "auth" in result["last_session"][0]

    def test_max_per_category_limit(self, mesh: MemoryMesh) -> None:
        for i in range(10):
            mesh.remember(f"Guardrail rule {i}", category="guardrail")

        result = mesh.session_start()
        assert len(result["guardrails"]) <= 5

    def test_project_context_query(self, mesh: MemoryMesh) -> None:
        mesh.remember("The auth module uses JWT tokens", category="context")
        mesh.remember("Database is PostgreSQL", category="context")

        result = mesh.session_start(project_context="authentication")
        assert len(result["project_context"]) >= 1

    def test_result_contains_strings_not_memory_objects(self, mesh: MemoryMesh) -> None:
        mesh.remember("I prefer Python", category="preference")

        result = mesh.session_start()
        for _key, value in result.items():
            assert isinstance(value, list)
            for item in value:
                assert isinstance(item, str)

    def test_no_project_store_still_works(self, tmp_path: str) -> None:
        global_db = os.path.join(str(tmp_path), "global2", "global.db")
        mesh = MemoryMesh(path=None, global_path=global_db, embedding="none")

        mesh.remember("I prefer dark mode", category="preference", scope="global")
        result = mesh.session_start()
        assert "I prefer dark mode" in result["user_profile"]
        assert result["project_context"] == []
