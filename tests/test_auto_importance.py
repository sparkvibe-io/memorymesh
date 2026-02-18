"""Tests for heuristic-based auto-importance scoring.

Covers each heuristic signal individually, combined scoring behaviour,
edge cases, and integration with core.py's remember(auto_importance=True).
"""

from __future__ import annotations

from memorymesh import MemoryMesh, score_importance
from memorymesh.auto_importance import (
    _keyword_signal,
    _length_signal,
    _specificity_signal,
    _structure_signal,
)

# ===================================================================
# Length signal
# ===================================================================


class TestLengthSignal:
    """Tests for the text-length heuristic."""

    def test_very_short_text(self):
        """Texts under 20 chars get a low score."""
        assert _length_signal("ok") == 0.2
        assert _length_signal("a" * 19) == 0.2

    def test_short_text(self):
        """Texts 20-49 chars get a below-average score."""
        assert _length_signal("a" * 20) == 0.4
        assert _length_signal("a" * 49) == 0.4

    def test_medium_text(self):
        """Texts 50-199 chars get the baseline score."""
        assert _length_signal("a" * 50) == 0.5
        assert _length_signal("a" * 199) == 0.5

    def test_long_text(self):
        """Texts 200-499 chars get a higher score."""
        assert _length_signal("a" * 200) == 0.7
        assert _length_signal("a" * 499) == 0.7

    def test_very_long_text(self):
        """Texts 500+ chars get the highest length score."""
        assert _length_signal("a" * 500) == 0.8
        assert _length_signal("a" * 5000) == 0.8


# ===================================================================
# Keyword signal
# ===================================================================


class TestKeywordSignal:
    """Tests for the keyword booster/reducer heuristic."""

    def test_neutral_text(self):
        """Text with no special keywords returns baseline 0.5."""
        assert _keyword_signal("the cat sat on the mat") == 0.5

    def test_single_booster(self):
        """One booster keyword raises the score."""
        score = _keyword_signal("this is a critical issue")
        assert score > 0.5

    def test_multiple_boosters(self):
        """Multiple booster keywords raise the score more."""
        single = _keyword_signal("critical issue found")
        multiple = _keyword_signal("critical security architecture decision")
        assert multiple > single

    def test_single_reducer(self):
        """One reducer keyword lowers the score."""
        score = _keyword_signal("this is a temporary thing")
        assert score < 0.5

    def test_multiple_reducers(self):
        """Multiple reducer keywords lower the score more."""
        single = _keyword_signal("this is temporary")
        multiple = _keyword_signal("temporary todo maybe draft")
        assert multiple < single

    def test_mixed_boosters_and_reducers(self):
        """Boosters and reducers partially cancel each other out."""
        mixed = _keyword_signal("critical bug but maybe temporary fix")
        # Has 3 boosters (critical, bug, fix) and 2 reducers (maybe, temporary)
        # 0.5 + 3*0.08 - 2*0.06 = 0.62
        assert 0.55 < mixed < 0.7

    def test_clamped_at_one(self):
        """Score never exceeds 1.0 even with many boosters."""
        text = " ".join(
            [
                "decision",
                "architecture",
                "critical",
                "important",
                "always",
                "never",
                "bug",
                "fix",
                "security",
                "preference",
                "convention",
                "principle",
                "requirement",
                "breaking",
            ]
        )
        assert _keyword_signal(text) == 1.0

    def test_clamped_at_zero(self):
        """Score never goes below 0.0 even with many reducers."""
        text = " ".join(
            [
                "test",
                "trying",
                "maybe",
                "perhaps",
                "temporary",
                "todo",
                "wip",
                "experiment",
                "draft",
                "scratch",
                "placeholder",
                "stub",
                "mock",
                "hack",
                "workaround",
            ]
        )
        assert _keyword_signal(text) == 0.0

    def test_case_insensitive(self):
        """Keyword matching is case-insensitive."""
        lower = _keyword_signal("critical decision")
        upper = _keyword_signal("CRITICAL DECISION")
        mixed = _keyword_signal("Critical Decision")
        assert lower == upper == mixed


# ===================================================================
# Structure signal
# ===================================================================


