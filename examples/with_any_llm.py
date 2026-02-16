"""MemoryMesh works with ANY LLM - it's just a memory layer.

This example shows how to use MemoryMesh as a memory layer
alongside any LLM provider (Claude, GPT, Gemini, Llama, Mistral, etc.)

MemoryMesh is NOT an LLM. It is a persistent memory store that sits
alongside your LLM of choice, providing context from past interactions.
"""

from memorymesh import MemoryMesh

# MemoryMesh is LLM-agnostic - it manages memory, not the LLM
memory = MemoryMesh(embedding="none")  # Even works without ML!

# Step 1: Before calling your LLM, recall relevant memories
user_message = "Can you help me with my Python project?"
relevant = memory.recall(user_message, k=3)

# Step 2: Build context from memories
memory_context = ""
if relevant:
    memory_context = "Previous context about this user:\n"
    memory_context += "\n".join(f"- {m.text}" for m in relevant)

# Step 3: Pass to ANY LLM (pseudocode - replace with your LLM client)
# response = your_llm_client.chat(
#     system=f"You are a helpful assistant.\n\n{memory_context}",
#     message=user_message,
# )

# Step 4: After the conversation, remember important things
memory.remember("User is working on a Python project")
memory.remember("User asked for help with Python", metadata={"topic": "python"})

print(f"Stored {memory.count()} memories")
print("Works with Claude, GPT, Gemini, Llama, Ollama, Mistral, or any other LLM!")
