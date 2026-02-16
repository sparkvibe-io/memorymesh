"""Core MemoryMesh class -- the main entry point for the library.

Ties together storage, embeddings, and relevance scoring into a clean,
three-method API: :meth:`remember`, :meth:`recall`, :meth:`forget`.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .embeddings import EmbeddingProvider, NoopEmbedding, create_embedding_provider
from .memory import Memory
from .relevance import RelevanceEngine, RelevanceWeights
from .store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryMesh:
    """The SQLite of AI Memory.

    An embeddable, zero-dependency AI memory library that any application
    can integrate in three lines of code::

        from memorymesh import MemoryMesh

        mem = MemoryMesh()
        mem.remember("The user prefers dark mode.")
        results = mem.recall("What theme does the user like?")

    Args:
        path: Path to the SQLite database file.  Defaults to
            ``~/.memorymesh/memories.db``.
        embedding: Embedding provider to use.  Accepts a string name
            (``"local"``, ``"ollama"``, ``"openai"``, ``"none"``) or an
            :class:`EmbeddingProvider` instance for full control.
        relevance_weights: Optional :class:`RelevanceWeights` to tune
            how memories are ranked during recall.
        **kwargs: Extra options forwarded to the embedding provider
            constructor.  Common keys:

            * ``ollama_model`` -- Ollama model name (default
              ``"nomic-embed-text"``).
            * ``ollama_base_url`` -- Ollama server URL.
            * ``openai_api_key`` -- OpenAI API key.
            * ``openai_model`` -- OpenAI embedding model.
            * ``openai_base_url`` -- OpenAI-compatible API URL.
            * ``local_model`` -- sentence-transformers model name.
            * ``local_device`` -- PyTorch device for local embeddings.
    """

    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        embedding: str | EmbeddingProvider = "local",
        relevance_weights: RelevanceWeights | None = None,
        **kwargs: Any,
    ) -> None:
        # -- Storage -----------------------------------------------------
        self._store = MemoryStore(path=path)

        # -- Embedding provider ------------------------------------------
        if isinstance(embedding, EmbeddingProvider):
            self._embedder = embedding
        else:
            self._embedder = self._build_embedder(embedding, **kwargs)

        # -- Relevance engine --------------------------------------------
        self._engine = RelevanceEngine(weights=relevance_weights)

        logger.info(
            "MemoryMesh initialised  store=%r  embedder=%r",
            self._store,
            self._embedder,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def remember(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        importance: float = 0.5,
        decay_rate: float = 0.01,
    ) -> str:
        """Store a new memory.

        Args:
            text: The textual content to remember.
            metadata: Optional key-value metadata to attach.
            importance: Importance score in ``[0, 1]``.  Higher values
                make the memory more prominent during recall.
            decay_rate: Rate at which importance decays over time.
                ``0`` means the memory never decays.

        Returns:
            The unique ID of the newly created memory.
        """
        # Compute embedding (may be empty list for NoopEmbedding).
        emb = self._safe_embed(text)

        memory = Memory(
            text=text,
            metadata=metadata or {},
            embedding=emb if emb else None,
            importance=importance,
            decay_rate=decay_rate,
        )

        self._store.save(memory)
        logger.debug("Remembered memory %s (%d chars)", memory.id, len(text))
        return memory.id

    def recall(
        self,
        query: str,
        k: int = 5,
        min_relevance: float = 0.0,
    ) -> list[Memory]:
        """Recall the most relevant memories for a query.

        Uses vector similarity (when embeddings are available) combined
        with recency, importance, and access frequency to rank results.
        Falls back to keyword search when the embedding provider is
        :class:`NoopEmbedding`.

        Args:
            query: Natural-language query describing what you want to
                recall.
            k: Maximum number of memories to return.
            min_relevance: Discard results scoring below this threshold.

        Returns:
            Up to *k* :class:`Memory` objects sorted by descending
            relevance.
        """
        query_embedding = self._safe_embed(query)

        if not query_embedding:
            # Fallback: keyword search only.
            candidates = self._store.search_by_text(query, limit=k * 4)
        else:
            # Vector search over all memories that have embeddings.
            candidates = self._store.get_all_with_embeddings()

            # Also include keyword matches so we don't miss exact hits.
            keyword_hits = self._store.search_by_text(query, limit=k * 2)
            seen_ids = {m.id for m in candidates}
            for hit in keyword_hits:
                if hit.id not in seen_ids:
                    candidates.append(hit)

        if not candidates:
            return []

        # Apply time-based decay before ranking.
        self._engine.apply_decay(candidates)

        # Rank and return top-k.
        results = self._engine.rank(
            candidates,
            query_embedding=query_embedding if query_embedding else None,
            k=k,
            min_relevance=min_relevance,
        )

        # Update access counts for returned memories.
        for mem in results:
            self._store.update_access(mem.id)
            mem.access_count += 1

        return results

    def forget(self, memory_id: str) -> bool:
        """Forget (delete) a specific memory.

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            ``True`` if the memory was found and deleted, ``False``
            otherwise.
        """
        deleted = self._store.delete(memory_id)
        if deleted:
            logger.debug("Forgot memory %s", memory_id)
        return deleted

    def forget_all(self) -> int:
        """Forget all memories.

        Returns:
            The number of memories deleted.
        """
        count = self._store.clear()
        logger.info("Forgot all %d memories", count)
        return count

    def count(self) -> int:
        """Return the total number of stored memories.

        Returns:
            An integer count.
        """
        return self._store.count()

    def list(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Memory]:
        """List memories with pagination.

        Args:
            limit: Maximum number of memories to return.
            offset: Number of memories to skip.

        Returns:
            A list of :class:`Memory` objects ordered by most recently
            updated first.
        """
        return self._store.list_all(limit=limit, offset=offset)

    def search(self, text: str, k: int = 5) -> list[Memory]:
        """Search memories by text similarity.

        This is a convenience alias for :meth:`recall`.

        Args:
            text: The search query.
            k: Maximum number of results.

        Returns:
            Up to *k* relevant memories.
        """
        return self.recall(query=text, k=k)

    def get(self, memory_id: str) -> Memory | None:
        """Retrieve a single memory by ID.

        Args:
            memory_id: The unique identifier.

        Returns:
            The :class:`Memory` if found, otherwise ``None``.
        """
        return self._store.get(memory_id)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying database connection."""
        self._store.close()

    def __enter__(self) -> MemoryMesh:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_embedder(name: str, **kwargs: Any) -> EmbeddingProvider:
        """Translate user-friendly kwargs to provider-specific ones."""
        provider_kwargs: dict[str, Any] = {}

        name_lower = name.lower().strip()

        if name_lower == "ollama":
            if "ollama_model" in kwargs:
                provider_kwargs["model"] = kwargs["ollama_model"]
            if "ollama_base_url" in kwargs:
                provider_kwargs["base_url"] = kwargs["ollama_base_url"]

        elif name_lower == "openai":
            if "openai_api_key" in kwargs:
                provider_kwargs["api_key"] = kwargs["openai_api_key"]
            if "openai_model" in kwargs:
                provider_kwargs["model"] = kwargs["openai_model"]
            if "openai_base_url" in kwargs:
                provider_kwargs["base_url"] = kwargs["openai_base_url"]

        elif name_lower in ("local", "sentence-transformers"):
            if "local_model" in kwargs:
                provider_kwargs["model_name"] = kwargs["local_model"]
            if "local_device" in kwargs:
                provider_kwargs["device"] = kwargs["local_device"]

        return create_embedding_provider(name, **provider_kwargs)

    def _safe_embed(self, text: str) -> list[float]:
        """Embed text, returning an empty list on failure.

        Catches and logs exceptions from the embedding provider so that
        a temporary embedding failure does not crash the application.

        Args:
            text: Input text.

        Returns:
            Embedding vector, or an empty list if embedding failed or
            the provider is :class:`NoopEmbedding`.
        """
        if isinstance(self._embedder, NoopEmbedding):
            return []
        try:
            return self._embedder.embed(text)
        except Exception:
            logger.warning(
                "Embedding failed for text (%.40s...), falling back to "
                "keyword search.",
                text,
                exc_info=True,
            )
            return []

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"MemoryMesh(store={self._store!r}, "
            f"embedder={self._embedder!r})"
        )
