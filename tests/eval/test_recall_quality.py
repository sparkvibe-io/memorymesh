"""Recall quality evaluation tests.

Tests that MemoryMesh's recall pipeline returns relevant results for
various query patterns.  Uses keyword-only mode (embedding='none') for
deterministic, reproducible tests.

Note: keyword-only mode uses LIKE substring matching.  Queries must
contain a substring that actually appears in the stored text.
"""
from __future__ import annotations

import pytest

from .conftest import mean_reciprocal_rank, precision_at_k, recall_at_k


class TestPreferenceRecall:
    """Test that user preferences are retrievable by keyword substring."""

    def test_dark_mode_preference(self, populated_mesh):
        results = populated_mesh.recall("dark mode", k=5)
        texts = [m.text for m in results]
        assert any("dark mode" in t for t in texts)

    def test_language_preference(self, populated_mesh):
        results = populated_mesh.recall("TypeScript", k=5)
        texts = [m.text for m in results]
        assert any("TypeScript" in t for t in texts)

    def test_formatting_preference(self, populated_mesh):
        results = populated_mesh.recall("tabs over spaces", k=5)
        texts = [m.text for m in results]
        assert any("tabs" in t.lower() or "spaces" in t.lower() for t in texts)


class TestDecisionContinuity:
    """Test that architectural decisions are retrievable."""

    def test_storage_decision(self, populated_mesh):
        results = populated_mesh.recall("SQLite", k=5)
        texts = [m.text for m in results]
        assert any("SQLite" in t for t in texts)

    def test_architecture_pattern(self, populated_mesh):
        results = populated_mesh.recall("dual-store", k=5)
        texts = [m.text for m in results]
        assert any("dual-store" in t for t in texts)


class TestStaleOverride:
    """Test that updated facts outrank stale ones."""

    def test_newer_memory_available(self, eval_mesh):
        """Store a fact, then update it -- both should be retrievable."""
        eval_mesh.remember("Server runs on port 3000", importance=0.5)
        eval_mesh.remember("Server runs on port 4000", importance=0.7)

        results = eval_mesh.recall("runs on port", k=5)
        texts = [m.text for m in results]
        assert any("port" in t for t in texts)
        # Higher importance should rank first
        if len(results) >= 2:
            assert results[0].importance >= results[1].importance


class TestCrossScopeIsolation:
    """Test that scope filtering works correctly."""

    def test_project_scope_only(self, populated_mesh):
        results = populated_mesh.recall("SQLite", k=10, scope="project")
        for mem in results:
            assert mem.scope == "project"

    def test_global_scope_only(self, populated_mesh):
        results = populated_mesh.recall("dark mode", k=10, scope="global")
        for mem in results:
            assert mem.scope == "global"

    def test_both_scopes_by_default(self, populated_mesh):
        results = populated_mesh.recall("mode", k=20)
        # "mode" appears in "dark mode" (global) and "WAL journal mode" (project)
        assert len(results) > 0


class TestCategoryRouting:
    """Test that categorized memories end up in the right scope."""

    def test_preference_routes_to_global(self, eval_mesh):
        mid = eval_mesh.remember(
            "I prefer vim over emacs",
            category="preference",
        )
        mem = eval_mesh.get(mid)
        assert mem is not None
        assert mem.scope == "global"

    def test_decision_routes_to_project(self, eval_mesh):
        mid = eval_mesh.remember(
            "Decided to use PostgreSQL for production",
            category="decision",
        )
        mem = eval_mesh.get(mid)
        assert mem is not None
        assert mem.scope == "project"

    def test_guardrail_routes_to_global(self, eval_mesh):
        mid = eval_mesh.remember(
            "Never commit secrets to git",
            category="guardrail",
        )
        mem = eval_mesh.get(mid)
        assert mem is not None
        assert mem.scope == "global"


class TestImportanceRanking:
    """Test that importance affects ranking."""

    def test_high_importance_ranks_first(self, eval_mesh):
        eval_mesh.remember("low importance fact about testing", importance=0.1)
        eval_mesh.remember("high importance fact about testing", importance=0.9)

        results = eval_mesh.recall("fact about testing", k=5)
        if len(results) >= 2:
            # Higher importance should generally rank first
            assert results[0].importance >= results[1].importance


class TestMetrics:
    """Test precision and recall metrics computation."""

    def test_precision_at_k_perfect(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        assert precision_at_k(retrieved, relevant, 3) == 1.0

    def test_precision_at_k_half(self):
        retrieved = ["a", "x", "b", "y"]
        relevant = {"a", "b"}
        assert precision_at_k(retrieved, relevant, 4) == 0.5

    def test_recall_at_k(self):
        retrieved = ["a", "x"]
        relevant = {"a", "b", "c"}
        assert recall_at_k(retrieved, relevant, 2) == pytest.approx(1 / 3)

    def test_mrr(self):
        retrieved = ["x", "a", "y"]
        relevant = {"a"}
        assert mean_reciprocal_rank(retrieved, relevant) == 0.5

    def test_mrr_first_position(self):
        retrieved = ["a", "x", "y"]
        relevant = {"a"}
        assert mean_reciprocal_rank(retrieved, relevant) == 1.0

    def test_mrr_not_found(self):
        retrieved = ["x", "y", "z"]
        relevant = {"a"}
        assert mean_reciprocal_rank(retrieved, relevant) == 0.0
