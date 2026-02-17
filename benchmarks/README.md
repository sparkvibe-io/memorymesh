# MemoryMesh Benchmarks

Performance benchmarks for MemoryMesh core operations.

## Running

```bash
# Via Makefile
make bench

# Directly
python -m benchmarks.bench_memorymesh

# Or from the project root
.venv/bin/python -m benchmarks.bench_memorymesh
```

## What is measured

| Benchmark | Description |
|---|---|
| **remember() throughput** | Time to store N memories (10, 100, 1000, 5000) |
| **recall() latency** | Time to recall top-k from stores of various sizes |
| **forget() latency** | Time to delete memories from stores of various sizes |
| **list() pagination** | Time to paginate through a 1000-memory store |
| **concurrent access** | Multi-threaded remember/recall (4 threads, 50 ops each) |
| **store size on disk** | SQLite database file size at various memory counts |
| **auto_importance scoring** | Throughput of heuristic importance scoring |
| **compaction impact** | Before/after compaction performance and memory count |
| **episodic memory** | Session-based remember, get_session, list_sessions |

## Output

Results are printed to stdout as a formatted table and saved as JSON to `benchmarks/results.json` for tracking over time.

## Configuration

All benchmarks use `embedding="none"` (keyword-only mode) by default for consistent, reproducible results without external dependencies. Each benchmark creates temporary databases that are cleaned up after the run.

## Interpreting results

- **per-op times** under 1ms are excellent for interactive use
- **concurrent throughput** above 500 ops/s indicates SQLite WAL mode is performing well
- **store size** should scale roughly linearly with memory count
- **compaction** should reduce both memory count and subsequent recall latency