class TestStructureSignal:
    """Tests for the code-structure heuristic."""

    def test_plain_text(self):
        """Text without code patterns gets a low structure score."""
        assert _structure_signal("the user likes dark mode") == 0.4

    def test_inline_code(self):
        """Text with inline backtick code gets a bump."""
        score = _structure_signal("use `pip install memorymesh` to install")
        assert score >= 0.6

    def test_function_definition(self):
        """Text with a function definition pattern gets a bump."""
        score = _structure_signal("the function def remember( stores data")
        assert score >= 0.6

    def test_multiple_patterns(self):
        """Multiple code patterns result in a higher score."""
        score = _structure_signal("import memorymesh; use `MemoryMesh` class with def remember(")
        assert score >= 0.75

    def test_many_patterns(self):
        """4+ code patterns reach the highest tier."""
        text = (
            "```python\n"
            "import memorymesh\n"
            "class MyAgent(Base):\n"
            "    def process(self):\n"
            "        mem.recall(`query`)\n"
            "```"
        )
        score = _structure_signal(text)
        assert score >= 0.9


# ===================================================================
# Specificity signal
# ===================================================================


class TestSpecificitySignal:
    """Tests for the specificity/proper-noun heuristic."""

    def test_vague_text(self):
        """Very generic text with no specificity markers scores low."""
        assert _specificity_signal("this is not very specific at all") == 0.3

    def test_file_path(self):
        """Text containing a file path gets a specificity boost."""
        score = _specificity_signal("edit the file src/memorymesh/core.py")
        assert score > 0.3

    def test_version_number(self):
        """Text with version numbers gets a specificity boost."""
        score = _specificity_signal("requires Python 3.9 or later")
        assert score > 0.3

    def test_url(self):
        """Text with a URL gets a specificity boost."""
        score = _specificity_signal("see https://example.com/docs for details")
        assert score > 0.3

    def test_camel_case(self):
        """Text with CamelCase identifiers gets a specificity boost."""
        score = _specificity_signal("the MemoryMesh class handles storage")
        assert score > 0.3

    def test_acronyms(self):
        """Text with uppercase acronyms gets a specificity boost."""
        score = _specificity_signal("uses JWT for API authentication over HTTP")
        assert score > 0.3

    def test_highly_specific(self):
        """Text full of specific references reaches the highest tier."""
        text = (
            "Fix src/memorymesh/core.py v2.1.0 MemoryMesh SQL injection "
            "in API endpoint https://example.com/security JWT token"
        )
        score = _specificity_signal(text)
        assert score >= 0.7


# ===================================================================
# Combined score_importance()
# ===================================================================


class TestScoreImportance:
    """Tests for the main public score_importance function."""

    def test_returns_float(self):
        """score_importance always returns a float."""
        result = score_importance("hello world")
        assert isinstance(result, float)

    def test_clamped_between_zero_and_one(self):
        """Result is always in [0.0, 1.0]."""
        for text in [
            "x",
            "a" * 1000,
            "critical security architecture decision always never",
            "temp todo maybe wip draft",
        ]:
            score = score_importance(text)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for {text!r}"

    def test_short_vague_text_low(self):
        """Very short, vague text scores below the baseline."""
        score = score_importance("ok")
        assert score < 0.5

    def test_important_technical_text_high(self):
        """Detailed, important, technical text scores above baseline."""
        text = (
            "Critical architecture decision: MemoryMesh v2.0 will use "
            "SQLite WAL mode for `concurrent_access()` in src/store.py. "
            "This is a security requirement for production deployment."
        )
        score = score_importance(text)
        assert score > 0.6

    def test_reducer_text_low(self):
        """Text loaded with reducer keywords scores lower."""
        score = score_importance("maybe try this temporary workaround test stub")
        assert score < 0.5

    def test_metadata_param_accepted(self):
        """metadata parameter is accepted without error (reserved for future use)."""
        score = score_importance("hello world", metadata={"source": "user"})
        assert isinstance(score, float)

    def test_none_metadata_accepted(self):
        """None metadata is accepted gracefully."""
        score = score_importance("hello world", metadata=None)
        assert isinstance(score, float)


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    """Tests for unusual inputs."""

    def test_whitespace_only_minimal(self):
        """Whitespace-only text (with at least one char) gets a low score."""
        # Memory dataclass rejects empty strings, but whitespace is valid
        score = score_importance("   ")
        assert 0.0 <= score <= 1.0
        assert score < 0.5  # whitespace is not important

    def test_very_long_text(self):
        """Very long text doesn't crash and stays in range."""
        text = "important decision about architecture. " * 200
        score = score_importance(text)
        assert 0.0 <= score <= 1.0

    def test_unicode_text(self):
        """Unicode content is handled without errors."""
        text = "L'architecture du systeme est tres importante pour la securite"
        score = score_importance(text)
        assert 0.0 <= score <= 1.0

    def test_emoji_text(self):
        """Emoji-laden text doesn't crash."""
        score = score_importance("fix the bug ASAP")
        assert 0.0 <= score <= 1.0

    def test_newlines_and_special_chars(self):
        """Text with newlines and special characters works."""
        text = "line1\nline2\n\n- bullet point\n  * nested"
        score = score_importance(text)
        assert 0.0 <= score <= 1.0

    def test_single_char(self):
        """Single character text returns a valid score."""
        score = score_importance("x")
        assert 0.0 <= score <= 1.0
        assert score < 0.5

    def test_numbers_only(self):
        """Numeric-only text returns a valid score."""
        score = score_importance("42")
        assert 0.0 <= score <= 1.0


