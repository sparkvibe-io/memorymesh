"""Tests for the categories module."""

from __future__ import annotations

import pytest

from memorymesh.categories import (
    CATEGORY_SCOPE_MAP,
    GLOBAL_CATEGORIES,
    PROJECT_CATEGORIES,
    VALID_CATEGORIES,
    auto_categorize,
    scope_for_category,
    validate_category,
)


class TestConstants:
    """Test category constants."""

    def test_valid_categories_is_frozenset(self) -> None:
        assert isinstance(VALID_CATEGORIES, frozenset)

    def test_all_categories_present(self) -> None:
        expected = {
            "preference", "guardrail", "mistake", "personality",
            "question", "decision", "pattern", "context", "session_summary",
        }
        assert expected == VALID_CATEGORIES

    def test_global_categories(self) -> None:
        assert {"preference", "guardrail", "mistake", "personality", "question"} == GLOBAL_CATEGORIES

    def test_project_categories(self) -> None:
        assert {"decision", "pattern", "context", "session_summary"} == PROJECT_CATEGORIES

    def test_scope_map_covers_all(self) -> None:
        assert set(CATEGORY_SCOPE_MAP.keys()) == VALID_CATEGORIES


class TestValidateCategory:
    """Test validate_category()."""

    def test_valid_categories_pass(self) -> None:
        for cat in VALID_CATEGORIES:
            validate_category(cat)  # should not raise

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid category"):
            validate_category("nonexistent")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_category("")


class TestScopeForCategory:
    """Test scope_for_category()."""

    def test_global_categories_return_global(self) -> None:
        for cat in GLOBAL_CATEGORIES:
            assert scope_for_category(cat) == "global"

    def test_project_categories_return_project(self) -> None:
        for cat in PROJECT_CATEGORIES:
            assert scope_for_category(cat) == "project"

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(ValueError):
            scope_for_category("invalid")


class TestAutoCategorize:
    """Test auto_categorize()."""

    def test_preference_detected(self) -> None:
        assert auto_categorize("I prefer Python over JavaScript") == "preference"
        assert auto_categorize("Always use black for formatting") == "preference"

    def test_guardrail_detected(self) -> None:
        assert auto_categorize("Never auto-commit without asking") == "guardrail"
        assert auto_categorize("Don't push to main directly") == "guardrail"
        assert auto_categorize("Must not expose API keys") == "guardrail"

    def test_mistake_detected(self) -> None:
        assert auto_categorize("Forgot to run tests before pushing") == "mistake"
        assert auto_categorize("The bug was caused by a race condition") == "mistake"
        assert auto_categorize("Lesson learned: always check edge cases") == "mistake"

    def test_personality_detected(self) -> None:
        assert auto_categorize("I am a senior Python developer") == "personality"
        assert auto_categorize("My role is tech lead at a healthcare startup") == "personality"
        assert auto_categorize("I work on backend systems") == "personality"

    def test_question_detected(self) -> None:
        assert auto_categorize("Why does the build fail intermittently?") == "question"
        assert auto_categorize("How does the auth module handle refresh tokens?") == "question"
        assert auto_categorize("I have a concern about the database schema") == "question"

    def test_decision_detected(self) -> None:
        assert auto_categorize("Decided to use SQLite over PostgreSQL") == "decision"
        assert auto_categorize("We chose JWT for authentication") == "decision"
        assert auto_categorize("The architecture uses a microservices approach") == "decision"

    def test_pattern_detected(self) -> None:
        assert auto_categorize("Convention: use Google docstrings everywhere") == "pattern"
        assert auto_categorize("The coding standard requires type hints on all public functions") == "pattern"

    def test_session_summary_detected(self) -> None:
        assert auto_categorize("Session summary: implemented auth module, 15 tests added") == "session_summary"

    def test_context_fallback(self) -> None:
        assert auto_categorize("Main entry point is src/core.py") == "context"
        assert auto_categorize("The project uses hatchling for packaging") == "context"

    def test_metadata_hint_respected(self) -> None:
        result = auto_categorize(
            "Some random text here",
            metadata={"category": "guardrail"},
        )
        assert result == "guardrail"

    def test_invalid_metadata_hint_ignored(self) -> None:
        result = auto_categorize(
            "I prefer dark mode",
            metadata={"category": "nonexistent"},
        )
        assert result == "preference"

    def test_none_metadata(self) -> None:
        result = auto_categorize("I prefer tabs over spaces", metadata=None)
        assert result == "preference"
