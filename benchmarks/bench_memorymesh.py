"""MemoryMesh performance benchmarks.

Measures throughput and latency of core MemoryMesh operations across different
store sizes.  Uses only the Python standard library for timing (time.perf_counter).
All benchmark databases are created in temporary directories and cleaned up after.

Run::

    python -m benchmarks.bench_memorymesh

Or via the Makefile::

    make bench
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the source tree is importable when running as `python -m benchmarks.bench_memorymesh`
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(_PROJECT_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))

from memorymesh import MemoryMesh  # noqa: E402
from memorymesh.auto_importance import score_importance  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REMEMBER_SIZES = [10, 100, 1000, 5000]
RECALL_K_VALUES = [5, 10, 20]
RECALL_STORE_SIZES = [10, 100, 1000, 5000]
CONCURRENT_THREADS = 4
CONCURRENT_OPS_PER_THREAD = 50

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mesh(tmpdir: str) -> MemoryMesh:
    """Create a MemoryMesh instance with keyword-only embedding in a temp dir."""
    project_db = os.path.join(tmpdir, "project", "memories.db")
    global_db = os.path.join(tmpdir, "global", "global.db")
    return MemoryMesh(path=project_db, global_path=global_db, embedding="none")


def _sample_text(i: int) -> str:
    """Generate a deterministic sample memory text."""
    topics = [
        "The authentication module uses JWT tokens with RS256 signing algorithm.",
        "Database migrations should always be backwards-compatible for zero-downtime deploys.",
        "The user prefers dark mode with Monokai color scheme in all editors.",
        "Critical bug fix: race condition in connection pool when max_connections exceeded.",
        "Architecture decision: use SQLite for local storage instead of Redis.",
        "Python 3.9 is the minimum supported version for this project.",
        "Performance optimization: batch embedding calls to reduce Ollama round-trips.",
        "Security audit finding: input validation missing on metadata JSON field.",
        "Convention: all public API methods must have Google-style docstrings.",
        "The CI pipeline runs tests on ubuntu, macos, and windows with Python 3.9-3.13.",
    ]
    base = topics[i % len(topics)]
    return f"[Memory {i}] {base} (variant {i // len(topics)})"


def _format_time(seconds: float) -> str:
    """Format a duration as a human-readable string."""
    ms = seconds * 1000
    if ms < 1:
        return f"{ms * 1000:.1f}us"
    if ms < 1000:
        return f"{ms:.2f}ms"
    return f"{seconds:.2f}s"


def _format_per_op(total_seconds: float, count: int) -> str:
    """Format a per-operation time."""
    if count == 0:
        return "N/A"
    return _format_time(total_seconds / count)


def _db_size_bytes(tmpdir: str) -> int:
    """Return total size of all .db files in a directory tree."""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(tmpdir):
        for f in filenames:
            if f.endswith((".db", ".db-wal", ".db-shm")):
                total += os.path.getsize(os.path.join(dirpath, f))
    return total


def _format_size(nbytes: int) -> str:
    """Format bytes as a human-readable string."""
    if nbytes < 1024:
        return f"{nbytes}B"
    if nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f}KB"
    return f"{nbytes / (1024 * 1024):.2f}MB"


# ---------------------------------------------------------------------------
# Individual benchmarks
# ---------------------------------------------------------------------------


def bench_remember(results: dict[str, Any]) -> None:
    """Benchmark remember() throughput at various store sizes."""
    print("\nremember() throughput")
    print("-" * 40)

    bench_data: list[dict[str, Any]] = []
    for n in REMEMBER_SIZES:
        tmpdir = tempfile.mkdtemp(prefix="memorymesh_bench_")
        try:
            mesh = _make_mesh(tmpdir)
            start = time.perf_counter()
            for i in range(n):
                mesh.remember(_sample_text(i))
            elapsed = time.perf_counter() - start
            mesh.close()

            per_op = elapsed / n
            print(f"  {n:>5} memories:  {_format_time(elapsed):>10} total  ({_format_per_op(elapsed, n)}/op)")
            bench_data.append({
                "n": n,
                "total_seconds": round(elapsed, 6),
                "per_op_seconds": round(per_op, 8),
            })
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    results["remember_throughput"] = bench_data


def bench_recall(results: dict[str, Any]) -> None:
    """Benchmark recall() latency at various store sizes and k values."""
    print("\nrecall() latency (keyword-only)")
    print("-" * 40)

    bench_data: list[dict[str, Any]] = []
    for store_size in RECALL_STORE_SIZES:
        tmpdir = tempfile.mkdtemp(prefix="memorymesh_bench_")
        try:
            mesh = _make_mesh(tmpdir)
            # Populate store
            for i in range(store_size):
                mesh.remember(_sample_text(i))

            print(f"  store size = {store_size}")
            k_results: list[dict[str, Any]] = []
            for k in RECALL_K_VALUES:
                # Run multiple queries and average
                queries = [
                    "authentication JWT token",
                    "database migration",
                    "dark mode preference",
                    "security vulnerability",
                    "Python version",
                ]
                total_time = 0.0
                for q in queries:
                    start = time.perf_counter()
                    mesh.recall(q, k=k)
                    total_time += time.perf_counter() - start

                avg_time = total_time / len(queries)
                print(f"    top-{k:<3}  {_format_time(avg_time):>10} avg")
                k_results.append({
                    "k": k,
                    "avg_seconds": round(avg_time, 6),
                    "queries": len(queries),
                })
            mesh.close()
            bench_data.append({
                "store_size": store_size,
                "results": k_results,
            })
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    results["recall_latency"] = bench_data


def bench_forget(results: dict[str, Any]) -> None:
    """Benchmark forget() latency."""
    print("\nforget() latency")
    print("-" * 40)

    bench_data: list[dict[str, Any]] = []
    for store_size in [100, 1000, 5000]:
        tmpdir = tempfile.mkdtemp(prefix="memorymesh_bench_")
        try:
            mesh = _make_mesh(tmpdir)
            ids: list[str] = []
            for i in range(store_size):
                ids.append(mesh.remember(_sample_text(i)))

            # Delete 10% of memories
            delete_count = max(1, store_size // 10)
            start = time.perf_counter()
            for mid in ids[:delete_count]:
                mesh.forget(mid)
            elapsed = time.perf_counter() - start
            mesh.close()

            per_op = elapsed / delete_count
            print(f"  store={store_size:>5}, delete {delete_count:>4}:  {_format_time(elapsed):>10} total  ({_format_per_op(elapsed, delete_count)}/op)")
            bench_data.append({
                "store_size": store_size,
                "delete_count": delete_count,
                "total_seconds": round(elapsed, 6),
                "per_op_seconds": round(per_op, 8),
            })
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    results["forget_latency"] = bench_data


def bench_list_pagination(results: dict[str, Any]) -> None:
    """Benchmark list() with pagination."""
    print("\nlist() pagination (store=1000)")
    print("-" * 40)

    tmpdir = tempfile.mkdtemp(prefix="memorymesh_bench_")
    try:
        mesh = _make_mesh(tmpdir)
        for i in range(1000):
            mesh.remember(_sample_text(i))

        bench_data: list[dict[str, Any]] = []
        for page_size in [10, 50, 100]:
            pages = 1000 // page_size
            start = time.perf_counter()
            for page in range(pages):
                mesh.list(limit=page_size, offset=page * page_size, scope="project")
            elapsed = time.perf_counter() - start

            per_page = elapsed / pages
            print(f"  page_size={page_size:>3}, {pages:>3} pages:  {_format_time(elapsed):>10} total  ({_format_per_op(elapsed, pages)}/page)")
            bench_data.append({
                "page_size": page_size,
                "pages": pages,
                "total_seconds": round(elapsed, 6),
                "per_page_seconds": round(per_page, 8),
            })
        mesh.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    results["list_pagination"] = bench_data


def bench_concurrent(results: dict[str, Any]) -> None:
    """Benchmark concurrent remember/recall from multiple threads."""
    print(f"\nconcurrent access ({CONCURRENT_THREADS} threads, {CONCURRENT_OPS_PER_THREAD} ops/thread)")
    print("-" * 40)

    tmpdir = tempfile.mkdtemp(prefix="memorymesh_bench_")
    try:
        mesh = _make_mesh(tmpdir)
        # Pre-populate with some data
        for i in range(100):
            mesh.remember(_sample_text(i))

        errors: list[str] = []
        timings: dict[str, list[float]] = {"remember": [], "recall": []}
        lock = threading.Lock()

        def worker(thread_id: int) -> None:
            try:
                for i in range(CONCURRENT_OPS_PER_THREAD):
                    # Alternate between remember and recall
                    if i % 2 == 0:
                        start = time.perf_counter()
                        mesh.remember(f"Thread {thread_id} memory {i}: concurrent test data")
                        elapsed = time.perf_counter() - start
                        with lock:
                            timings["remember"].append(elapsed)
                    else:
                        start = time.perf_counter()
                        mesh.recall("concurrent test", k=5)
                        elapsed = time.perf_counter() - start
                        with lock:
                            timings["recall"].append(elapsed)
            except Exception as e:
                with lock:
                    errors.append(f"Thread {thread_id}: {e}")

        threads = []
        wall_start = time.perf_counter()
        for t in range(CONCURRENT_THREADS):
            th = threading.Thread(target=worker, args=(t,))
            threads.append(th)
            th.start()

        for th in threads:
            th.join()
        wall_elapsed = time.perf_counter() - wall_start

        mesh.close()

        total_ops = CONCURRENT_THREADS * CONCURRENT_OPS_PER_THREAD

        def _avg(lst: list[float]) -> float:
            return sum(lst) / len(lst) if lst else 0.0

        remember_avg = _avg(timings["remember"])
        recall_avg = _avg(timings["recall"])

        print(f"  wall time:       {_format_time(wall_elapsed)}")
        print(f"  total ops:       {total_ops}")
        print(f"  throughput:      {total_ops / wall_elapsed:.0f} ops/s")
        print(f"  avg remember:    {_format_time(remember_avg)}")
        print(f"  avg recall:      {_format_time(recall_avg)}")
        print(f"  errors:          {len(errors)}")

        results["concurrent"] = {
            "threads": CONCURRENT_THREADS,
            "ops_per_thread": CONCURRENT_OPS_PER_THREAD,
            "wall_seconds": round(wall_elapsed, 6),
            "total_ops": total_ops,
            "throughput_ops_per_sec": round(total_ops / wall_elapsed, 1),
            "avg_remember_seconds": round(remember_avg, 8),
            "avg_recall_seconds": round(recall_avg, 8),
            "errors": len(errors),
        }
        if errors:
            results["concurrent"]["error_details"] = errors[:5]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def bench_store_size(results: dict[str, Any]) -> None:
    """Benchmark database file size at various memory counts."""
    print("\nstore size on disk")
    print("-" * 40)

    bench_data: list[dict[str, Any]] = []
    for n in REMEMBER_SIZES:
        tmpdir = tempfile.mkdtemp(prefix="memorymesh_bench_")
        try:
            mesh = _make_mesh(tmpdir)
            for i in range(n):
                mesh.remember(_sample_text(i))
            mesh.close()

            size = _db_size_bytes(tmpdir)
            per_memory = size / n if n > 0 else 0
            print(f"  {n:>5} memories:  {_format_size(size):>10}  ({_format_size(int(per_memory))}/memory)")
            bench_data.append({
                "n": n,
                "total_bytes": size,
                "per_memory_bytes": round(per_memory),
            })
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    results["store_size"] = bench_data


def bench_auto_importance(results: dict[str, Any]) -> None:
    """Benchmark auto_importance scoring throughput."""
    print("\nauto_importance scoring")
    print("-" * 40)

    texts = [_sample_text(i) for i in range(1000)]

    start = time.perf_counter()
    for text in texts:
        score_importance(text)
    elapsed = time.perf_counter() - start

    per_op = elapsed / len(texts)
    print(f"  1000 texts:  {_format_time(elapsed):>10} total  ({_format_per_op(elapsed, len(texts))}/op)")

    # Also benchmark remember() with auto_importance=True
    tmpdir = tempfile.mkdtemp(prefix="memorymesh_bench_")
    try:
        mesh = _make_mesh(tmpdir)
        n = 500
        start = time.perf_counter()
        for i in range(n):
            mesh.remember(_sample_text(i), auto_importance=True)
        elapsed_remember = time.perf_counter() - start
        mesh.close()

        print(f"  remember(auto_importance=True, n=500):  {_format_time(elapsed_remember):>10} total  ({_format_per_op(elapsed_remember, n)}/op)")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    results["auto_importance"] = {
        "score_only": {
            "n": len(texts),
            "total_seconds": round(elapsed, 6),
            "per_op_seconds": round(per_op, 8),
        },
        "remember_with_auto": {
            "n": 500,
            "total_seconds": round(elapsed_remember, 6),
            "per_op_seconds": round(elapsed_remember / 500, 8),
        },
    }


def bench_compaction(results: dict[str, Any]) -> None:
    """Benchmark compaction on a store with near-duplicate memories."""
    print("\ncompaction impact")
    print("-" * 40)

    tmpdir = tempfile.mkdtemp(prefix="memorymesh_bench_")
    try:
        mesh = _make_mesh(tmpdir)

        # Insert 200 memories with ~50% near-duplicates
        for i in range(100):
            mesh.remember(_sample_text(i))
        # Insert near-duplicates (same content with minor variations)
        for i in range(100):
            mesh.remember(f"[Memory {i}] " + _sample_text(i)[len(f"[Memory {i}] "):] + f" (extra note {i})")

        count_before = mesh.count(scope="project")

        # Dry run first
        start = time.perf_counter()
        dry_result = mesh.compact(scope="project", similarity_threshold=0.85, dry_run=True)
        dry_elapsed = time.perf_counter() - start
        print(f"  dry run (200 memories):  {_format_time(dry_elapsed):>10}  ({dry_result.merged_count} merges planned)")

        # Measure recall before compaction
        start = time.perf_counter()
        for _ in range(10):
            mesh.recall("authentication JWT", k=5)
        recall_before = (time.perf_counter() - start) / 10

        # Actual compaction
        start = time.perf_counter()
        compact_result = mesh.compact(scope="project", similarity_threshold=0.85)
        compact_elapsed = time.perf_counter() - start

        count_after = mesh.count(scope="project")
        print(f"  compact (200 memories):  {_format_time(compact_elapsed):>10}  ({compact_result.merged_count} merged)")
        print(f"  memories: {count_before} -> {count_after}")

        # Measure recall after compaction
        start = time.perf_counter()
        for _ in range(10):
            mesh.recall("authentication JWT", k=5)
        recall_after = (time.perf_counter() - start) / 10

        print(f"  recall before:  {_format_time(recall_before)}")
        print(f"  recall after:   {_format_time(recall_after)}")

        mesh.close()

        results["compaction"] = {
            "memories_before": count_before,
            "memories_after": count_after,
            "merged_count": compact_result.merged_count,
            "compact_seconds": round(compact_elapsed, 6),
            "dry_run_seconds": round(dry_elapsed, 6),
            "recall_before_seconds": round(recall_before, 6),
            "recall_after_seconds": round(recall_after, 6),
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def bench_episodic(results: dict[str, Any]) -> None:
    """Benchmark episodic memory (session-based) operations."""
    print("\nepisodic memory (session_id)")
    print("-" * 40)

    tmpdir = tempfile.mkdtemp(prefix="memorymesh_bench_")
    try:
        mesh = _make_mesh(tmpdir)

        # Create memories across 10 sessions
        n_sessions = 10
        memories_per_session = 50
        session_ids: list[str] = []

        start = time.perf_counter()
        for s in range(n_sessions):
            sid = f"session-{s:04d}"
            session_ids.append(sid)
            for i in range(memories_per_session):
                mesh.remember(
                    _sample_text(s * memories_per_session + i),
                    session_id=sid,
                )
        remember_elapsed = time.perf_counter() - start
        total_memories = n_sessions * memories_per_session
        print(f"  remember ({total_memories} across {n_sessions} sessions):  {_format_time(remember_elapsed):>10}")

        # Benchmark get_session
        start = time.perf_counter()
        for sid in session_ids:
            mesh.get_session(sid, scope="project")
        get_session_elapsed = time.perf_counter() - start
        print(f"  get_session ({n_sessions} calls):  {_format_time(get_session_elapsed):>10}  ({_format_per_op(get_session_elapsed, n_sessions)}/call)")

        # Benchmark list_sessions
        start = time.perf_counter()
        for _ in range(10):
            mesh.list_sessions(scope="project")
        list_sessions_elapsed = time.perf_counter() - start
        print(f"  list_sessions (10 calls):  {_format_time(list_sessions_elapsed / 10):>10} avg")

        # Benchmark recall with session_id boost
        start = time.perf_counter()
        for _ in range(10):
            mesh.recall("authentication JWT", k=5, session_id="session-0005")
        recall_session_elapsed = (time.perf_counter() - start) / 10
        print(f"  recall with session_id:  {_format_time(recall_session_elapsed):>10} avg")

        mesh.close()

        results["episodic"] = {
            "n_sessions": n_sessions,
            "memories_per_session": memories_per_session,
            "total_memories": total_memories,
            "remember_seconds": round(remember_elapsed, 6),
            "get_session_seconds": round(get_session_elapsed, 6),
            "get_session_per_call_seconds": round(get_session_elapsed / n_sessions, 8),
            "list_sessions_avg_seconds": round(list_sessions_elapsed / 10, 8),
            "recall_with_session_avg_seconds": round(recall_session_elapsed, 8),
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all benchmarks and print results."""
    print("=" * 50)
    print("  MemoryMesh Benchmark Results")
    print("=" * 50)
    print(f"  Python {sys.version.split()[0]}")
    print("  Embedding: none (keyword-only)")

    results: dict[str, Any] = {
        "python_version": sys.version.split()[0],
        "embedding": "none",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    overall_start = time.perf_counter()

    bench_remember(results)
    bench_recall(results)
    bench_forget(results)
    bench_list_pagination(results)
    bench_concurrent(results)
    bench_store_size(results)
    bench_auto_importance(results)
    bench_compaction(results)
    bench_episodic(results)

    overall_elapsed = time.perf_counter() - overall_start
    results["total_seconds"] = round(overall_elapsed, 3)

    print("\n" + "=" * 50)
    print(f"  Total benchmark time: {_format_time(overall_elapsed)}")
    print("=" * 50)

    # Save JSON results
    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
