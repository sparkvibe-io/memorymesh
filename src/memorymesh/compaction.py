"""Memory compaction and deduplication for MemoryMesh.

Detects similar or redundant memories and merges them to keep the store lean.
All similarity computation is pure Python with zero external dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from .memory import PROJECT_SCOPE, Memory, validate_scope
from .store import cosine_similarity

if TYPE_CHECKING:
    from .core import MemoryMesh

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CompactionResult:
    """Result of a compaction operation.

    Attributes:
        merged_count: Number of merge operations performed (each merge
            combines two memories into one).
        deleted_ids: IDs of memories that were deleted (the "secondary"
            memory in each merge).
        kept_ids: IDs of memories that were kept (the "primary" memory
            in each merge, now updated with merged content).
        details: List of dicts describing each merge operation, with
            ``primary_id``, ``secondary_id``, ``similarity``, and
            ``merged_text_preview`` keys.
    """

    merged_count: int = 0
    deleted_ids: list[str] = field(default_factory=list)
    kept_ids: list[str] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Text similarity (pure Python)
# ---------------------------------------------------------------------------


def _word_set(text: str) -> set[str]:
    """Normalise text and return the set of unique words.

    Args:
        text: Input text.

    Returns:
        A set of lowercased words.
    """
    return set(text.lower().split())


def jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two texts on word sets.

    Args:
        a: First text.
        b: Second text.

    Returns:
        Jaccard index in ``[0, 1]``.  Returns ``0.0`` if both texts are
        empty.
    """
    set_a = _word_set(a)
    set_b = _word_set(b)
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def text_similarity(a: str, b: str) -> float:
    """Compute text similarity using Jaccard + containment check.

    If one text is a substring of the other, similarity is ``1.0``.
    Otherwise, Jaccard word-set similarity is returned.

    Args:
        a: First text.
        b: Second text.

    Returns:
        Similarity score in ``[0, 1]``.
    """
    # Containment check -- if one is a substring of the other, they are
    # effectively duplicates.
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    if a_lower in b_lower or b_lower in a_lower:
        return 1.0
    return jaccard_similarity(a, b)


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def find_duplicates(
    memories: list[Memory],
    threshold: float = 0.85,
) -> list[tuple[Memory, Memory]]:
    """Find pairs of memories with high text similarity.

    Uses pure-Python Jaccard word-set similarity and containment checks.
    The first element of each pair is the "primary" (higher importance or
    older), and the second is the "secondary" (candidate for deletion).

    Args:
        memories: List of memories to scan.
        threshold: Minimum similarity to consider a pair as duplicates.
            Must be in ``(0, 1]``.

    Returns:
        A list of ``(primary, secondary)`` tuples.
    """
    pairs: list[tuple[Memory, Memory]] = []
    seen_secondary: set[str] = set()

    for i in range(len(memories)):
        if memories[i].id in seen_secondary:
            continue
        for j in range(i + 1, len(memories)):
            if memories[j].id in seen_secondary:
                continue
            sim = text_similarity(memories[i].text, memories[j].text)
            if sim >= threshold:
                primary, secondary = _pick_primary(memories[i], memories[j])
                pairs.append((primary, secondary))
                seen_secondary.add(secondary.id)
    return pairs


def find_near_duplicates(
    memories: list[Memory],
    embeddings_fn: Callable[[str], list[float]] | None = None,
    threshold: float = 0.9,
) -> list[tuple[Memory, Memory]]:
    """Find pairs of memories with high embedding cosine similarity.

    Only considers memories that already have embeddings stored. If
    ``embeddings_fn`` is provided it is used to compute missing
    embeddings on-the-fly; otherwise memories without embeddings are
    skipped.

    Args:
        memories: List of memories to scan.
        embeddings_fn: Optional callable that takes text and returns an
            embedding vector.  Used to fill in missing embeddings.
        threshold: Minimum cosine similarity to consider a pair as near
            duplicates.  Must be in ``(0, 1]``.

    Returns:
        A list of ``(primary, secondary)`` tuples.
    """
    # Build list of (memory, embedding) for memories that have embeddings.
    embedded: list[tuple[Memory, list[float]]] = []
    for mem in memories:
        emb = mem.embedding
        if emb:
            embedded.append((mem, emb))
        elif embeddings_fn is not None:
            try:
                emb = embeddings_fn(mem.text)
                if emb:
                    embedded.append((mem, emb))
            except Exception:
                logger.debug("Failed to embed memory %s, skipping.", mem.id)

    pairs: list[tuple[Memory, Memory]] = []
    seen_secondary: set[str] = set()

    for i in range(len(embedded)):
        mem_i, emb_i = embedded[i]
        if mem_i.id in seen_secondary:
            continue
        for j in range(i + 1, len(embedded)):
            mem_j, emb_j = embedded[j]
            if mem_j.id in seen_secondary:
                continue
            try:
                sim = cosine_similarity(emb_i, emb_j)
            except ValueError:
                continue
            if sim >= threshold:
                primary, secondary = _pick_primary(mem_i, mem_j)
                pairs.append((primary, secondary))
                seen_secondary.add(secondary.id)
    return pairs


