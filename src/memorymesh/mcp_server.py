"""MemoryMesh MCP Server -- Model Context Protocol interface.

Exposes MemoryMesh as an MCP tool server over stdin/stdout JSON-RPC,
allowing any MCP-compatible AI tool (Claude Code, Cursor, Windsurf, etc.)
to use ``remember``, ``recall``, ``forget``, ``forget_all``, and
``memory_stats`` as first-class tools.

This module uses **only the Python standard library** (json, sys, logging)
so it introduces zero additional dependencies.

Configuration via environment variables:

    MEMORYMESH_PATH        Path to the SQLite database file.
    MEMORYMESH_EMBEDDING   Embedding provider name (default: "none").
    MEMORYMESH_OLLAMA_MODEL  Ollama model name when using ollama embeddings.
    OPENAI_API_KEY         API key when using openai embeddings.

Usage::

    # Run directly:
    python -m memorymesh.mcp_server

    # Or via the installed entry point:
    memorymesh-mcp
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

from .core import MemoryMesh

# ---------------------------------------------------------------------------
# Logging -- all output goes to stderr so stdout stays clean for JSON-RPC
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if os.environ.get("MEMORYMESH_DEBUG") else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("memorymesh.mcp_server")

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

SERVER_INFO = {
    "name": "memorymesh",
    "version": "0.1.0",
}

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "remember",
        "description": (
            "Store a new memory in MemoryMesh. Use this to save facts, preferences, "
            "decisions, or any information that should persist across conversations. "
            "Returns the unique memory ID."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text content to remember.",
                },
                "metadata": {
                    "type": "object",
                    "description": (
                        "Optional key-value metadata to attach to the memory "
                        "(e.g., {\"source\": \"user\", \"topic\": \"preferences\"})."
                    ),
                    "additionalProperties": True,
                },
                "importance": {
                    "type": "number",
                    "description": (
                        "Importance score between 0.0 and 1.0. Higher values make "
                        "the memory more prominent during recall. Default: 0.5."
                    ),
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "recall",
        "description": (
            "Recall relevant memories from MemoryMesh. Searches stored memories "
            "using semantic similarity (when embeddings are enabled) and keyword "
            "matching. Returns the most relevant memories ranked by relevance."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language query describing what to recall.",
                },
                "k": {
                    "type": "integer",
                    "description": "Maximum number of memories to return. Default: 5.",
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "forget",
        "description": (
            "Forget (permanently delete) a specific memory by its ID. "
            "Use this when information is outdated or incorrect."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "The unique identifier of the memory to delete.",
                },
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "forget_all",
        "description": (
            "Forget ALL stored memories. This is a destructive operation that "
            "permanently deletes every memory in the database. Use with caution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "memory_stats",
        "description": (
            "Get statistics about stored memories: total count, oldest memory "
            "timestamp, and newest memory timestamp."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------


class MemoryMeshMCPServer:
    """MCP server that wraps a MemoryMesh instance.

    Reads JSON-RPC messages from stdin and writes responses to stdout,
    following the Model Context Protocol specification.

    Args:
        mesh: An existing :class:`MemoryMesh` instance to use. If ``None``,
            one will be created from environment variable configuration.
    """

    def __init__(self, mesh: MemoryMesh | None = None) -> None:
        if mesh is not None:
            self._mesh = mesh
        else:
            self._mesh = self._create_mesh_from_env()
        self._initialized = False
        logger.info("MemoryMeshMCPServer created with mesh=%r", self._mesh)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def _create_mesh_from_env() -> MemoryMesh:
        """Build a MemoryMesh instance from environment variables.

        Reads ``MEMORYMESH_PATH``, ``MEMORYMESH_EMBEDDING``,
        ``MEMORYMESH_OLLAMA_MODEL``, and ``OPENAI_API_KEY`` from the
        environment and forwards them to the MemoryMesh constructor.

        Returns:
            A configured :class:`MemoryMesh` instance.
        """
        path = os.environ.get("MEMORYMESH_PATH")
        embedding = os.environ.get("MEMORYMESH_EMBEDDING", "none")

        kwargs: dict[str, Any] = {}

        ollama_model = os.environ.get("MEMORYMESH_OLLAMA_MODEL")
        if ollama_model:
            kwargs["ollama_model"] = ollama_model

        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            kwargs["openai_api_key"] = openai_key

        logger.info(
            "Creating MemoryMesh from env: path=%r, embedding=%r",
            path,
            embedding,
        )
        return MemoryMesh(path=path, embedding=embedding, **kwargs)

    # ------------------------------------------------------------------
    # Message loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run the server's main read-dispatch-write loop.

        Reads newline-delimited JSON-RPC messages from stdin until EOF,
        dispatches each to the appropriate handler, and writes the
        response to stdout.  Notifications (no ``id``) do not produce
        a response.
        """
        logger.info("MCP server starting, reading from stdin...")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            logger.debug("Received: %s", line[:200])

            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                self._send_error(None, -32700, f"Parse error: {exc}")
                continue

            # JSON-RPC batch is not required by MCP but handle gracefully.
            if isinstance(message, list):
                for msg in message:
                    self._handle_message(msg)
            else:
                self._handle_message(message)

        logger.info("stdin closed, shutting down.")
        self._mesh.close()

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _handle_message(self, message: dict[str, Any]) -> None:
        """Route a single JSON-RPC message to the correct handler.

        Args:
            message: A parsed JSON-RPC request or notification.
        """
        if not isinstance(message, dict):
            self._send_error(None, -32600, "Invalid request: expected a JSON object.")
            return

        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params", {})

        if method is None:
            self._send_error(msg_id, -32600, "Invalid request: missing 'method'.")
            return

        logger.debug("Dispatching method=%r id=%r", method, msg_id)

        handler = self._get_handler(method)
        if handler is None:
            # Notifications we don't handle can be silently ignored.
            if msg_id is not None:
                self._send_error(msg_id, -32601, f"Method not found: {method}")
            return

        try:
            result = handler(params)
        except Exception as exc:
            logger.exception("Error handling %s", method)
            self._send_error(msg_id, -32603, f"Internal error: {exc}")
            return

        # Only send a response for requests (those with an id).
        if msg_id is not None:
            self._send_result(msg_id, result)

    def _get_handler(self, method: str) -> Any:
        """Look up the handler function for a given MCP method.

        Args:
            method: The JSON-RPC method name.

        Returns:
            A callable ``(params) -> result``, or ``None`` if the method
            is not supported.
        """
        handlers: dict[str, Any] = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "notifications/initialized": self._handle_initialized,
        }
        return handlers.get(method)

    # ------------------------------------------------------------------
    # Protocol handlers
    # ------------------------------------------------------------------

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ``initialize`` request.

        Returns server capabilities and info per the MCP specification.

        Args:
            params: Client-provided initialization parameters.

        Returns:
            A dict with ``protocolVersion``, ``capabilities``, and
            ``serverInfo``.
        """
        self._initialized = True
        logger.info(
            "Client initialized: %s",
            params.get("clientInfo", {}).get("name", "unknown"),
        )
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {},
            },
            "serverInfo": SERVER_INFO,
        }

    def _handle_initialized(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ``initialized`` notification.

        This is a no-op acknowledgement sent by the client after the
        initialize handshake completes.

        Args:
            params: Notification parameters (unused).

        Returns:
            An empty dict (notifications do not produce visible responses).
        """
        logger.debug("Client sent 'initialized' notification.")
        return {}

    def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ``ping`` request.

        Args:
            params: Ping parameters (unused).

        Returns:
            An empty dict as acknowledgement.
        """
        return {}

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ``tools/list`` request.

        Args:
            params: List parameters (unused).

        Returns:
            A dict with a ``tools`` key containing all tool definitions.
        """
        return {"tools": TOOLS}

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ``tools/call`` request.

        Dispatches to the appropriate tool handler based on the tool name,
        validates arguments, and returns the result in MCP content format.

        Args:
            params: Must contain ``name`` (tool name) and optionally
                ``arguments`` (tool parameters).

        Returns:
            A dict with a ``content`` list containing the tool result.

        Raises:
            ValueError: If the tool name is unknown or arguments are invalid.
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        logger.info("Tool call: %s(%r)", tool_name, arguments)

        tool_handlers: dict[str, Any] = {
            "remember": self._tool_remember,
            "recall": self._tool_recall,
            "forget": self._tool_forget,
            "forget_all": self._tool_forget_all,
            "memory_stats": self._tool_memory_stats,
        }

        handler = tool_handlers.get(tool_name)  # type: ignore[arg-type]
        if handler is None:
            return self._tool_error(f"Unknown tool: {tool_name}")

        try:
            return handler(arguments)
        except Exception as exc:
            logger.exception("Tool %s raised an exception", tool_name)
            return self._tool_error(f"Tool '{tool_name}' failed: {exc}")

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_remember(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``remember`` tool.

        Args:
            args: Tool arguments. Must include ``text``. May include
                ``metadata`` and ``importance``.

        Returns:
            MCP content response with the new memory ID.
        """
        text = args.get("text")
        if not text or not isinstance(text, str):
            return self._tool_error("'text' is required and must be a non-empty string.")

        metadata = args.get("metadata", {})
        if not isinstance(metadata, dict):
            return self._tool_error("'metadata' must be an object.")

        importance = args.get("importance", 0.5)
        if not isinstance(importance, (int, float)):
            return self._tool_error("'importance' must be a number.")
        importance = max(0.0, min(1.0, float(importance)))

        memory_id = self._mesh.remember(
            text=text,
            metadata=metadata,
            importance=importance,
        )

        result = {
            "memory_id": memory_id,
            "message": f"Remembered: {text[:80]}{'...' if len(text) > 80 else ''}",
        }
        return self._tool_success(json.dumps(result, indent=2))

    def _tool_recall(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``recall`` tool.

        Args:
            args: Tool arguments. Must include ``query``. May include ``k``.

        Returns:
            MCP content response with a list of matching memories.
        """
        query = args.get("query")
        if not query or not isinstance(query, str):
            return self._tool_error("'query' is required and must be a non-empty string.")

        k = args.get("k", 5)
        if not isinstance(k, int) or k < 1:
            return self._tool_error("'k' must be a positive integer.")
        k = min(k, 100)

        memories = self._mesh.recall(query=query, k=k)

        results = []
        for mem in memories:
            results.append({
                "id": mem.id,
                "text": mem.text,
                "metadata": mem.metadata,
                "importance": round(mem.importance, 4),
                "created_at": mem.created_at.isoformat(),
                "access_count": mem.access_count,
            })

        output = {
            "query": query,
            "count": len(results),
            "memories": results,
        }
        return self._tool_success(json.dumps(output, indent=2))

    def _tool_forget(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``forget`` tool.

        Args:
            args: Tool arguments. Must include ``memory_id``.

        Returns:
            MCP content response indicating success or failure.
        """
        memory_id = args.get("memory_id")
        if not memory_id or not isinstance(memory_id, str):
            return self._tool_error("'memory_id' is required and must be a string.")

        deleted = self._mesh.forget(memory_id)
        result = {
            "memory_id": memory_id,
            "deleted": deleted,
            "message": (
                f"Memory {memory_id} deleted."
                if deleted
                else f"Memory {memory_id} not found."
            ),
        }
        return self._tool_success(json.dumps(result, indent=2))

    def _tool_forget_all(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``forget_all`` tool.

        Args:
            args: Tool arguments (unused).

        Returns:
            MCP content response with the count of deleted memories.
        """
        count = self._mesh.forget_all()
        result = {
            "deleted_count": count,
            "message": f"Deleted all {count} memories.",
        }
        return self._tool_success(json.dumps(result, indent=2))

    def _tool_memory_stats(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``memory_stats`` tool.

        Args:
            args: Tool arguments (unused).

        Returns:
            MCP content response with memory statistics.
        """
        total = self._mesh.count()

        oldest_str: str | None = None
        newest_str: str | None = None

        if total > 0:
            # Fetch the oldest and newest memories by listing with pagination.
            # list() returns memories ordered by most recently updated first.
            all_memories = self._mesh.list(limit=total, offset=0)
            if all_memories:
                sorted_by_created = sorted(all_memories, key=lambda m: m.created_at)
                oldest_str = sorted_by_created[0].created_at.isoformat()
                newest_str = sorted_by_created[-1].created_at.isoformat()

        result = {
            "total_memories": total,
            "oldest_memory": oldest_str,
            "newest_memory": newest_str,
        }
        return self._tool_success(json.dumps(result, indent=2))

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tool_success(text: str) -> dict[str, Any]:
        """Build a successful MCP tool result.

        Args:
            text: The text content of the result.

        Returns:
            MCP-formatted content response.
        """
        return {
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }

    @staticmethod
    def _tool_error(message: str) -> dict[str, Any]:
        """Build an error MCP tool result.

        Args:
            message: Human-readable error description.

        Returns:
            MCP-formatted error content response with ``isError`` flag.
        """
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"error": message}),
                }
            ],
            "isError": True,
        }

    def _send_result(self, msg_id: Any, result: Any) -> None:
        """Write a JSON-RPC success response to stdout.

        Args:
            msg_id: The request ID to echo back.
            result: The result payload.
        """
        response = {
            "jsonrpc": JSONRPC_VERSION,
            "id": msg_id,
            "result": result,
        }
        self._write_message(response)

    def _send_error(
        self,
        msg_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> None:
        """Write a JSON-RPC error response to stdout.

        Args:
            msg_id: The request ID to echo back (may be ``None``).
            code: Numeric error code per JSON-RPC spec.
            message: Human-readable error description.
            data: Optional additional error data.
        """
        error_obj: dict[str, Any] = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error_obj["data"] = data

        response: dict[str, Any] = {
            "jsonrpc": JSONRPC_VERSION,
            "id": msg_id,
            "error": error_obj,
        }
        self._write_message(response)

    @staticmethod
    def _write_message(message: dict[str, Any]) -> None:
        """Serialize and write a JSON-RPC message to stdout.

        Each message is written as a single line of JSON followed by a
        newline, which is the standard framing for MCP over stdio.

        Args:
            message: The JSON-RPC message dict to send.
        """
        line = json.dumps(message, ensure_ascii=False)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MemoryMesh MCP server.

    This is the entry point used by the ``memorymesh-mcp`` console script
    and by ``python -m memorymesh.mcp_server``.
    """
    logger.info("Starting MemoryMesh MCP server...")
    logger.info(
        "Config: MEMORYMESH_PATH=%r  MEMORYMESH_EMBEDDING=%r",
        os.environ.get("MEMORYMESH_PATH", "(default)"),
        os.environ.get("MEMORYMESH_EMBEDDING", "none"),
    )

    try:
        server = MemoryMeshMCPServer()
        server.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user.")
        sys.exit(0)
    except Exception:
        logger.exception("Fatal error in MCP server.")
        sys.exit(1)


if __name__ == "__main__":
    main()
