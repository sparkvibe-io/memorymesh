"""Pluggable embedding providers for MemoryMesh.

Each provider implements a simple interface: given text, return a vector of
floats.  Providers are designed to be lazy-loaded so that heavy ML
dependencies are only imported when actually used.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class EmbeddingProvider(ABC):
    """Abstract base class for all embedding providers.

    Subclasses must implement :meth:`embed`.  A default
    :meth:`embed_batch` is provided that simply calls :meth:`embed` in a
    loop, but providers are encouraged to override it with a more
    efficient implementation when the underlying model/API supports
    batching.
    """

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Compute the embedding vector for a single piece of text.

        Args:
            text: The input text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Compute embeddings for multiple texts.

        The default implementation calls :meth:`embed` sequentially.
        Subclasses may override this for batch optimisations.

        Args:
            texts: A list of input texts.

        Returns:
            A list of embedding vectors, one per input text.
        """
        return [self.embed(t) for t in texts]

    @property
    def dimension(self) -> int | None:
        """Return the dimensionality of the embeddings, if known.

        Returns:
            The number of floats in each embedding vector, or ``None`` if
            the dimension is not known ahead of time.
        """
        return None


# ---------------------------------------------------------------------------
# Local (sentence-transformers)
# ---------------------------------------------------------------------------


