"""MemoryMesh HTTP server for Smithery deployment.

Wraps the MemoryMesh library as a Streamable HTTP MCP server using FastMCP,
enabling deployment on Smithery's container hosting platform.

The server exposes the same 10 tools as the stdio MCP server:
  remember, recall, forget, forget_all, update_memory, memory_stats,
  session_start, review_memories, status, configure_project

Environment variables:
    PORT                   HTTP port (default: 8080, set by Smithery)
    MEMORYMESH_EMBEDDING   Embedding provider (default: "none")
    MEMORYMESH_PATH        Path to project SQLite database
    MEMORYMESH_GLOBAL_PATH Path to global SQLite database
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Optional

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.middleware.cors import CORSMiddleware

from memorymesh import MemoryMesh, __version__
from memorymesh.memory import GLOBAL_SCOPE, PROJECT_SCOPE
from memorymesh.review import review_memories
from middleware import SmitheryConfigMiddleware

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(name="MemoryMesh")

# ---------------------------------------------------------------------------
# Shared MemoryMesh instance
# ---------------------------------------------------------------------------

_mesh: Optional[MemoryMesh] = None


def _get_mesh() -> MemoryMesh:
    """Get or create the shared MemoryMesh instance."""
    global _mesh
    if _mesh is None:
        path = os.environ.get("MEMORYMESH_PATH")
        global_path = os.environ.get("MEMORYMESH_GLOBAL_PATH")
        embedding = os.environ.get("MEMORYMESH_EMBEDDING", "none")
        _mesh = MemoryMesh(
            path=path,
            global_path=global_path,
            embedding=embedding,
        )
    return _mesh


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(
    title="Remember",
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
))
def remember(
    text: Annotated[str, Field(description="The text content to remember.")],
    category: Annotated[Optional[str], Field(description="Memory category. Auto-routes scope (e.g. 'preference' -> global, 'decision' -> project).")] = None,
    importance: Annotated[Optional[float], Field(description="Importance score between 0.0 and 1.0. Higher = more prominent during recall. Default: 0.5.")] = None,
    scope: Annotated[Optional[str], Field(description="Where to store: 'project' (default) or 'global'.")] = None,
    auto_categorize: Annotated[bool, Field(description="If true, auto-detect category and importance from text.")] = False,
    on_conflict: Annotated[Optional[str], Field(description="Contradiction handling: 'keep_both' (default), 'update', or 'skip'.")] = None,
    pin: Annotated[bool, Field(description="Pin this memory. Pinned memories have max importance and never decay.")] = False,
    redact_secrets: Annotated[bool, Field(description="If true, redact detected secrets (API keys, tokens) before storing.")] = False,
    metadata: Annotated[Optional[dict[str, Any]], Field(description="Key-value metadata to attach to the memory.")] = None,
) -> str:
    """Store a new memory in MemoryMesh. Use this to save facts, preferences, decisions, or any information that should persist across conversations."""
    mesh = _get_mesh()
    mem = mesh.remember(
        text=text,
        category=category,
        importance=importance,
        scope=scope,
        auto_categorize=auto_categorize,
        on_conflict=on_conflict,
        pin=pin,
        redact_secrets=redact_secrets,
        metadata=metadata,
    )
    return f"Remembered (id={mem.id}, scope={mem.scope}): {text[:80]}"


@mcp.tool(annotations=ToolAnnotations(
    title="Recall",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
))
def recall(
    query: Annotated[str, Field(description="Natural-language query describing what to recall.")],
    k: Annotated[int, Field(description="Maximum number of memories to return. Default: 5.")] = 5,
    scope: Annotated[Optional[str], Field(description="Limit search to 'project' or 'global'. Omit to search both.")] = None,
    category: Annotated[Optional[str], Field(description="Filter by memory category.")] = None,
    min_importance: Annotated[Optional[float], Field(description="Only return memories with importance >= this value.")] = None,
) -> list[dict[str, Any]]:
    """Recall relevant memories from MemoryMesh using semantic similarity and keyword matching."""
    mesh = _get_mesh()
    memories = mesh.recall(
        query=query,
        k=k,
        scope=scope,
        category=category,
        min_importance=min_importance,
    )
    return [
        {
            "id": m.id,
            "text": m.text,
            "category": m.category,
            "importance": m.importance,
            "scope": m.scope,
            "created_at": m.created_at,
        }
        for m in memories
    ]


@mcp.tool(annotations=ToolAnnotations(
    title="Forget",
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=False,
))
def forget(
    memory_id: Annotated[str, Field(description="The unique identifier of the memory to delete.")],
) -> str:
    """Permanently delete a specific memory by its ID. Searches both project and global stores."""
    mesh = _get_mesh()
    mesh.forget(memory_id)
    return f"Forgotten: {memory_id}"


@mcp.tool(annotations=ToolAnnotations(
    title="Forget All",
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=False,
))
def forget_all(
    scope: Annotated[str, Field(description="Which scope to clear: 'project' (default) or 'global'.")] = "project",
) -> str:
    """Forget ALL stored memories in the specified scope. This is a destructive operation."""
    mesh = _get_mesh()
    mesh.forget_all(scope=scope)
    return f"All {scope} memories forgotten."


@mcp.tool(annotations=ToolAnnotations(
    title="Update Memory",
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
))
def update_memory(
    memory_id: Annotated[str, Field(description="The ID of the memory to update.")],
    text: Annotated[Optional[str], Field(description="New text content (replaces existing).")] = None,
    importance: Annotated[Optional[float], Field(description="New importance score between 0.0 and 1.0.")] = None,
    scope: Annotated[Optional[str], Field(description="Move memory to this scope: 'project' or 'global'.")] = None,
    metadata: Annotated[Optional[dict[str, Any]], Field(description="New metadata key-value pairs (replaces existing).")] = None,
) -> str:
    """Update an existing memory's text, importance, scope, or metadata in place. Only provided fields are changed."""
    mesh = _get_mesh()
    fields: dict[str, Any] = {}
    if text is not None:
        fields["text"] = text
    if importance is not None:
        fields["importance"] = importance
    if scope is not None:
        fields["scope"] = scope
    if metadata is not None:
        fields["metadata"] = metadata
    mesh.update(memory_id, **fields)
    return f"Updated: {memory_id}"