def _pick_primary(a: Memory, b: Memory) -> tuple[Memory, Memory]:
    """Choose which memory to keep as primary.

    Prefers the memory with higher importance; ties broken by older
    ``created_at`` (keep the original).

    Args:
        a: First memory.
        b: Second memory.

    Returns:
        A ``(primary, secondary)`` tuple.
    """
    if a.importance > b.importance:
        return (a, b)
    if b.importance > a.importance:
        return (b, a)
    # Equal importance -- keep the older one.
    if a.created_at <= b.created_at:
        return (a, b)
    return (b, a)


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------


def merge_memories(primary: Memory, secondary: Memory) -> Memory:
    """Merge two memories, keeping the best attributes from each.

    The primary memory's text is kept.  If the secondary's text is
    substantially different (Jaccard similarity below 0.95), it is
    appended on a new line with a separator.

    Metadata from both memories is combined (primary takes precedence
    on key conflicts).  The older ``created_at``, newer ``updated_at``,
    higher importance, and summed access counts are used.

    Args:
        primary: The memory to keep (its ID is preserved).
        secondary: The memory to merge into the primary.

    Returns:
        A new :class:`Memory` with the merged result. The ID matches
        the primary's ID.
    """
    # Decide whether to append secondary text.
    sim = jaccard_similarity(primary.text, secondary.text)
    if sim < 0.95:
        merged_text = primary.text.rstrip() + "\n---\n" + secondary.text.lstrip()
    else:
        merged_text = primary.text

    # Merge metadata: secondary first, then primary overwrites.
    merged_metadata: dict[str, Any] = {}
    merged_metadata.update(secondary.metadata)
    merged_metadata.update(primary.metadata)

    return Memory(
        id=primary.id,
        text=merged_text,
        metadata=merged_metadata,
        embedding=primary.embedding,
        created_at=min(primary.created_at, secondary.created_at),
        updated_at=max(primary.updated_at, secondary.updated_at),
        access_count=primary.access_count + secondary.access_count,
        importance=max(primary.importance, secondary.importance),
        decay_rate=min(primary.decay_rate, secondary.decay_rate),
        scope=primary.scope,
    )


# ---------------------------------------------------------------------------
# Main compaction entry point
# ---------------------------------------------------------------------------


def compact(
    mesh: MemoryMesh,
    scope: str = PROJECT_SCOPE,
    similarity_threshold: float = 0.85,
    dry_run: bool = False,
) -> CompactionResult:
    """Compact memories by merging duplicates and near-duplicates.

    Scans all memories in the given scope, finds pairs that exceed the
    similarity threshold (using text similarity), and merges them.

    When embeddings are available, also runs embedding-based near-duplicate
    detection at a higher threshold (0.9) to catch semantically similar
    memories that differ in wording.

    Args:
        mesh: The :class:`MemoryMesh` instance to compact.
        scope: ``"project"`` or ``"global"``.  Only one scope is compacted
            per call to avoid accidentally merging across stores.
        similarity_threshold: Minimum text similarity (Jaccard + containment)
            to consider two memories as duplicates.  Default is ``0.85``.
        dry_run: If ``True``, compute the compaction plan but do not
            actually merge or delete anything.

    Returns:
        A :class:`CompactionResult` describing what was (or would be)
        merged.
    """
    validate_scope(scope)

    # Load all memories for the given scope.
    memories = mesh.list(limit=100_000, scope=scope)
    if len(memories) < 2:
        return CompactionResult()

    # Phase 1: text-based duplicate detection.
    pairs = find_duplicates(memories, threshold=similarity_threshold)

    # Phase 2: embedding-based near-duplicate detection (additive).
    # Only memories with embeddings participate; we skip the embed_fn
    # to avoid expensive recomputation during compaction.
    already_paired = set()
    for primary, secondary in pairs:
        already_paired.add(primary.id)
        already_paired.add(secondary.id)

    unpaired = [m for m in memories if m.id not in already_paired]
    if len(unpaired) >= 2:
        embedding_pairs = find_near_duplicates(unpaired, embeddings_fn=None, threshold=0.9)
        pairs.extend(embedding_pairs)

    if not pairs:
        return CompactionResult()

    result = CompactionResult()

    for primary, secondary in pairs:
        merged = merge_memories(primary, secondary)
        detail = {
            "primary_id": primary.id,
            "secondary_id": secondary.id,
            "similarity": round(text_similarity(primary.text, secondary.text), 3),
            "merged_text_preview": merged.text[:100],
        }
        result.details.append(detail)

        if not dry_run:
            # Save the merged memory (updates the primary in the store).
            store = mesh._store_for_scope(scope)
            store.save(merged)
            # Delete the secondary.
            mesh.forget(secondary.id)

        result.merged_count += 1
        result.deleted_ids.append(secondary.id)
        result.kept_ids.append(primary.id)

    logger.info(
        "Compaction %s: %d merges, %d deleted (scope=%s, threshold=%.2f)",
        "planned (dry_run)" if dry_run else "complete",
        result.merged_count,
        len(result.deleted_ids),
        scope,
        similarity_threshold,
    )

    return result
