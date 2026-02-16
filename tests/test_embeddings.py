"""Tests for embedding providers.

Covers the NoopEmbedding provider and the factory function.  Tests for
real embedding providers (Ollama, OpenAI, local) are skipped if the
required dependencies are not installed.
"""

from __future__ import annotations

import pytest

from memorymesh.embeddings import NoopEmbedding
from memorymesh.embeddings import create_embedding_provider as create_provider

# ------------------------------------------------------------------
# NoopEmbedding
# ------------------------------------------------------------------


def test_noop_embedding():
    """NoopEmbedding.embed() returns an empty list for any input."""
    provider = NoopEmbedding()
    result = provider.embed("any text at all")
    assert result == []


def test_noop_batch():
    """NoopEmbedding.embed_batch() returns a list of empty lists."""
    provider = NoopEmbedding()
    texts = ["one", "two", "three"]
    results = provider.embed_batch(texts)

    assert len(results) == len(texts)
    for r in results:
        assert r == []


def test_noop_dimension():
    """NoopEmbedding reports dimension as 0."""
    provider = NoopEmbedding()
    assert provider.dimension == 0


# ------------------------------------------------------------------
# Factory: create_provider
# ------------------------------------------------------------------


def test_create_provider_none():
    """create_provider('none') returns a NoopEmbedding."""
    provider = create_provider("none")
    assert isinstance(provider, NoopEmbedding)


def test_create_provider_unknown():
    """create_provider() raises ValueError for an unrecognized provider name."""
    with pytest.raises(ValueError, match=r"[Uu]nknown"):
        create_provider("nonexistent_provider")


# ------------------------------------------------------------------
# Real providers (skipped if dependencies are missing)
# ------------------------------------------------------------------


class TestOllamaEmbedding:
    """Tests for OllamaEmbedding (requires ollama package and server)."""

    @pytest.fixture(autouse=True)
    def _skip_if_unavailable(self):
        pytest.importorskip("httpx", reason="httpx not installed")
        # Even with httpx installed, the Ollama server may not be running.
        # These tests are intended for CI or local dev with Ollama available.

    @pytest.mark.skip(reason="Requires running Ollama server")
    def test_ollama_embed(self):
        """OllamaEmbedding produces a non-empty vector."""
        provider = create_provider("ollama", model="nomic-embed-text")
        result = provider.embed("test sentence")
        assert isinstance(result, list)
        assert len(result) > 0


class TestOpenAIEmbedding:
    """Tests for OpenAIEmbedding (requires openai package and API key)."""

    @pytest.fixture(autouse=True)
    def _skip_if_unavailable(self):
        pytest.importorskip("openai", reason="openai package not installed")

    @pytest.mark.skip(reason="Requires valid OpenAI API key")
    def test_openai_embed(self):
        """OpenAIEmbedding produces a non-empty vector."""
        import os

        provider = create_provider("openai", api_key=os.getenv("OPENAI_API_KEY"))
        result = provider.embed("test sentence")
        assert isinstance(result, list)
        assert len(result) > 0


class TestLocalEmbedding:
    """Tests for local/sentence-transformer based embeddings."""

    @pytest.fixture(autouse=True)
    def _skip_if_unavailable(self):
        pytest.importorskip(
            "sentence_transformers",
            reason="sentence-transformers not installed",
        )

    @pytest.mark.skip(reason="Requires model download; run manually")
    def test_local_embed(self):
        """Local embedding produces a non-empty vector."""
        provider = create_provider("local")
        result = provider.embed("test sentence")
        assert isinstance(result, list)
        assert len(result) > 0
