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
from typing import Any, Optional

import uvicorn
from mcp.server.fastmcp import FastMCP
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


@mcp.tool()
def remember(
    text: str,
    category: Optional[str] = None,
    importance: Optional[float] = None,
    scope: Optional[str] = None,
    auto_categorize: bool = False,
    on_conflict: Optional[str] = None,
    pin: bool = False,
    redact_secrets: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Store a new memory in MemoryMesh.

    Use this to save facts, preferences, decisions, or any information
    that should persist across conversations.
    """
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


@mcp.tool()
def recall(
    query: str,
    k: int = 5,
    scope: Optional[str] = None,
    category: Optional[str] = None,
    min_importance: Optional[float] = None,
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


@mcp.tool()
def forget(memory_id: str) -> str:
    """Permanently delete a specific memory by its ID."""
    mesh = _get_mesh()
    mesh.forget(memory_id)
    return f"Forgotten: {memory_id}"


@mcp.tool()
def forget_all(scope: str = "project") -> str:
    """Forget ALL stored memories in the specified scope. Destructive operation."""
    mesh = _get_mesh()
    mesh.forget_all(scope=scope)
    return f"All {scope} memories forgotten."


@mcp.tool()
def update_memory(
    memory_id: str,
    text: Optional[str] = None,
    importance: Optional[float] = None,
    scope: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Update an existing memory's text, importance, scope, or metadata in place."""
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


@mcp.tool()
def memory_stats(scope: Optional[str] = None) -> dict[str, Any]:
    """Get statistics about stored memories: total count, oldest and newest timestamps."""
    mesh = _get_mesh()
    stats = mesh.stats(scope=scope)
    return stats


@mcp.tool()
def session_start(project_context: Optional[str] = None) -> dict[str, Any]:
    """Retrieve structured context for the start of a new AI session."""
    mesh = _get_mesh()
    context = mesh.session_start(project_context=project_context)
    return context


@mcp.tool()
def review_memories_tool(scope: Optional[str] = None) -> dict[str, Any]:
    """Audit memories for quality issues (scope mismatches, verbosity, staleness, duplicates)."""
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


@mcp.tool()
def status() -> dict[str, Any]:
    """Get MemoryMesh health status: project store, global store, embedding provider, and version."""
    mesh = _get_mesh()
    return {
        "version": __version__,
        "project_store": mesh._project_store is not None,
        "global_store": mesh._global_store is not None,
        "embedding": str(type(mesh._embedding).__name__),
    }


@mcp.tool()
def configure_project(path: str) -> str:
    """Set the project root at runtime without restarting the server."""
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