class LocalEmbedding(EmbeddingProvider):
    """Embedding provider using ``sentence-transformers`` locally.

    The model is lazily loaded on the first call to :meth:`embed` so that
    import time and memory usage stay low until embeddings are actually
    needed.

    Args:
        model_name: The Hugging Face model identifier.  Defaults to
            ``all-MiniLM-L6-v2`` which is small, fast, and produces
            384-dimensional embeddings.
        device: PyTorch device string (``"cpu"``, ``"cuda"``, etc.).
            Defaults to ``"cpu"``.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._model: Any = None  # lazy-loaded SentenceTransformer

    def _load_model(self) -> None:
        """Import sentence-transformers and load the model."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "The 'sentence-transformers' package is required for local "
                "embeddings.  Install it with:\n\n"
                "    pip install sentence-transformers\n\n"
                "Or use a different embedding provider:\n"
                "    MemoryMesh(embedding='none')    # keyword search only\n"
                "    MemoryMesh(embedding='ollama')   # Ollama API\n"
                "    MemoryMesh(embedding='openai')   # OpenAI API"
            ) from exc

        logger.info(
            "Loading sentence-transformers model '%s' on %s ...",
            self._model_name,
            self._device,
        )
        self._model = SentenceTransformer(self._model_name, device=self._device)

    def embed(self, text: str) -> list[float]:
        """Compute the embedding for *text* using the local model.

        The model is loaded on first use.

        Args:
            text: Input text.

        Returns:
            384-dimensional float vector (for the default model).
        """
        if self._model is None:
            self._load_model()
        vector = self._model.encode(text, convert_to_numpy=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Compute embeddings for a batch of texts.

        Leverages sentence-transformers' native batching for efficiency.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []
        if self._model is None:
            self._load_model()
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

    @property
    def dimension(self) -> int:
        return 384  # all-MiniLM-L6-v2

    def __repr__(self) -> str:
        return f"LocalEmbedding(model={self._model_name!r}, device={self._device!r})"


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


class OllamaEmbedding(EmbeddingProvider):
    """Embedding provider using a locally-running Ollama server.

    Ollama must be running and accessible at the given ``base_url``.

    Args:
        model: The Ollama model name to use for embeddings.  Common
            choices include ``nomic-embed-text`` and ``all-minilm``.
        base_url: The Ollama API base URL.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")

    def embed(self, text: str) -> list[float]:
        """Compute the embedding via the Ollama ``/api/embed`` endpoint.

        Args:
            text: Input text.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            ConnectionError: If Ollama is not reachable.
            RuntimeError: If the API returns an error.
        """
        import json
        import urllib.error
        import urllib.request

        url = f"{self._base_url}/api/embed"
        payload = json.dumps({"model": self._model, "input": text}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Could not connect to Ollama at {self._base_url}. "
                "Is Ollama running?  Start it with: ollama serve"
            ) from exc

        embeddings = data.get("embeddings")
        if not embeddings:
            raise RuntimeError(
                f"Ollama returned an unexpected response: {data}"
            )
        return embeddings[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Compute embeddings for multiple texts via Ollama.

        Ollama's ``/api/embed`` endpoint supports passing a list of
        inputs for batch processing.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        import json
        import urllib.error
        import urllib.request

        url = f"{self._base_url}/api/embed"
        payload = json.dumps({"model": self._model, "input": texts}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Could not connect to Ollama at {self._base_url}. "
                "Is Ollama running?  Start it with: ollama serve"
            ) from exc

        embeddings = data.get("embeddings")
        if not embeddings:
            raise RuntimeError(
                f"Ollama returned an unexpected response: {data}"
            )
        return embeddings

    def __repr__(self) -> str:
        return (
            f"OllamaEmbedding(model={self._model!r}, "
            f"base_url={self._base_url!r})"
        )


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIEmbedding(EmbeddingProvider):
    """Embedding provider using the OpenAI Embeddings API.

    Requires a valid OpenAI API key, passed directly or set in the
    ``OPENAI_API_KEY`` environment variable.

    Args:
        api_key: OpenAI API key.  If ``None``, falls back to the
            ``OPENAI_API_KEY`` environment variable.
        model: The OpenAI embedding model name.
        base_url: API base URL (useful for Azure or compatible proxies).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        import os

        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "An OpenAI API key is required.  Pass it as:\n\n"
                "    MemoryMesh(embedding='openai', openai_api_key='sk-...')\n\n"
                "Or set the OPENAI_API_KEY environment variable."
            )
        self._model = model
        self._base_url = base_url.rstrip("/")

    def embed(self, text: str) -> list[float]:
        """Compute the embedding via the OpenAI API.

        Args:
            text: Input text.

        Returns:
            Embedding vector as a list of floats.
        """
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Compute embeddings for multiple texts via the OpenAI API.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors, in the same order as the inputs.
        """
        if not texts:
            return []

        import json
        import urllib.error
        import urllib.request

        url = f"{self._base_url}/embeddings"
        payload = json.dumps(
            {"model": self._model, "input": texts}
        ).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode() if exc.fp else ""
            raise RuntimeError(
                f"OpenAI API error ({exc.code}): {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Could not connect to OpenAI API at {self._base_url}: {exc}"
            ) from exc

        # Sort by index to guarantee ordering matches input.
        items = sorted(data.get("data", []), key=lambda d: d["index"])
        return [item["embedding"] for item in items]

    @property
    def dimension(self) -> int:
        return 1536  # text-embedding-3-small

    def __repr__(self) -> str:
        return f"OpenAIEmbedding(model={self._model!r})"


# ---------------------------------------------------------------------------
# Noop (keyword-only fallback)
# ---------------------------------------------------------------------------


class NoopEmbedding(EmbeddingProvider):
    """A no-operation embedding provider.

    Always returns an empty list.  Use this when you only need keyword /
    substring search and do not want to install any ML dependencies.
    """

    def embed(self, text: str) -> list[float]:
        """Return an empty embedding.

        Args:
            text: Ignored.

        Returns:
            An empty list.
        """
        return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return empty embeddings for all inputs.

        Args:
            texts: Ignored.

        Returns:
            A list of empty lists.
        """
        return [[] for _ in texts]

    @property
    def dimension(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "NoopEmbedding()"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDER_ALIASES: dict[str, type[EmbeddingProvider]] = {
    "local": LocalEmbedding,
    "sentence-transformers": LocalEmbedding,
    "ollama": OllamaEmbedding,
    "openai": OpenAIEmbedding,
    "none": NoopEmbedding,
    "noop": NoopEmbedding,
}


def create_embedding_provider(
    name: str, **kwargs: Any
) -> EmbeddingProvider:
    """Create an embedding provider by name.

    This is a convenience factory so that users can specify a provider as
    a simple string.

    Args:
        name: Provider name.  Supported values: ``"local"``,
            ``"sentence-transformers"``, ``"ollama"``, ``"openai"``,
            ``"none"`` / ``"noop"``.
        **kwargs: Forwarded to the provider's constructor.

    Returns:
        An :class:`EmbeddingProvider` instance.

    Raises:
        ValueError: If *name* is not a recognised provider.

    Examples::

        provider = create_embedding_provider("local")
        provider = create_embedding_provider("ollama", model="nomic-embed-text")
        provider = create_embedding_provider("openai", api_key="sk-...")
        provider = create_embedding_provider("none")
    """
    cls = _PROVIDER_ALIASES.get(name.lower().strip())
    if cls is None:
        supported = ", ".join(sorted(_PROVIDER_ALIASES))
        raise ValueError(
            f"Unknown embedding provider {name!r}. "
            f"Supported providers: {supported}"
        )
    return cls(**kwargs)