@mcp.tool(annotations=ToolAnnotations(
    title="Memory Stats",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
))
def memory_stats(
    scope: Annotated[Optional[str], Field(description="Limit stats to 'project' or 'global'. Omit for combined stats.")] = None,
) -> dict[str, Any]:
    """Get statistics about stored memories: total count, oldest and newest timestamps."""
    mesh = _get_mesh()
    stats = mesh.stats(scope=scope)
    return stats


@mcp.tool(annotations=ToolAnnotations(
    title="Session Start",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
))
def session_start(
    project_context: Annotated[Optional[str], Field(description="Brief description of what the user is working on.")] = None,
) -> dict[str, Any]:
    """Retrieve structured context for the start of a new AI session. Returns user profile, guardrails, and project context."""
    mesh = _get_mesh()
    context = mesh.session_start(project_context=project_context)
    return context


@mcp.tool(
    name="review_memories",
    annotations=ToolAnnotations(
        title="Review Memories",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def review_memories_tool(
    scope: Annotated[Optional[str], Field(description="Limit review to 'project' or 'global'. Omit to review all.")] = None,
) -> dict[str, Any]:
    """Audit memories for quality issues (scope mismatches, verbosity, staleness, duplicates). Returns issues with suggestions."""
    mesh = _get_mesh()
    stores = []
    if scope != GLOBAL_SCOPE and mesh._project_store:
        stores.append(("project", mesh._project_store))
    if scope != PROJECT_SCOPE and mesh._global_store:
        stores.append(("global", mesh._global_store))

    all_issues = []
    for store_scope, store in stores:
        result = review_memories(store, scope=store_scope)
        all_issues.extend(
            {"scope": store_scope, "type": i.issue_type, "message": i.message, "memory_id": i.memory_id}
            for i in result.issues
        )
    return {"issues": all_issues, "count": len(all_issues)}


@mcp.tool(annotations=ToolAnnotations(
    title="Status",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
))
def status() -> dict[str, Any]:
    """Get MemoryMesh health status: project store, global store, embedding provider, and version."""
    mesh = _get_mesh()
    return {
        "version": __version__,
        "project_store": mesh._project_store is not None,
        "global_store": mesh._global_store is not None,
        "embedding": str(type(mesh._embedding).__name__),
    }


@mcp.tool(annotations=ToolAnnotations(
    title="Configure Project",
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
))
def configure_project(
    path: Annotated[str, Field(description="Absolute path to the project root directory.")],
) -> str:
    """Set the project root at runtime without restarting the server. Creates the project database at <path>/.memorymesh/memories.db."""
    mesh = _get_mesh()
    db_path = os.path.join(os.path.expanduser(path), ".memorymesh", "memories.db")
    os.environ["MEMORYMESH_PATH"] = db_path
    # Reinitialize with new path
    global _mesh
    _mesh = None
    _get_mesh()
    return f"Project configured: {path}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the HTTP server for Smithery deployment."""
    app = mcp.streamable_http_app()

    # CORS for browser-based MCP clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "mcp-protocol-version"],
        max_age=86400,
    )

    # Smithery config extraction middleware
    app = SmitheryConfigMiddleware(app)

    port = int(os.environ.get("PORT", 8080))
    print(f"MemoryMesh MCP Server v{__version__} starting on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
