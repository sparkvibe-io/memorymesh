"""MemoryMesh with OpenAI - works with any OpenAI-powered application.

Uses OpenAI's text-embedding-ada-002 (or newer) model to generate
high-quality embeddings for semantic recall.

Requirements:
    - ``pip install memorymesh[openai]`` (or ``pip install openai``)
    - A valid OpenAI API key set as OPENAI_API_KEY environment variable
"""

import os

from memorymesh import MemoryMesh

memory = MemoryMesh(
    embedding="openai",
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

# Build user memory over time
memory.remember("User is a data scientist at a healthcare company")
memory.remember("User prefers pandas over polars for data analysis")
memory.remember("User needs HIPAA-compliant solutions")

# Retrieve relevant memories to augment LLM context
query = "What tools should I recommend for data processing?"
memories = memory.recall(query, k=3)

# Format memories as context for any LLM
context = "\n".join(f"- {m.text}" for m in memories)
print(f"Context for LLM:\n{context}")
