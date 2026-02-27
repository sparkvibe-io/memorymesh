"""Core MemoryMesh class -- the main entry point for the library.

Ties together storage, embeddings, and relevance scoring into a clean,
three-method API: :meth:`remember`, :meth:`recall`, :meth:`forget`.
"""

from __future__ import annotations

import builtins
import logging
import os
from typing import Any

from .auto_importance import score_importance
from .categories import CATEGORY_SCOPE_MAP, GLOBAL_CATEGORIES, PROJECT_CATEGORIES, validate_category
from .categories import auto_categorize as _auto_categorize
from .categories import infer_scope as _infer_scope
from .compaction import CompactionResult
from .contradiction import ConflictMode, find_contradictions
from .embeddings import EmbeddingProvider, NoopEmbedding, create_embedding_provider
from .memory import GLOBAL_SCOPE, PROJECT_SCOPE, Memory, validate_scope
from .privacy import check_for_secrets
from .privacy import redact_secrets as _redact_secrets
from .relevance import RelevanceEngine, RelevanceWeights
from .store import _DEFAULT_GLOBAL_DB, MemoryStore, migrate_legacy_db

logger = logging.getLogger(__name__)


class MemoryMesh:
    """The SQLite of AI Memory.

    An embeddable, zero-dependency AI memory library that any application
    can integrate in three lines of code::

        from memorymesh import MemoryMesh

        mem = MemoryMesh()
        mem.remember("The user prefers dark mode.")
        results = mem.recall("What theme does the user like?")

    MemoryMesh uses a **hybrid dual-store** architecture:

    * A **project store** (``path``) holds project-specific memories.
    * A **global store** (``global_path``) holds user preferences and
      cross-project facts.

    When ``path`` is ``None`` (the default), no project store is created
    and only global memory is available.

    Args:
        path: Path to the project SQLite database file, or ``None`` for
            global-only mode.
        global_path: Path to the global SQLite database file.  Defaults
            to ``~/.memorymesh/global.db``.
        embedding: Embedding provider to use.  Accepts a string name
            (``"local"``, ``"ollama"``, ``"openai"``, ``"none"``) or an
            :class:`EmbeddingProvider` instance for full control.
        relevance_weights: Optional :class:`RelevanceWeights` to tune
            how memories are ranked during recall.
        encryption_key: Optional passphrase for encrypting memory data
            at rest.  When provided, the ``text`` and ``metadata`` fields
            are encrypted before being written to SQLite.  Uses
            PBKDF2-HMAC-SHA256 key derivation with a per-database salt.
            ``None`` (default) disables encryption.
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
        global_path: str | os.PathLike[str] | None = None,
        embedding: str | EmbeddingProvider = "local",
        relevance_weights: RelevanceWeights | None = None,
        encryption_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        # -- Legacy migration --------------------------------------------
        migrate_legacy_db()

        # -- Storage (dual-store) ----------------------------------------
        self._project_store: MemoryStore | None = MemoryStore(path=path) if path else None
        self._global_store = MemoryStore(path=global_path or _DEFAULT_GLOBAL_DB)

        # -- Optional encryption -----------------------------------------
        if encryption_key is not None:
            from .encryption import EncryptedMemoryStore

            if self._project_store is not None:
                self._project_store = EncryptedMemoryStore(  # type: ignore[assignment]
                    self._project_store, encryption_key
                )
            self._global_store = EncryptedMemoryStore(  # type: ignore[assignment]
                self._global_store, encryption_key
            )

        # -- Embedding provider ------------------------------------------
        if isinstance(embedding, EmbeddingProvider):
            self._embedder = embedding
        else:
            self._embedder = self._build_embedder(embedding, **kwargs)

        # -- Relevance engine --------------------------------------------
        self._engine = RelevanceEngine(weights=relevance_weights)

        # -- Auto-compaction settings ----------------------------------------
        self._compact_interval = 50  # compact every N writes
        self._writes_since_compact = 0

        logger.info(
            "MemoryMesh initialised  project_store=%r  global_store=%r  embedder=%r",
            self._project_store,
            self._global_store,
            self._embedder,
        )

    # ------------------------------------------------------------------
    # Path properties
    # ------------------------------------------------------------------

    @property
    def project_path(self) -> str | None:
        """Return the project database path, or ``None`` if not configured."""
        return self._project_store._path if self._project_store else None

    @property
    def global_path(self) -> str:
        """Return the global database path."""
        return self._global_store._path

    @property
    def compact_interval(self) -> int:
        """Number of ``remember()`` calls between automatic compaction passes.

        Set to ``0`` to disable auto-compaction.  Default is ``50``.
        """
        return self._compact_interval

    @compact_interval.setter
    def compact_interval(self, value: int) -> None:
        self._compact_interval = max(0, value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def remember(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        importance: float = 0.5,
        decay_rate: float = 0.01,
        scope: str | None = None,
        auto_importance: bool = False,
        session_id: str | None = None,
        category: str | None = None,
        auto_categorize: bool = False,
        pin: bool = False,
        redact: bool = False,
        on_conflict: str = "keep_both",
    ) -> str:
        """Store a new memory.

        Args:
            text: The textual content to remember.
            metadata: Optional key-value metadata to attach.
            importance: Importance score in ``[0, 1]``.  Higher values
                make the memory more prominent during recall.
            decay_rate: Rate at which importance decays over time.
                ``0`` means the memory never decays.
            scope: ``"project"``, ``"global"``, or ``None`` (default).
                When ``None``, the scope is inferred automatically --
                first from *category* routing, then from subject-based
                heuristics (user-focused text → global, project-focused
                → project).  Falls back to ``"project"`` if no signal
                is detected.  When explicitly set, the value is
                respected unless *category* overrides it.
            auto_importance: If ``True``, override *importance* with a
                heuristic score computed from the text content.
            session_id: Optional session/episode identifier for grouping
                memories by conversation or task.
            category: Optional memory category (e.g. ``"preference"``,
                ``"guardrail"``, ``"decision"``).  When set, the scope
                is automatically routed based on the category.
            auto_categorize: If ``True`` and *category* is ``None``,
                detect the category from the text using heuristics.
                Also enables *auto_importance* automatically.
            pin: If ``True``, pin this memory so it has maximum
                importance (1.0), never decays, and is always prominent
                in recall results.
            redact: If ``True``, automatically redact detected secrets
                (API keys, tokens, passwords) before storing.
            on_conflict: How to handle contradictions with existing
                memories.  ``"keep_both"`` (default) stores both and
                flags the contradiction.  ``"update"`` replaces the
                most similar existing memory.  ``"skip"`` discards the
                new memory if a contradiction is found.

        Returns:
            The unique ID of the newly created memory, or an empty
            string if *on_conflict* is ``"skip"`` and a contradiction
            was detected.

        Raises:
            RuntimeError: If *scope* is ``"project"`` but no project
                database is configured.
            ValueError: If *category* is not a recognised category name.
        """
        meta = dict(metadata) if metadata else {}
        caller_set_scope = scope is not None

        # -- Category handling -------------------------------------------------
        if auto_categorize and category is None:
            category = _auto_categorize(text, meta)
            auto_importance = True  # auto-categorize implies auto-importance

        if category is not None:
            validate_category(category)
            scope = CATEGORY_SCOPE_MAP[category]
            meta["category"] = category

        # -- Subject-based scope inference ------------------------------------
        # If the caller didn't explicitly set scope, refine via text analysis.
        if not caller_set_scope:
            project_name = None
            if self._project_store:
                # path is <root>/.memorymesh/memories.db → dirname twice → root
                project_name = os.path.basename(
                    os.path.dirname(os.path.dirname(self._project_store._path))
                )
            inferred = _infer_scope(
                text,
                category_scope=scope,
                project_name=project_name,
            )
            if inferred is not None:
                scope = inferred

        # Default to project scope if still None.
        if scope is None:
            scope = PROJECT_SCOPE

        validate_scope(scope)
        store = self._store_for_scope(scope)

        if auto_importance:
            importance = score_importance(text, meta)

        # -- Pin handling -------------------------------------------------
        if pin:
            importance = 1.0
            decay_rate = 0.0
            meta["pinned"] = True

        # -- Privacy guard ------------------------------------------------
        secrets_found = check_for_secrets(text)
        if secrets_found:
            logger.warning(
                "Potential secrets detected in memory text: %s",
                ", ".join(secrets_found),
            )
            meta["has_secrets_warning"] = True
            meta["detected_secret_types"] = secrets_found
            if redact:
                text = _redact_secrets(text)

        # Compute embedding (may be empty list for NoopEmbedding).
        emb = self._safe_embed(text)

        # -- Contradiction detection ----------------------------------------
        try:
            conflict_mode = ConflictMode(on_conflict)
        except ValueError:
            conflict_mode = ConflictMode.KEEP_BOTH

        contradictions = find_contradictions(
            text=text,
            embedding=emb if emb else None,
            store=store,
        )

        if contradictions:
            contradiction_ids = [m.id for m, _ in contradictions]
            logger.warning(
                "New memory may contradict existing memories: %s",
                contradiction_ids,
            )

            if conflict_mode == ConflictMode.SKIP:
                logger.info("Skipped storing memory (on_conflict=skip)")
                return ""

            if conflict_mode == ConflictMode.UPDATE:
                most_similar_mem = contradictions[0][0]
                store.delete(most_similar_mem.id)
                meta["replaced_memory_id"] = most_similar_mem.id
                logger.info(
                    "Will replace memory %s (on_conflict=update)",
                    most_similar_mem.id,
                )

            # For KEEP_BOTH and UPDATE, flag contradictions in metadata
            meta["contradicts"] = contradiction_ids

        memory = Memory(
            text=text,
            metadata=meta,
            embedding=emb if emb else None,
            importance=importance,
            decay_rate=decay_rate,
            session_id=session_id,
            scope=scope,
        )

        store.save(memory)
        logger.debug(
            "Remembered memory %s (%d chars, scope=%s, category=%s, session=%s)",
            memory.id,
            len(text),
            scope,
            category,
            session_id,
        )

        # Auto-compact if threshold reached.
        self._writes_since_compact += 1
        if self._compact_interval > 0 and self._writes_since_compact >= self._compact_interval:
            self._auto_compact(scope)

        return memory.id

    def recall(
        self,
        query: str,
        k: int = 5,
        min_relevance: float = 0.0,
        scope: str | None = None,
        session_id: str | None = None,
        category: str | None = None,
        min_importance: float | None = None,
        time_range: tuple[str, str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> builtins.list[Memory]:
        """Recall the most relevant memories for a query.

        Uses vector similarity (when embeddings are available) combined
        with recency, importance, and access frequency to rank results.
        Falls back to keyword search when the embedding provider is
        :class:`NoopEmbedding`.

        When *session_id* is provided, memories from the same session
        receive a temporary importance boost so that in-session context
        is preferred.

        Args:
            query: Natural-language query describing what you want to
                recall.
            k: Maximum number of memories to return.
            min_relevance: Discard results scoring below this threshold.
            scope: ``"project"``, ``"global"``, or ``None`` (default)
                to search both stores.
            session_id: Optional session identifier.  When set, memories
                belonging to the same session are boosted in ranking.
            category: Filter by memory category (e.g. ``"decision"``).
            min_importance: Only return memories with importance at or
                above this value.
            time_range: Tuple of ``(start_iso, end_iso)`` to filter by
                creation time.
            metadata_filter: Dict of key-value pairs to match in
                memory metadata.

        Returns:
            Up to *k* :class:`Memory` objects sorted by descending
            relevance.
        """
        query_embedding = self._safe_embed(query)

        has_filters = any([category, min_importance is not None, time_range, metadata_filter])
        candidates: list[Memory] = []

        if scope in (None, PROJECT_SCOPE) and self._project_store:
            if has_filters:
                project_candidates = self._project_store.search_filtered(
                    category=category,
                    min_importance=min_importance,
                    time_range=time_range,
                    metadata_filter=metadata_filter,
                )
            else:
                project_candidates = self._get_candidates(
                    query,
                    query_embedding,
                    self._project_store,
                )
            for m in project_candidates:
                m.scope = PROJECT_SCOPE
            candidates.extend(project_candidates)

        if scope in (None, GLOBAL_SCOPE):
            if has_filters:
                global_candidates = self._global_store.search_filtered(
                    category=category,
                    min_importance=min_importance,
                    time_range=time_range,
                    metadata_filter=metadata_filter,
                )
            else:
                global_candidates = self._get_candidates(
                    query,
                    query_embedding,
                    self._global_store,
                )
            for m in global_candidates:
                m.scope = GLOBAL_SCOPE
            candidates.extend(global_candidates)

        if not candidates:
            return []

        # Apply time-based decay before ranking.
        self._engine.apply_decay(candidates)

        # Boost same-session memories by temporarily increasing importance.
        session_boost = 0.15
        boosted_ids: set[str] = set()
        if session_id:
            for mem in candidates:
                if mem.session_id == session_id:
                    mem.importance = min(1.0, mem.importance + session_boost)
                    boosted_ids.add(mem.id)

        # Rank and return top-k.
        results = self._engine.rank(
            candidates,
            query_embedding=query_embedding if query_embedding else None,
            k=k,
            min_relevance=min_relevance,
        )

        # Restore boosted importance so the persisted value is unchanged.
        for mem in results:
            if mem.id in boosted_ids:
                mem.importance = max(0.0, mem.importance - session_boost)

        # Update access counts for returned memories.
        for mem in results:
            store = self._global_store if mem.scope == GLOBAL_SCOPE else self._project_store
            if store:
                store.update_access(mem.id)
            mem.access_count += 1

        return results

    def forget(self, memory_id: str) -> bool:
        """Forget (delete) a specific memory.

        Checks the project store first, then falls back to the global
        store.

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            ``True`` if the memory was found and deleted, ``False``
            otherwise.
        """
        if self._project_store and self._project_store.delete(memory_id):
            logger.debug("Forgot memory %s (project)", memory_id)
            return True
        if self._global_store.delete(memory_id):
            logger.debug("Forgot memory %s (global)", memory_id)
            return True
        return False

    def forget_all(self, scope: str = PROJECT_SCOPE) -> int:
        """Forget all memories in the given scope.

        Args:
            scope: ``"project"`` (default) or ``"global"``.

        Returns:
            The number of memories deleted.
        """
        validate_scope(scope)
        store = self._store_for_scope(scope, allow_none=True)
        if store is None:
            return 0
        count = store.clear()
        logger.info("Forgot all %d memories (scope=%s)", count, scope)
        return count

    def count(self, scope: str | None = None) -> int:
        """Return the number of stored memories.

        Args:
            scope: ``"project"``, ``"global"``, or ``None`` (default)
                for the total across both stores.

        Returns:
            An integer count.
        """
        if scope == PROJECT_SCOPE:
            return self._project_store.count() if self._project_store else 0
        if scope == GLOBAL_SCOPE:
            return self._global_store.count()
        # scope is None → total
        total = self._global_store.count()
        if self._project_store:
            total += self._project_store.count()
        return total

    def list(
        self,
        limit: int = 10,
        offset: int = 0,
        scope: str | None = None,
    ) -> builtins.list[Memory]:
        """List memories with pagination.

        Args:
            limit: Maximum number of memories to return.
            offset: Number of memories to skip.
            scope: ``"project"``, ``"global"``, or ``None`` (default)
                to merge both stores.

        Returns:
            A list of :class:`Memory` objects ordered by most recently
            updated first.
        """
        if scope == PROJECT_SCOPE:
            if not self._project_store:
                return []
            mems = self._project_store.list_all(limit=limit, offset=offset)
            for m in mems:
                m.scope = PROJECT_SCOPE
            return mems
        if scope == GLOBAL_SCOPE:
            mems = self._global_store.list_all(limit=limit, offset=offset)
            for m in mems:
                m.scope = GLOBAL_SCOPE
            return mems

        # scope is None → merge both stores, re-sort by updated_at.
        all_mems: list[Memory] = []
        if self._project_store:
            project_mems = self._project_store.list_all(
                limit=limit + offset,
            )
            for m in project_mems:
                m.scope = PROJECT_SCOPE
            all_mems.extend(project_mems)
        global_mems = self._global_store.list_all(limit=limit + offset)
        for m in global_mems:
            m.scope = GLOBAL_SCOPE
        all_mems.extend(global_mems)

        all_mems.sort(key=lambda m: m.updated_at, reverse=True)
        return all_mems[offset : offset + limit]

    def search(self, text: str, k: int = 5) -> builtins.list[Memory]:
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

        Checks the project store first, then falls back to the global
        store.

        Args:
            memory_id: The unique identifier.

        Returns:
            The :class:`Memory` if found, otherwise ``None``.
        """
        if self._project_store:
            mem = self._project_store.get(memory_id)
            if mem is not None:
                mem.scope = PROJECT_SCOPE
                return mem
        mem = self._global_store.get(memory_id)
        if mem is not None:
            mem.scope = GLOBAL_SCOPE
        return mem

    def update(
        self,
        memory_id: str,
        text: str | None = None,
        importance: float | None = None,
        decay_rate: float | None = None,
        metadata: dict[str, Any] | None = None,
        scope: str | None = None,
    ) -> Memory | None:
        """Update an existing memory in place.

        Any provided parameter replaces the corresponding field.  If
        *text* is changed, the embedding is recomputed automatically.

        When *scope* is provided and differs from the memory's current
        scope, the memory is **migrated**: deleted from the old store
        and re-created in the new store with the updated fields.

        Args:
            memory_id: The unique identifier of the memory to update.
            text: New text content, or ``None`` to keep existing.
            importance: New importance score, or ``None`` to keep existing.
            decay_rate: New decay rate, or ``None`` to keep existing.
            metadata: New metadata dict, or ``None`` to keep existing.
            scope: Target scope (``"project"`` or ``"global"``).
                ``None`` keeps the memory in its current store.

        Returns:
            The updated :class:`Memory` if found, or ``None`` if
            *memory_id* does not exist.

        Raises:
            RuntimeError: If the target scope is ``"project"`` but no
                project database is configured.
        """
        mem = self.get(memory_id)
        if mem is None:
            return None

        current_scope = mem.scope

        # Determine effective new values.
        new_text = text if text is not None else mem.text
        new_importance = importance if importance is not None else mem.importance
        new_decay_rate = decay_rate if decay_rate is not None else mem.decay_rate
        new_metadata = metadata if metadata is not None else mem.metadata

        if scope is not None and scope != current_scope:
            # -- Scope migration: delete from old, create in new store ---
            validate_scope(scope)
            old_store = self._store_for_scope(current_scope)
            old_store.delete(memory_id)

            # Recompute embedding for the (possibly new) text.
            emb = self._safe_embed(new_text)

            new_mem = Memory(
                id=memory_id,
                text=new_text,
                metadata=new_metadata,
                embedding=emb if emb else None,
                created_at=mem.created_at,
                importance=new_importance,
                decay_rate=new_decay_rate,
                access_count=mem.access_count,
                session_id=mem.session_id,
                scope=scope,
            )
            target_store = self._store_for_scope(scope)
            target_store.save(new_mem)
            logger.debug(
                "Migrated memory %s from %s to %s",
                memory_id,
                current_scope,
                scope,
            )
            return self.get(memory_id)

        # -- In-place update ------------------------------------------
        from .store import _UNSET

        new_embedding: Any = _UNSET
        if text is not None and text != mem.text:
            emb = self._safe_embed(text)
            new_embedding = emb if emb else None

        store = self._store_for_scope(current_scope)
        store.update_fields(
            memory_id=memory_id,
            text=text,
            importance=importance,
            decay_rate=decay_rate,
            metadata=metadata,
            embedding=new_embedding,
        )
        logger.debug("Updated memory %s in %s store", memory_id, current_scope)
        return self.get(memory_id)

    def get_time_range(
        self,
        scope: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Return the oldest and newest ``created_at`` timestamps.

        Args:
            scope: ``"project"``, ``"global"``, or ``None`` (default)
                to consider both stores.

        Returns:
            A ``(oldest_iso, newest_iso)`` tuple, or ``(None, None)``
            if the relevant store(s) are empty.
        """
        if scope == PROJECT_SCOPE:
            if not self._project_store:
                return (None, None)
            return self._project_store.get_time_range()
        if scope == GLOBAL_SCOPE:
            return self._global_store.get_time_range()

        # scope is None → merge ranges from both stores.
        ranges: list[tuple[str | None, str | None]] = []
        if self._project_store:
            ranges.append(self._project_store.get_time_range())
        ranges.append(self._global_store.get_time_range())

        oldest_vals = [r[0] for r in ranges if r[0] is not None]
        newest_vals = [r[1] for r in ranges if r[1] is not None]

        oldest = min(oldest_vals) if oldest_vals else None
        newest = max(newest_vals) if newest_vals else None
        return (oldest, newest)

    def get_session(
        self,
        session_id: str,
        scope: str | None = None,
    ) -> builtins.list[Memory]:
        """Retrieve all memories belonging to a specific session.

        Args:
            session_id: The session identifier to filter by.
            scope: ``"project"``, ``"global"``, or ``None`` (default)
                to search both stores.

        Returns:
            A list of :class:`Memory` objects ordered by creation time.
        """
        results: list[Memory] = []

        if scope in (None, PROJECT_SCOPE) and self._project_store:
            mems = self._project_store.get_by_session(session_id)
            for m in mems:
                m.scope = PROJECT_SCOPE
            results.extend(mems)

        if scope in (None, GLOBAL_SCOPE):
            mems = self._global_store.get_by_session(session_id)
            for m in mems:
                m.scope = GLOBAL_SCOPE
            results.extend(mems)

        results.sort(key=lambda m: m.created_at)
        return results

    def list_sessions(
        self,
        scope: str | None = None,
        limit: int = 50,
    ) -> builtins.list[dict[str, Any]]:
        """List distinct sessions with summary statistics.

        Args:
            scope: ``"project"``, ``"global"``, or ``None`` (default)
                to merge sessions from both stores.
            limit: Maximum number of sessions to return.

        Returns:
            A list of dicts with keys ``session_id``, ``count``,
            ``first_at``, ``last_at``, and ``scope``, ordered by most
            recent session first.
        """
        results: list[dict[str, Any]] = []

        if scope in (None, PROJECT_SCOPE) and self._project_store:
            sessions = self._project_store.list_sessions(limit=limit)
            for s in sessions:
                s["scope"] = PROJECT_SCOPE
            results.extend(sessions)

        if scope in (None, GLOBAL_SCOPE):
            sessions = self._global_store.list_sessions(limit=limit)
            for s in sessions:
                s["scope"] = GLOBAL_SCOPE
            results.extend(sessions)

        # Sort by most recent first and trim to limit.
        results.sort(key=lambda s: s["last_at"], reverse=True)
        return results[:limit]

    def compact(
        self,
        scope: str = PROJECT_SCOPE,
        similarity_threshold: float = 0.85,
        dry_run: bool = False,
    ) -> CompactionResult:
        """Compact memories by merging duplicates and near-duplicates.

        Scans all memories in the given scope, finds pairs that exceed
        the similarity threshold, and merges them.  The primary memory
        (higher importance or older) is kept; the secondary is deleted.

        Args:
            scope: ``"project"`` or ``"global"``.  Only one scope is
                compacted per call.
            similarity_threshold: Minimum text similarity to consider
                two memories as duplicates.  Default is ``0.85``.
            dry_run: If ``True``, compute the compaction plan but do
                not actually merge or delete anything.

        Returns:
            A :class:`CompactionResult` describing what was (or would
            be) merged.

        Raises:
            RuntimeError: If *scope* is ``"project"`` but no project
                database is configured.
        """
        from .compaction import compact as _compact

        return _compact(
            self,
            scope=scope,
            similarity_threshold=similarity_threshold,
            dry_run=dry_run,
        )

    # ------------------------------------------------------------------
    # Session start (structured context retrieval)
    # ------------------------------------------------------------------

    def session_start(
        self,
        project_context: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve structured context for the start of a new session.

        Gathers user profile, guardrails, common mistakes, recurring
        questions, and project context into a structured dict that an AI
        can consume as system context.

        Args:
            project_context: Optional brief description of what the user
                is working on, used to find relevant project memories.

        Returns:
            A dict with keys:

            - ``user_profile`` -- personality + preferences (list of str)
            - ``guardrails`` -- rules to follow (list of str)
            - ``common_mistakes`` -- past mistakes to avoid (list of str)
            - ``common_questions`` -- recurring user questions (list of str)
            - ``project_context`` -- relevant project memories (list of str)
            - ``last_session`` -- most recent session summary (list of str)
        """
        max_per_category = 5

        # -- Helper: collect memories by category from a store -------------
        def _collect(
            store: MemoryStore | None,
            categories: frozenset[str],
            scope_label: str,
        ) -> dict[str, list[Memory]]:
            if store is None:
                return {cat: [] for cat in categories}
            all_mems = store.list_all(limit=500)
            by_cat: dict[str, list[Memory]] = {cat: [] for cat in categories}
            for mem in all_mems:
                cat = mem.metadata.get("category")
                if cat in categories:
                    by_cat[cat].append(mem)
            # Sort each bucket by importance (desc) and trim.
            for cat in by_cat:
                by_cat[cat].sort(key=lambda m: m.importance, reverse=True)
                by_cat[cat] = by_cat[cat][:max_per_category]
            return by_cat

        global_by_cat = _collect(self._global_store, GLOBAL_CATEGORIES, GLOBAL_SCOPE)
        project_by_cat = _collect(self._project_store, PROJECT_CATEGORIES, PROJECT_SCOPE)

        # -- Build result dict ---------------------------------------------
        result: dict[str, list[str]] = {
            "user_profile": [
                m.text
                for m in (
                    global_by_cat.get("personality", []) + global_by_cat.get("preference", [])
                )
            ][:max_per_category],
            "guardrails": [m.text for m in global_by_cat.get("guardrail", [])],
            "common_mistakes": [m.text for m in global_by_cat.get("mistake", [])],
            "common_questions": [m.text for m in global_by_cat.get("question", [])],
            "project_context": [m.text for m in project_by_cat.get("context", [])],
            "last_session": [m.text for m in project_by_cat.get("session_summary", [])[:1]],
        }

        # Add project decisions and patterns to project_context.
        result["project_context"].extend(m.text for m in project_by_cat.get("decision", []))
        result["project_context"].extend(m.text for m in project_by_cat.get("pattern", []))
        result["project_context"] = result["project_context"][:max_per_category]

        # If project_context query provided, supplement with recall results.
        if project_context and self._project_store:
            recalled = self.recall(
                query=project_context,
                k=max_per_category,
                scope=PROJECT_SCOPE,
            )
            existing_texts = set(result["project_context"])
            for mem in recalled:
                if mem.text not in existing_texts:
                    result["project_context"].append(mem.text)
                    existing_texts.add(mem.text)
            result["project_context"] = result["project_context"][: max_per_category * 2]

        logger.info(
            "session_start: profile=%d guardrails=%d mistakes=%d "
            "questions=%d project=%d session=%d",
            len(result["user_profile"]),
            len(result["guardrails"]),
            len(result["common_mistakes"]),
            len(result["common_questions"]),
            len(result["project_context"]),
            len(result["last_session"]),
        )

        return result

    # ------------------------------------------------------------------
    # Smart Sync
    # ------------------------------------------------------------------

    def smart_sync(
        self,
        top_n: int = 20,
        weights: RelevanceWeights | None = None,
        scope: str | None = None,
    ) -> builtins.list[Memory]:
        """Return the top-N most relevant memories ranked for sync.

        This method is the foundation for ``.md`` export -- callers (sync
        module, format adapters) use it to get relevance-ranked memories
        instead of dumping everything.

        The default weights emphasise importance and recency over semantic
        similarity (which is not meaningful without a query context).

        Args:
            top_n: Maximum number of memories to return.
            weights: Custom :class:`RelevanceWeights` for sync ranking.
                Defaults to ``semantic=0.0, recency=0.3, importance=0.5,
                frequency=0.2``.
            scope: ``"project"``, ``"global"``, or ``None`` (default)
                to rank memories from both stores.

        Returns:
            Up to *top_n* :class:`Memory` objects sorted by descending
            relevance.
        """
        if weights is None:
            weights = RelevanceWeights(
                semantic=0.0,
                recency=0.3,
                importance=0.5,
                frequency=0.2,
            )

        sync_engine = RelevanceEngine(weights=weights)

        candidates: list[Memory] = []

        if scope in (None, PROJECT_SCOPE) and self._project_store:
            project_mems = self._project_store.list_all(limit=10_000)
            for m in project_mems:
                m.scope = PROJECT_SCOPE
            candidates.extend(project_mems)

        if scope in (None, GLOBAL_SCOPE):
            global_mems = self._global_store.list_all(limit=10_000)
            for m in global_mems:
                m.scope = GLOBAL_SCOPE
            candidates.extend(global_mems)

        if not candidates:
            return []

        # Apply decay before ranking.
        sync_engine.apply_decay(candidates)

        return sync_engine.rank(
            candidates,
            query_embedding=None,
            k=top_n,
        )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying database connections."""
        if self._project_store:
            self._project_store.close()
        self._global_store.close()

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

    def _auto_compact(self, scope: str) -> None:
        """Run a lightweight compaction pass after N writes.

        Silently catches and logs any errors so that a compaction
        failure never breaks a ``remember()`` call.

        Args:
            scope: The scope to compact.
        """
        try:
            result = self.compact(
                scope=scope,
                similarity_threshold=0.85,
                dry_run=False,
            )
            self._writes_since_compact = 0
            if result.merged_count > 0:
                logger.info(
                    "Auto-compacted %d duplicate(s) in %s store.",
                    result.merged_count,
                    scope,
                )
        except Exception:
            logger.warning(
                "Auto-compaction failed for scope=%s, will retry later.",
                scope,
                exc_info=True,
            )

    def _store_for_scope(
        self,
        scope: str,
        allow_none: bool = False,
    ) -> MemoryStore:
        """Return the :class:`MemoryStore` for the given *scope*.

        Args:
            scope: ``"project"`` or ``"global"``.
            allow_none: If ``True``, return ``None`` instead of raising
                when the project store is not configured.

        Raises:
            RuntimeError: If *scope* is ``"project"`` but no project
                database is configured and *allow_none* is ``False``.
        """
        if scope == GLOBAL_SCOPE:
            return self._global_store
        if self._project_store is not None:
            return self._project_store
        if allow_none:
            return None  # type: ignore[return-value]
        raise RuntimeError(
            "No project database configured. "
            "The project root could not be detected automatically.\n"
            "Fix options:\n"
            "  1. Use the 'configure_project' tool with your project path\n"
            "  2. Set MEMORYMESH_PROJECT_ROOT=/path/to/project in MCP server env config\n"
            "  3. Set MEMORYMESH_PATH=/path/to/project/.memorymesh/memories.db in env config\n"
            "  4. Launch your AI tool from within a project directory\n"
            "Fallback: Use scope='global' for non-project memories."
        )

    def _get_candidates(
        self,
        query: str,
        query_embedding: builtins.list[float],
        store: MemoryStore,
    ) -> builtins.list[Memory]:
        """Gather candidate memories from a single store.

        Combines vector search (when embeddings are available) with
        keyword fallback, mirroring the original ``recall`` logic.

        Args:
            query: The natural-language query.
            query_embedding: Pre-computed query embedding (may be empty).
            store: The :class:`MemoryStore` to search.

        Returns:
            A deduplicated list of candidate :class:`Memory` objects.
        """
        if not query_embedding:
            return store.search_by_text(query, limit=20)

        candidates = store.get_all_with_embeddings()
        keyword_hits = store.search_by_text(query, limit=10)
        seen_ids = {m.id for m in candidates}
        for hit in keyword_hits:
            if hit.id not in seen_ids:
                candidates.append(hit)
        return candidates

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

    def _safe_embed(self, text: str) -> builtins.list[float]:
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
                "Embedding failed for text (%.40s...), falling back to keyword search.",
                text,
                exc_info=True,
            )
            return []

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"MemoryMesh(project_store={self._project_store!r}, "
            f"global_store={self._global_store!r}, "
            f"embedder={self._embedder!r})"
        )