# ===================================================================
# Integration with core.py
# ===================================================================


class TestCoreIntegration:
    """Tests for auto_importance integration with MemoryMesh.remember()."""

    def test_auto_importance_false_by_default(self, tmp_path):
        """By default, remember() uses the explicit importance value."""
        mesh = MemoryMesh(
            path=str(tmp_path / "mem.db"),
            embedding="none",
            global_path=str(tmp_path / "global.db"),
        )
        mem_id = mesh.remember("hello world", importance=0.9)
        mem = mesh.get(mem_id)
        assert mem is not None
        assert mem.importance == 0.9

    def test_auto_importance_overrides_explicit(self, tmp_path):
        """When auto_importance=True, the explicit importance is overridden."""
        mesh = MemoryMesh(
            path=str(tmp_path / "mem.db"),
            embedding="none",
            global_path=str(tmp_path / "global.db"),
        )
        text = (
            "Critical architecture decision: always use WAL mode "
            "for SQLite in production deployment of MemoryMesh v2.0"
        )
        mem_id = mesh.remember(text, importance=0.1, auto_importance=True)
        mem = mesh.get(mem_id)
        assert mem is not None
        # Auto-scored importance should be significantly higher than 0.1
        assert mem.importance > 0.1
        # And it should match score_importance directly
        expected = score_importance(text)
        assert abs(mem.importance - expected) < 0.01

    def test_auto_importance_low_text(self, tmp_path):
        """Auto-importance assigns low scores to trivial text."""
        mesh = MemoryMesh(
            path=str(tmp_path / "mem.db"),
            embedding="none",
            global_path=str(tmp_path / "global.db"),
        )
        mem_id = mesh.remember("ok", auto_importance=True)
        mem = mesh.get(mem_id)
        assert mem is not None
        assert mem.importance < 0.5

    def test_auto_importance_with_metadata(self, tmp_path):
        """auto_importance works alongside metadata."""
        mesh = MemoryMesh(
            path=str(tmp_path / "mem.db"),
            embedding="none",
            global_path=str(tmp_path / "global.db"),
        )
        text = (
            "Critical security fix in src/auth.py: the JWT validation was "
            "bypassed when the token contained a null byte. Always validate "
            "token format before decoding."
        )
        mem_id = mesh.remember(
            text,
            metadata={"source": "user"},
            auto_importance=True,
        )
        mem = mesh.get(mem_id)
        assert mem is not None
        assert mem.metadata == {"source": "user"}
        assert mem.importance > 0.5

    def test_auto_importance_global_scope(self, tmp_path):
        """auto_importance works with global scope."""
        mesh = MemoryMesh(
            path=str(tmp_path / "mem.db"),
            embedding="none",
            global_path=str(tmp_path / "global.db"),
        )
        text = "User preference: always use dark mode in all applications"
        mem_id = mesh.remember(text, scope="global", auto_importance=True)
        mem = mesh.get(mem_id)
        assert mem is not None
        expected = score_importance(text)
        assert abs(mem.importance - expected) < 0.01
