"""MemoryMesh with Ollama for local embeddings.

Ollama provides fast, private, local embedding models. Combined with
MemoryMesh's SQLite storage, this gives you a fully local AI memory
system with zero cloud dependencies.

Requirements:
    - Ollama installed and running locally (https://ollama.com)
    - An embedding model pulled: ``ollama pull nomic-embed-text``
"""

from memorymesh import MemoryMesh

# Use Ollama for embeddings (requires Ollama running locally)
memory = MemoryMesh(embedding="ollama", ollama_model="nomic-embed-text")

# Store conversation context
memory.remember("User asked about deploying Flask apps to production")
memory.remember("User prefers Docker-based deployments")
memory.remember("User's tech stack: Python, Flask, PostgreSQL, Redis")

# Later, recall relevant context
context = memory.recall("How should I deploy my app?")
print("Relevant context for deployment question:")
for m in context:
    print(f"  - {m.text}")
