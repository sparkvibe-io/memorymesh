# FAQ

Common questions about MemoryMesh.

## Why SQLite, not plain .md files?

SQLite is the engine. Markdown is the view. This is the same pattern browsers use -- they store bookmarks in SQLite but display them as a list.

Plain markdown files cannot do: vector similarity search, importance scoring, access counting, time-based decay, metadata filtering, or atomic transactions. MemoryMesh uses SQLite for all of that, and syncs a readable snapshot to `.md` files for tools that need them.

## Why not a full RAG / vector database (Pinecone, Weaviate)?

MemoryMesh already IS local RAG. It embeds text, stores vectors, computes cosine similarity, and ranks results -- all in-process, all local. For AI memory scale (hundreds to low thousands of memories), SQLite with in-process similarity is faster and simpler than a separate database server. Zero infrastructure, zero cost, zero network latency.

## Why structured storage for unstructured data?

The text is unstructured -- `remember("whatever you want")` accepts any free-form string. The metadata is structured: importance scores, timestamps, access counts, decay rates, embeddings. The structure is invisible plumbing that makes recall smart. You never see it unless you want to.

## What does "semantic search" mean?

Instead of matching exact keywords, semantic search understands meaning. Searching "How do we handle auth?" finds memories about authentication even if they never contain the word "auth." This requires an embedding provider (local, Ollama, or OpenAI). Without one, MemoryMesh falls back to keyword matching, which still works well for most use cases.

## What is the difference between standalone and with Ollama?

**Standalone** (`embedding="none"`) uses keyword matching -- fast, zero dependencies, good for most use cases. **With Ollama** (`embedding="ollama"`) you get semantic search via a local model -- better recall accuracy, still fully local, no API keys. Ollama runs on your machine just like MemoryMesh.

## Do I need an API key?

No. The base install works with zero dependencies and zero API keys. Ollama embeddings are also free and local. Only OpenAI embeddings require an API key.

## Can I use MemoryMesh with multiple AI tools at once?

Yes. MemoryMesh stores memories in SQLite and can sync to Claude Code (`MEMORY.md`), Codex CLI (`AGENTS.md`), and Gemini CLI (`GEMINI.md`) simultaneously. Run `memorymesh sync --to auto --format all` and your knowledge follows you across tools.

---

[Back to README](../README.md)
