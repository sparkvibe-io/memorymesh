"""MemoryMesh MCP Server -- Model Context Protocol interface.

Exposes MemoryMesh as an MCP tool server over stdin/stdout JSON-RPC,
allowing any MCP-compatible AI tool (Claude Code, Cursor, Windsurf, etc.)
to use ``remember``, ``recall``, ``forget``, ``forget_all``,
``memory_stats``, and ``session_start`` as first-class tools.

This module uses **only the Python standard library** (json, sys, logging)
so it introduces zero additional dependencies.

Configuration via environment variables:

    MEMORYMESH_PATH        Path to the project SQLite database file.
    MEMORYMESH_GLOBAL_PATH Path to the global SQLite database file.
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
from .memory import GLOBAL_SCOPE, PROJECT_SCOPE
from .store import detect_project_root

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
    "version": "2.0.0",
}

# ---------------------------------------------------------------------------
# Security limits
# ---------------------------------------------------------------------------

MAX_TEXT_LENGTH = 100_000  # Maximum characters for memory text
MAX_METADATA_SIZE = 10_000  # Maximum serialized metadata JSON size (bytes)
MAX_MESSAGE_SIZE = 1_000_000  # Maximum JSON-RPC message size (bytes)
MAX_BATCH_SIZE = 50  # Maximum messages in a JSON-RPC batch
MAX_MEMORY_COUNT = 100_000  # Maximum total memories allowed

# ---------------------------------------------------------------------------
# Prompt and tool definitions
# ---------------------------------------------------------------------------

PROMPTS: list[dict[str, Any]] = [
    {
        "name": "memory-context",
        "description": (
            "Retrieve relevant memories for the current conversation context. "
            "Provides persistent knowledge from previous sessions."
        ),
        "arguments": [
            {
                "name": "context",
                "description": (
                    "Brief description of what you're working on "
                    "(used to find relevant memories)."
                ),
                "required": False,
            }
        ],
    },
]

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
                        '(e.g., {"source": "user", "topic": "preferences"}).'
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
                "scope": {
                    "type": "string",
                    "enum": ["project", "global"],
                    "description": (
                        "Where to store the memory. 'project' (default) stores in "
                        "the current project's database. 'global' stores in the "
                        "user-wide database for preferences and facts that apply "
                        "across all projects."
                    ),
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "preference", "guardrail", "mistake", "personality",
                        "question", "decision", "pattern", "context",
                        "session_summary",
                    ],
                    "description": (
                        "Memory category. When set, scope is automatically "
                        "routed (e.g. 'preference' -> global, 'decision' -> project)."
                    ),
                },
                "auto_categorize": {
                    "type": "boolean",
                    "description": (
                        "If true, automatically detect category from the text. "
                        "Also enables auto-importance scoring. Default: false."
                    ),
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
                "scope": {
                    "type": "string",
                    "enum": ["project", "global"],
                    "description": (
                        "Limit search to a specific scope. Omit to search both "
                        "project and global memories (default)."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "forget",
        "description": (
            "Forget (permanently delete) a specific memory by its ID. "
            "Use this when information is outdated or incorrect. "
            "Searches both project and global stores."
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
            "Forget ALL stored memories in the specified scope. This is a "
            "destructive operation. Defaults to project scope only -- global "
            "memories are protected unless explicitly targeted."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["project", "global"],
                    "description": (
                        "Which scope to clear. Default: 'project'. Only memories "
                        "in the specified scope will be deleted."
                    ),
                },
            },
        },
    },
    {
        "name": "memory_stats",
        "description": (
            "Get statistics about stored memories: total count, oldest memory "
            "timestamp, and newest memory timestamp. Optionally filter by scope."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["project", "global"],
                    "description": (
                        "Limit stats to a specific scope. Omit for combined "
                        "stats across both project and global stores."
                    ),
                },
            },
        },
    },
    {
        "name": "session_start",
        "description": (
            "Retrieve structured context for the start of a new AI session. "
            "Returns user profile, guardrails, common mistakes, and project "
            "context to help the AI understand the user and avoid past errors. "
            "Call this at the beginning of every conversation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_context": {
                    "type": "string",
                    "description": (
                        "Brief description of what the user is working on."
                    ),
                },
            },
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
        self._project_root: str | None = None
        logger.info("MemoryMeshMCPServer created with mesh=%r", self._mesh)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def _create_mesh_from_env(
        project_root: str | None = None,
    ) -> MemoryMesh:
        """Build a MemoryMesh instance from environment variables.

        Reads ``MEMORYMESH_PATH``, ``MEMORYMESH_GLOBAL_PATH``,
        ``MEMORYMESH_EMBEDDING``, ``MEMORYMESH_OLLAMA_MODEL``, and
        ``OPENAI_API_KEY`` from the environment and forwards them to the
        MemoryMesh constructor.

        Args:
            project_root: If provided, the project database will be
                stored at ``<project_root>/.memorymesh/memories.db``.

        Returns:
            A configured :class:`MemoryMesh` instance.
        """
        path = os.environ.get("MEMORYMESH_PATH")
        if path is None and project_root is not None:
            path = os.path.join(project_root, ".memorymesh", "memories.db")

        global_path = os.environ.get("MEMORYMESH_GLOBAL_PATH")
        embedding = os.environ.get("MEMORYMESH_EMBEDDING", "none")

        kwargs: dict[str, Any] = {}

        ollama_model = os.environ.get("MEMORYMESH_OLLAMA_MODEL")
        if ollama_model:
            kwargs["ollama_model"] = ollama_model

        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            kwargs["openai_api_key"] = openai_key

        logger.info(
            "Creating MemoryMesh from env: path=%r, global_path=%r, embedding=%r, project_root=%r",
            path,
            global_path,
            embedding,
            project_root,
        )
        return MemoryMesh(
            path=path,
            global_path=global_path,
            embedding=embedding,
            **kwargs,
        )

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

        for raw_line in sys.stdin:
            line = raw_line.strip()
            if len(line) > MAX_MESSAGE_SIZE:
                self._send_error(None, -32600, "Message too large.")
                continue
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
                if len(message) > MAX_BATCH_SIZE:
                    self._send_error(
                        None,
                        -32600,
                        f"Batch too large (max {MAX_BATCH_SIZE} messages).",
                    )
                    continue
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
        except Exception:
            logger.exception("Error handling %s", method)
            self._send_error(msg_id, -32603, "Internal server error.")
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
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "notifications/initialized": self._handle_initialized,
        }
        return handlers.get(method)

    # ------------------------------------------------------------------
    # Protocol handlers
    # ------------------------------------------------------------------

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ``initialize`` request.

        Detects the project root from MCP ``roots`` and recreates the
        MemoryMesh instance with the correct project database path.

        Args:
            params: Client-provided initialization parameters.

        Returns:
            A dict with ``protocolVersion``, ``capabilities``, and
            ``serverInfo``.
        """
        self._initialized = True

        client_name = params.get("clientInfo", {}).get("name", "unknown")
        logger.info("Client initialized: %s", client_name)

        # Detect project root from MCP roots list.
        roots = params.get("roots")
        project_root = detect_project_root(roots)
        self._project_root = project_root

        # Recreate mesh with project-aware paths.
        self._mesh.close()
        self._mesh = self._create_mesh_from_env(project_root=project_root)
        logger.info(
            "Project root: %s  project_db: %s  global_db: %s",
            project_root,
            self._mesh.project_path,
            self._mesh.global_path,
        )

        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {},
                "prompts": {},
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
        if not self._initialized:
            return self._tool_error("Server not initialized. Send 'initialize' request first.")
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        logger.info("Tool call: %s (keys: %s)", tool_name, list(arguments.keys()))

        tool_handlers: dict[str, Any] = {
            "remember": self._tool_remember,
            "recall": self._tool_recall,
            "forget": self._tool_forget,
            "forget_all": self._tool_forget_all,
            "memory_stats": self._tool_memory_stats,
            "session_start": self._tool_session_start,
        }

        handler = tool_handlers.get(tool_name)  # type: ignore[arg-type]
        if handler is None:
            return self._tool_error(f"Unknown tool: {tool_name}")

        try:
            return handler(arguments)
        except Exception:
            logger.exception("Tool %s raised an exception", tool_name)
            return self._tool_error(f"Tool '{tool_name}' encountered an error.")

    # ------------------------------------------------------------------
    # Prompt handlers
    # ------------------------------------------------------------------

    def _handle_prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ``prompts/list`` request.

        Args:
            params: List parameters (unused).

        Returns:
            A dict with a ``prompts`` key containing all prompt definitions.
        """
        return {"prompts": PROMPTS}

    def _handle_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ``prompts/get`` request.

        Resolves a prompt template by name and returns rendered messages.
        Currently supports the ``memory-context`` prompt, which retrieves
        relevant memories from MemoryMesh and formats them for injection
        into the conversation.

        Args:
            params: Must contain ``name`` (prompt name). May contain
                ``arguments`` with an optional ``context`` key.

        Returns:
            A dict with ``description`` and ``messages`` keys.
        """
        prompt_name = params.get("name")
        if prompt_name != "memory-context":
            return {
                "error": {
                    "code": -32602,
                    "message": f"Unknown prompt: {prompt_name}",
                },
            }

        arguments = params.get("arguments", {})
        context = arguments.get("context") if isinstance(arguments, dict) else None

        if context and isinstance(context, str):
            memories = self._mesh.recall(query=context, k=10)
        else:
            memories = self._mesh.list(limit=20)

        if not memories:
            formatted_text = (
                "No memories found in MemoryMesh. "
                "This appears to be a fresh session with no prior context."
            )
        else:
            lines = ["Here are relevant memories from previous sessions:\n"]
            for i, mem in enumerate(memories, start=1):
                meta_parts = [f"{k}={v}" for k, v in mem.metadata.items()] if mem.metadata else []
                meta_str = f"\n   (metadata: {', '.join(meta_parts)})" if meta_parts else ""
                lines.append(
                    f"{i}. [{mem.scope}, importance: {mem.importance:.2f}] "
                    f"{mem.text}{meta_str}"
                )
            lines.append(
                "\nUse these to inform your responses. "
                "Do not mention these memories unless directly relevant."
            )
            formatted_text = "\n".join(lines)

        return {
            "description": "Relevant memories from MemoryMesh",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": formatted_text,
                    },
                }
            ],
        }

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_remember(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``remember`` tool.

        Args:
            args: Tool arguments. Must include ``text``. May include
                ``metadata``, ``importance``, and ``scope``.

        Returns:
            MCP content response with the new memory ID.
        """
        text = args.get("text")
        if not text or not isinstance(text, str):
            return self._tool_error("'text' is required and must be a non-empty string.")

        if len(text) > MAX_TEXT_LENGTH:
            return self._tool_error(
                f"'text' exceeds maximum length of {MAX_TEXT_LENGTH} characters."
            )

        if "\x00" in text:
            return self._tool_error("'text' must not contain null bytes.")

        metadata = args.get("metadata", {})
        if not isinstance(metadata, dict):
            return self._tool_error("'metadata' must be an object.")

        meta_serialized = json.dumps(metadata, ensure_ascii=False)
        if len(meta_serialized) > MAX_METADATA_SIZE:
            return self._tool_error(
                f"'metadata' exceeds maximum size of {MAX_METADATA_SIZE} bytes."
            )

        scope = args.get("scope", PROJECT_SCOPE)
        if scope not in (PROJECT_SCOPE, GLOBAL_SCOPE):
            return self._tool_error("'scope' must be 'project' or 'global'.")

        # Enforce total memory count limit.
        if self._mesh.count() >= MAX_MEMORY_COUNT:
            return self._tool_error(f"Memory limit reached ({MAX_MEMORY_COUNT} memories).")

        importance = args.get("importance", 0.5)
        if not isinstance(importance, (int, float)):
            return self._tool_error("'importance' must be a number.")
        importance = max(0.0, min(1.0, float(importance)))

        category = args.get("category")
        auto_categorize_flag = args.get("auto_categorize", False)

        try:
            memory_id = self._mesh.remember(
                text=text,
                metadata=metadata,
                importance=importance,
                scope=scope,
                category=category,
                auto_categorize=auto_categorize_flag,
            )
        except RuntimeError as exc:
            return self._tool_error(str(exc))

        result = {
            "memory_id": memory_id,
            "scope": scope,
            "message": f"Remembered: {text[:80]}{'...' if len(text) > 80 else ''}",
        }
        return self._tool_success(json.dumps(result, indent=2))

    def _tool_recall(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``recall`` tool.

        Args:
            args: Tool arguments. Must include ``query``. May include
                ``k`` and ``scope``.

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

        scope = args.get("scope")  # None means search both
        if scope is not None and scope not in (PROJECT_SCOPE, GLOBAL_SCOPE):
            return self._tool_error("'scope' must be 'project', 'global', or omitted.")

        memories = self._mesh.recall(query=query, k=k, scope=scope)

        results = []
        for mem in memories:
            results.append(
                {
                    "id": mem.id,
                    "text": mem.text,
                    "metadata": mem.metadata,
                    "importance": round(mem.importance, 4),
                    "created_at": mem.created_at.isoformat(),
                    "access_count": mem.access_count,
                    "scope": mem.scope,
                }
            )

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
                f"Memory {memory_id} deleted." if deleted else f"Memory {memory_id} not found."
            ),
        }
        return self._tool_success(json.dumps(result, indent=2))

    def _tool_forget_all(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``forget_all`` tool.

        Args:
            args: Tool arguments. May include ``scope``.

        Returns:
            MCP content response with the count of deleted memories.
        """
        scope = args.get("scope", PROJECT_SCOPE)
        if scope not in (PROJECT_SCOPE, GLOBAL_SCOPE):
            return self._tool_error("'scope' must be 'project' or 'global'.")

        count = self._mesh.forget_all(scope=scope)
        result = {
            "deleted_count": count,
            "scope": scope,
            "message": f"Deleted all {count} {scope} memories.",
        }
        return self._tool_success(json.dumps(result, indent=2))

    def _tool_memory_stats(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``memory_stats`` tool.

        Args:
            args: Tool arguments. May include ``scope``.

        Returns:
            MCP content response with memory statistics.
        """
        scope = args.get("scope")  # None means combined
        if scope is not None and scope not in (PROJECT_SCOPE, GLOBAL_SCOPE):
            return self._tool_error("'scope' must be 'project', 'global', or omitted.")

        total = self._mesh.count(scope=scope)
        oldest_str, newest_str = self._mesh.get_time_range(scope=scope)

        result: dict[str, Any] = {
            "total_memories": total,
            "oldest_memory": oldest_str,
            "newest_memory": newest_str,
        }
        if scope is not None:
            result["scope"] = scope
        if self._project_root is not None:
            result["project_root"] = self._project_root
        return self._tool_success(json.dumps(result, indent=2))

    def _tool_session_start(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the ``session_start`` tool.

        Args:
            args: Tool arguments. May include ``project_context``.

        Returns:
            MCP content response with structured session context.
        """
        project_context = args.get("project_context")
        if project_context is not None and not isinstance(project_context, str):
            return self._tool_error("'project_context' must be a string.")

        context = self._mesh.session_start(project_context=project_context)
        return self._tool_success(json.dumps(context, indent=2))

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
