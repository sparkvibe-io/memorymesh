"""Tests for subject-based scope inference."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator

import pytest

from memorymesh.categories import infer_scope
from memorymesh.core import MemoryMesh

# ---------------------------------------------------------------------------
# Unit tests for infer_scope()
# ---------------------------------------------------------------------------


class TestInferScopeUserSubject:
    """Text about the user should infer global scope."""

    def test_user_prefers(self) -> None:
        assert infer_scope("User prefers dark mode in all editors") == "global"

    def test_user_likes(self) -> None:
        assert infer_scope("User likes functional programming style") == "global"

    def test_user_always(self) -> None:
        assert infer_scope("User always runs tests before committing") == "global"

    def test_possessive_name_pattern(self) -> None:
        assert infer_scope("Krishna's patterns: asks questions before acting") == "global"

    def test_possessive_name_workflow(self) -> None:
        assert infer_scope("Alice's workflow: review PR, then merge") == "global"

    def test_across_all_projects(self) -> None:
        assert infer_scope("This preference applies across all projects") == "global"

    def test_interaction_pattern(self) -> None:
        assert infer_scope("Interaction pattern: prefers speed once decided") == "global"

    def test_communication_style(self) -> None:
        assert infer_scope("Communication style: concise, direct, no fluff") == "global"

    def test_coding_style(self) -> None:
        assert infer_scope("Coding style: functional over OOP when possible") == "global"

    def test_personal_preference(self) -> None:
        assert infer_scope("Personal preference: always use type hints") == "global"


class TestInferScopeProjectSubject:
    """Text about the project should infer project scope."""

    def test_file_path(self) -> None:
        assert infer_scope("Entry point is src/memorymesh/core.py") == "project"

    def test_test_path(self) -> None:
        assert infer_scope("Tests are in tests/ directory") == "project"

    def test_pyproject_toml(self) -> None:
        assert infer_scope("pyproject.toml configured with hatchling") == "project"

    def test_implementation_state(self) -> None:
        assert infer_scope("Implementation state (2026-02-17): Phase 1 complete") == "project"

    def test_version_date(self) -> None:
        assert infer_scope("v0.1.0 released 2026-02-16") == "project"

    def test_tests_passing(self) -> None:
        assert infer_scope("633 tests pass, 3 skipped, ruff clean") == "project"

    def test_commit_hash(self) -> None:
        assert infer_scope("Committed as commit 4fb7df3 on main") == "project"

    def test_python_file(self) -> None:
        assert infer_scope("Modified core.py to add update method") == "project"

    def test_product_name_match(self) -> None:
        result = infer_scope(
            "MemoryMesh is an embeddable AI memory library",
            project_name="MemoryMesh",
        )
        assert result == "project"


class TestInferScopeNoSignal:
    """Ambiguous text should return None."""

    def test_generic_text(self) -> None:
        assert infer_scope("SQLite uses WAL mode for concurrency") is None

    def test_short_text(self) -> None:
        assert infer_scope("Important decision made") is None

    def test_empty_text(self) -> None:
        assert infer_scope("") is None


class TestInferScopeConflictResolution:
    """When both user and project signals are present, the stronger wins."""

    def test_user_wins_when_stronger(self) -> None:
        # Multiple user signals vs one project signal
        text = "User prefers and user always likes to keep core.py clean"
        result = infer_scope(text)
        assert result == "global"

    def test_project_wins_when_stronger(self) -> None:
        # Multiple project signals vs one user signal
        text = "User prefers src/memorymesh/core.py over store.py for the main entry in tests/"
        result = infer_scope(text)
        assert result == "project"

    def test_product_name_adds_weight(self) -> None:
        # User signal + product name → product name adds 2, user adds 1
        text = "User prefers MemoryMesh for all memory tasks"
        result = infer_scope(text, project_name="MemoryMesh")
        assert result == "project"


# ---------------------------------------------------------------------------
# Integration tests: remember() with scope inference
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def mesh(tmp_dir: str) -> Generator[MemoryMesh, None, None]:
    db_path = os.path.join(tmp_dir, "project.db")
    global_path = os.path.join(tmp_dir, "global.db")
    m = MemoryMesh(path=db_path, global_path=global_path, embedding="none")
    yield m
    m.close()


class TestRememberScopeInference:
    """remember() should auto-infer scope when not explicitly provided."""

    def test_user_text_goes_global(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("User prefers dark mode everywhere")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "global"

    def test_project_text_goes_project(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Entry point is src/memorymesh/core.py")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "project"

    def test_explicit_scope_respected(self, mesh: MemoryMesh) -> None:
        # Even though text is user-focused, explicit scope wins.
        mid = mesh.remember("User prefers dark mode", scope="project")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "project"

    def test_category_routing_still_works(self, mesh: MemoryMesh) -> None:
        # Category routing: "preference" → global.
        mid = mesh.remember("Some neutral text", category="preference")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "global"

    def test_no_signal_defaults_to_project(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("SQLite uses WAL mode for concurrency")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "project"

    def test_name_pattern_goes_global(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Krishna's patterns: tests CLI hands-on, wants brutal honesty")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "global"

    def test_auto_categorize_with_inference(self, mesh: MemoryMesh) -> None:
        # auto_categorize gives "pattern" (→ project), but subject is user → global
        mid = mesh.remember(
            "Krishna's workflow preference: always review before merge",
            auto_categorize=True,
        )
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.scope == "global"
