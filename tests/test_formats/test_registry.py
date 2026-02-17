"""Tests for the format adapter registry and factory (``memorymesh.formats``)."""

from __future__ import annotations

import pytest

from memorymesh.formats import (
    FormatAdapter,
    create_format_adapter,
    get_all_adapters,
    get_format_names,
)

# ---------------------------------------------------------------------------
# Registry / factory
# ---------------------------------------------------------------------------


def test_create_claude_adapter():
    adapter = create_format_adapter("claude")
    assert adapter.name == "claude"
    assert adapter.display_name == "Claude Code"


def test_create_codex_adapter():
    adapter = create_format_adapter("codex")
    assert adapter.name == "codex"
    assert adapter.display_name == "OpenAI Codex CLI"


def test_create_gemini_adapter():
    adapter = create_format_adapter("gemini")
    assert adapter.name == "gemini"
    assert adapter.display_name == "Google Gemini CLI"


def test_create_unknown_adapter():
    with pytest.raises(ValueError, match="Unknown format"):
        create_format_adapter("unknown")


def test_get_all_adapters():
    adapters = get_all_adapters()
    names = [a.name for a in adapters]
    assert "claude" in names
    assert "codex" in names
    assert "gemini" in names


def test_get_format_names():
    names = get_format_names()
    assert "claude" in names
    assert "codex" in names
    assert "gemini" in names
    assert names == sorted(names)


def test_all_adapters_are_format_adapter_instances():
    for adapter in get_all_adapters():
        assert isinstance(adapter, FormatAdapter)


def test_adapter_file_names():
    claude = create_format_adapter("claude")
    codex = create_format_adapter("codex")
    gemini = create_format_adapter("gemini")
    assert "MEMORY.md" in claude.file_names
    assert "AGENTS.md" in codex.file_names
    assert "GEMINI.md" in gemini.file_names
