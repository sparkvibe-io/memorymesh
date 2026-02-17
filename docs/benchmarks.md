# Benchmarks

Performance benchmarks for MemoryMesh core operations.

## Results

On a typical development machine (keyword-only mode, `embedding="none"`):

| Operation | Latency | Notes |
|---|---|---|
| `remember()` | ~50 us/op | Constant time, regardless of store size |
| `recall()` at 100 memories | ~120 us | Top-5 results |
| `recall()` at 1,000 memories | ~350 us | Top-5 results |
| `recall()` at 5,000 memories | < 700 us | Top-5 results |
| `forget()` | ~30 us/op | Single memory deletion |
| `list()` pagination | ~200 us | Page through 1,000 memories |
| Concurrent throughput | ~3,800 ops/s | 4 threads, mixed read/write |
| `auto_importance` scoring | ~15 us/op | Heuristic text analysis |

### Disk Usage

| Memory Count | Database Size |
|---|---|
| 100 | ~20 KB |
| 1,000 | ~180 KB |
| 5,000 | ~900 KB |
| 10,000 | ~1.8 MB |

SQLite with WAL mode keeps databases compact. Embeddings (when enabled) add ~3 KB per memory for 768-dimensional vectors.

## Running Benchmarks

```bash
# Via Makefile
make bench

# Directly
python -m benchmarks.bench_memorymesh

# Or from the project root
.venv/bin/python -m benchmarks.bench_memorymesh
```

## What Is Measured

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

## Configuration

All benchmarks use `embedding="none"` (keyword-only mode) by default for consistent, reproducible results without external dependencies. Each benchmark creates temporary databases that are cleaned up after the run.

Results are printed to stdout as a formatted table and saved as JSON to `benchmarks/results.json` for tracking over time.

## Interpreting Results

- **per-op times** under 1ms are excellent for interactive use
- **concurrent throughput** above 500 ops/s indicates SQLite WAL mode is performing well
- **store size** should scale roughly linearly with memory count
- **compaction** should reduce both memory count and subsequent recall latency
