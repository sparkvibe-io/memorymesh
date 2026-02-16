"""MemoryMesh Quick Start - 3 lines to AI memory."""

from memorymesh import MemoryMesh

# Initialize (SQLite database, no external services needed)
memory = MemoryMesh()

# Remember something
memory.remember("User prefers Python and dark mode")
memory.remember("User is working on a machine learning project")
memory.remember("User's name is Alex")

# Recall relevant memories
results = memory.recall("What programming language does the user like?")
for m in results:
    print(f"  [{m.importance:.2f}] {m.text}")

# Forget a specific memory
if results:
    memory.forget(results[0].id)
    print(f"Forgot memory: {results[0].text}")

print(f"Total memories: {memory.count()}")
