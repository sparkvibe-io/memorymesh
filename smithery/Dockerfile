# MemoryMesh Smithery Container
# Runs the HTTP MCP server for Smithery's container hosting platform.
FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy project files
COPY pyproject.toml server.py middleware.py ./

# Install dependencies (generates lock on the fly)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Smithery requires port 8080
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT []
CMD ["python", "server.py"]
