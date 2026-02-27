"""Tests for the MemoryMesh MCP server.

Covers protocol handlers, tool validation & security, tool happy paths,
dispatch & guards, response helpers, factory methods, and edge cases.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from memorymesh import __version__
from memorymesh.core import MemoryMesh
from memorymesh.mcp_server import (
    MAX_MEMORY_COUNT,
    MAX_METADATA_SIZE,
    MAX_TEXT_LENGTH,
    PROMPTS,
    TOOLS,
    MemoryMeshMCPServer,
    main,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _call_tool(server: MemoryMeshMCPServer, name: str, args: dict[str, Any] | None = None) -> dict:
    """Shorthand for calling a tool through _handle_tools_call."""
    return server._handle_tools_call({"name": name, "arguments": args or {}})


def _get_result_data(response: dict[str, Any]) -> dict[str, Any]:
    """Parse the JSON text payload from a successful MCP tool response."""
    text = response["content"][0]["text"]
    return json.loads(text)


def _is_error(response: dict[str, Any]) -> bool:
    """Check whether the response has the isError flag."""
    return response.get("isError", False) is True


def _get_error_message(response: dict[str, Any]) -> str:
    """Extract the human-readable error message from an error response."""
    data = json.loads(response["content"][0]["text"])
    return data["error"]


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mesh(tmp_path) -> Generator[MemoryMesh, None, None]:
    """A real MemoryMesh with project + global stores, no embeddings."""
    m = MemoryMesh(
        path=tmp_path / "project.db",
        global_path=tmp_path / "global.db",
        embedding="none",
    )
    yield m
    m.close()


@pytest.fixture
def server(mesh: MemoryMesh) -> MemoryMeshMCPServer:
    """An initialized MCP server with an injected mesh."""
    s = MemoryMeshMCPServer(mesh=mesh)
    s._initialized = True
    s._client_name = "test-client"
    return s


@pytest.fixture
def uninitialized_server() -> MemoryMeshMCPServer:
    """A bare MCP server with no mesh and not initialized."""
    return MemoryMeshMCPServer()


# ==================================================================
# Priority 1 — Constants & Constructor
# ==================================================================


class TestConstants:
    """Verify module-level constants are sane."""

    def test_tool_count(self) -> None:
        assert len(TOOLS) == 10

    def test_prompt_count(self) -> None:
        assert len(PROMPTS) == 1

    def test_server_name(self) -> None:
        from memorymesh.mcp_server import SERVER_INFO

        assert SERVER_INFO["name"] == "memorymesh"

    def test_positive_limits(self) -> None:
        assert MAX_TEXT_LENGTH > 0
        assert MAX_METADATA_SIZE > 0
        assert MAX_MEMORY_COUNT > 0


class TestServerConstructor:
    """Verify constructor behaviour."""

    def test_with_mesh(self, mesh: MemoryMesh) -> None:
        s = MemoryMeshMCPServer(mesh=mesh)
        assert s._mesh is mesh
        assert s._initialized is False

    def test_without_mesh(self) -> None:
        s = MemoryMeshMCPServer()
        assert s._mesh is None
        assert s._initialized is False
        assert s._client_name == "unknown"


# ==================================================================
# Priority 2 — Response Helpers
# ==================================================================


class TestResponseHelpers:
    """Verify the _tool_success and _tool_error envelope formats."""

    def test_tool_success_format(self) -> None:
        resp = MemoryMeshMCPServer._tool_success("hello")
        assert resp["content"][0]["type"] == "text"
        assert resp["content"][0]["text"] == "hello"
        assert "isError" not in resp

    def test_tool_error_format(self) -> None:
        resp = MemoryMeshMCPServer._tool_error("bad input")
        assert resp["isError"] is True
        data = json.loads(resp["content"][0]["text"])
        assert data["error"] == "bad input"

    def test_send_result_writes_jsonrpc(self, server: MemoryMeshMCPServer) -> None:
        """_send_result writes valid JSON-RPC to stdout."""
        import io

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            server._send_result(42, {"ok": True})
        msg = json.loads(buf.getvalue().strip())
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 42
        assert msg["result"]["ok"] is True

    def test_send_error_writes_jsonrpc(self, server: MemoryMeshMCPServer) -> None:
        """_send_error writes valid JSON-RPC error to stdout."""
        import io

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            server._send_error(7, -32600, "bad request")
        msg = json.loads(buf.getvalue().strip())
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 7
        assert msg["error"]["code"] == -32600
        assert msg["error"]["message"] == "bad request"


# ==================================================================
# Priority 3 — Tool Validation & Security (highest risk)
# ==================================================================


class TestToolRememberValidation:
    """Boundary checks for the remember tool."""

    def test_missing_text(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {})
        assert _is_error(resp)
        assert "text" in _get_error_message(resp).lower()

    def test_empty_text(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": ""})
        assert _is_error(resp)

    def test_non_string_text(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": 123})
        assert _is_error(resp)

    def test_max_length_text(self, server: MemoryMeshMCPServer) -> None:
        long_text = "a" * (MAX_TEXT_LENGTH + 1)
        resp = _call_tool(server, "remember", {"text": long_text})
        assert _is_error(resp)
        assert "maximum length" in _get_error_message(resp).lower()

    def test_null_bytes_rejected(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "hello\x00world"})
        assert _is_error(resp)
        assert "null" in _get_error_message(resp).lower()

    def test_bad_metadata_type(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "ok", "metadata": "not-a-dict"})
        assert _is_error(resp)
        assert "metadata" in _get_error_message(resp).lower()

    def test_oversized_metadata(self, server: MemoryMeshMCPServer) -> None:
        big_meta = {"key": "x" * MAX_METADATA_SIZE}
        resp = _call_tool(server, "remember", {"text": "ok", "metadata": big_meta})
        assert _is_error(resp)
        assert "metadata" in _get_error_message(resp).lower()

    def test_invalid_scope(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "ok", "scope": "invalid"})
        assert _is_error(resp)
        assert "scope" in _get_error_message(resp).lower()

    def test_bad_importance_type(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "ok", "importance": "high"})
        assert _is_error(resp)
        assert "importance" in _get_error_message(resp).lower()

    def test_importance_clamped_high(self, server: MemoryMeshMCPServer) -> None:
        """Importance > 1 should be clamped, not rejected."""
        resp = _call_tool(server, "remember", {"text": "clamped high", "importance": 5.0})
        assert not _is_error(resp)

    def test_importance_clamped_low(self, server: MemoryMeshMCPServer) -> None:
        """Importance < 0 should be clamped, not rejected."""
        resp = _call_tool(server, "remember", {"text": "clamped low", "importance": -1.0})
        assert not _is_error(resp)

    def test_exact_max_length_accepted(self, server: MemoryMeshMCPServer) -> None:
        """Text at exactly MAX_TEXT_LENGTH should be accepted."""
        exact_text = "a" * MAX_TEXT_LENGTH
        resp = _call_tool(server, "remember", {"text": exact_text})
        assert not _is_error(resp)


class TestToolRecallValidation:
    """Boundary checks for the recall tool."""

    def test_missing_query(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "recall", {})
        assert _is_error(resp)
        assert "query" in _get_error_message(resp).lower()

    def test_empty_query(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "recall", {"query": ""})
        assert _is_error(resp)

    def test_non_string_query(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "recall", {"query": 42})
        assert _is_error(resp)

    def test_bad_k_type(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "recall", {"query": "test", "k": "five"})
        assert _is_error(resp)
        assert "k" in _get_error_message(resp).lower()

    def test_k_zero(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "recall", {"query": "test", "k": 0})
        assert _is_error(resp)

    def test_k_clamped_to_100(self, server: MemoryMeshMCPServer) -> None:
        """k > 100 should be clamped, not rejected."""
        resp = _call_tool(server, "recall", {"query": "test", "k": 500})
        assert not _is_error(resp)

    def test_invalid_scope(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "recall", {"query": "test", "scope": "secret"})
        assert _is_error(resp)

    def test_bad_min_importance(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "recall", {"query": "test", "min_importance": "high"})
        assert _is_error(resp)


class TestToolForget:
    """Validation and behaviour for the forget tool."""

    def test_missing_memory_id(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "forget", {})
        assert _is_error(resp)

    def test_non_string_memory_id(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "forget", {"memory_id": 123})
        assert _is_error(resp)

    def test_existing_memory(self, server: MemoryMeshMCPServer) -> None:
        # First remember something
        resp = _call_tool(server, "remember", {"text": "to forget"})
        mid = _get_result_data(resp)["memory_id"]

        resp = _call_tool(server, "forget", {"memory_id": mid})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["deleted"] is True

    def test_nonexistent_memory(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "forget", {"memory_id": "nonexistent-id"})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["deleted"] is False


class TestToolForgetAll:
    """Validation and behaviour for the forget_all tool."""

    def test_defaults_to_project_scope(self, server: MemoryMeshMCPServer) -> None:
        _call_tool(server, "remember", {"text": "project mem", "scope": "project"})
        resp = _call_tool(server, "forget_all", {})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["scope"] == "project"

    def test_project_scope(self, server: MemoryMeshMCPServer) -> None:
        _call_tool(server, "remember", {"text": "p1", "scope": "project"})
        resp = _call_tool(server, "forget_all", {"scope": "project"})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["scope"] == "project"

    def test_global_scope(self, server: MemoryMeshMCPServer) -> None:
        _call_tool(server, "remember", {"text": "g1", "scope": "global"})
        resp = _call_tool(server, "forget_all", {"scope": "global"})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["scope"] == "global"

    def test_invalid_scope(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "forget_all", {"scope": "invalid"})
        assert _is_error(resp)


class TestToolUpdateMemoryValidation:
    """Validation for the update_memory tool."""

    def test_missing_memory_id(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "update_memory", {})
        assert _is_error(resp)

    def test_empty_memory_id(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "update_memory", {"memory_id": ""})
        assert _is_error(resp)

    def test_nonexistent_memory_id(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "update_memory", {"memory_id": "nonexistent"})
        assert _is_error(resp)
        assert "not found" in _get_error_message(resp).lower()

    def test_update_text(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "original"})
        mid = _get_result_data(resp)["memory_id"]

        resp = _call_tool(server, "update_memory", {"memory_id": mid, "text": "updated"})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["memory_id"] == mid
        assert "updated" in data["message"].lower()

    def test_update_importance(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "test imp"})
        mid = _get_result_data(resp)["memory_id"]

        resp = _call_tool(server, "update_memory", {"memory_id": mid, "importance": 0.9})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["importance"] == 0.9

    def test_update_scope(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "scope test", "scope": "project"})
        mid = _get_result_data(resp)["memory_id"]

        resp = _call_tool(server, "update_memory", {"memory_id": mid, "scope": "global"})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["scope"] == "global"

    def test_update_metadata(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "meta test"})
        mid = _get_result_data(resp)["memory_id"]

        resp = _call_tool(
            server, "update_memory", {"memory_id": mid, "metadata": {"tag": "updated"}}
        )
        assert not _is_error(resp)

    def test_empty_text_rejected(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "nonempty"})
        mid = _get_result_data(resp)["memory_id"]

        resp = _call_tool(server, "update_memory", {"memory_id": mid, "text": ""})
        assert _is_error(resp)

    def test_oversized_text(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "ok"})
        mid = _get_result_data(resp)["memory_id"]

        resp = _call_tool(
            server, "update_memory", {"memory_id": mid, "text": "a" * (MAX_TEXT_LENGTH + 1)}
        )
        assert _is_error(resp)

    def test_oversized_metadata(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "ok"})
        mid = _get_result_data(resp)["memory_id"]

        resp = _call_tool(
            server,
            "update_memory",
            {"memory_id": mid, "metadata": {"big": "x" * MAX_METADATA_SIZE}},
        )
        assert _is_error(resp)


# ==================================================================
# Priority 4 — Tool Happy Paths
# ==================================================================


class TestToolRememberHappyPath:
    """Successful remember scenarios."""

    def test_minimal_params(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "hello world"})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert "memory_id" in data
        assert data["scope"] == "project"
        assert "hello world" in data["message"]

    def test_all_params(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(
            server,
            "remember",
            {
                "text": "all params test",
                "metadata": {"tag": "full"},
                "importance": 0.8,
                "scope": "global",
                "category": "preference",
            },
        )
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["memory_id"]

    def test_auto_populates_source_metadata(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "provenance test"})
        data = _get_result_data(resp)
        mid = data["memory_id"]
        # Verify metadata was set on the actual memory
        mem = server._mesh.get(mid)
        assert mem is not None
        assert mem.metadata.get("source") == "mcp"
        assert mem.metadata.get("tool") == "test-client"

    def test_preserves_existing_source(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(
            server,
            "remember",
            {"text": "custom source", "metadata": {"source": "user"}},
        )
        data = _get_result_data(resp)
        mem = server._mesh.get(data["memory_id"])
        assert mem is not None
        assert mem.metadata["source"] == "user"

    def test_truncated_message(self, server: MemoryMeshMCPServer) -> None:
        """Messages longer than 80 chars should be truncated in the response."""
        long_text = "a" * 100
        resp = _call_tool(server, "remember", {"text": long_text})
        data = _get_result_data(resp)
        assert "..." in data["message"]

    def test_default_scope_is_project(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "default scope"})
        data = _get_result_data(resp)
        assert data["scope"] == "project"

    def test_explicit_global_scope(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "global test", "scope": "global"})
        data = _get_result_data(resp)
        assert data["scope"] == "global"

    def test_pin_flag(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "remember", {"text": "pinned mem", "pin": True})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        mem = server._mesh.get(data["memory_id"])
        assert mem is not None
        assert mem.importance == 1.0


class TestToolRecallHappyPath:
    """Successful recall scenarios."""

    def test_returns_matching_memories(self, server: MemoryMeshMCPServer) -> None:
        _call_tool(server, "remember", {"text": "The user prefers dark mode"})
        resp = _call_tool(server, "recall", {"query": "dark mode"})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["count"] >= 1
        mem = data["memories"][0]
        assert "id" in mem
        assert "text" in mem
        assert "importance" in mem
        assert "scope" in mem
        assert "access_count" in mem
        assert "created_at" in mem

    def test_default_k(self, server: MemoryMeshMCPServer) -> None:
        for i in range(10):
            _call_tool(server, "remember", {"text": f"keyword memory {i}"})
        resp = _call_tool(server, "recall", {"query": "keyword memory"})
        data = _get_result_data(resp)
        assert data["count"] <= 5  # default k=5

    def test_scope_filter(self, server: MemoryMeshMCPServer) -> None:
        _call_tool(server, "remember", {"text": "project fact", "scope": "project"})
        _call_tool(server, "remember", {"text": "global fact", "scope": "global"})
        resp = _call_tool(server, "recall", {"query": "fact", "scope": "project"})
        data = _get_result_data(resp)
        for mem in data["memories"]:
            assert mem["scope"] == "project"

    def test_empty_result(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "recall", {"query": "xyznonexistent"})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["count"] == 0

    def test_min_importance_filter(self, server: MemoryMeshMCPServer) -> None:
        _call_tool(server, "remember", {"text": "low imp recall", "importance": 0.1})
        _call_tool(server, "remember", {"text": "high imp recall", "importance": 0.9})
        resp = _call_tool(server, "recall", {"query": "imp recall", "min_importance": 0.5})
        data = _get_result_data(resp)
        for mem in data["memories"]:
            assert mem["importance"] >= 0.5


class TestToolMemoryStats:
    """Tests for the memory_stats tool."""

    def test_empty_store(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "memory_stats", {})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["total_memories"] == 0

    def test_with_memories(self, server: MemoryMeshMCPServer) -> None:
        _call_tool(server, "remember", {"text": "stat mem 1"})
        _call_tool(server, "remember", {"text": "stat mem 2"})
        resp = _call_tool(server, "memory_stats", {})
        data = _get_result_data(resp)
        assert data["total_memories"] >= 2

    def test_scope_filter(self, server: MemoryMeshMCPServer) -> None:
        _call_tool(server, "remember", {"text": "proj stat", "scope": "project"})
        resp = _call_tool(server, "memory_stats", {"scope": "project"})
        data = _get_result_data(resp)
        assert data["scope"] == "project"
        assert data["total_memories"] >= 1

    def test_invalid_scope(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "memory_stats", {"scope": "invalid"})
        assert _is_error(resp)


class TestToolSessionStart:
    """Tests for the session_start tool."""

    def test_returns_context(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "session_start", {})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        # session_start returns structured context with store_health
        assert "store_health" in data
        assert "user_profile" in data

    def test_store_health_with_project(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "session_start", {})
        data = _get_result_data(resp)
        assert data["store_health"]["global_store"] == "ok"
        assert data["store_health"]["project_store"] == "ok"

    def test_store_health_without_project(self, tmp_path) -> None:
        """When no project store is configured, report not_configured."""
        m = MemoryMesh(
            global_path=tmp_path / "global.db",
            embedding="none",
        )
        s = MemoryMeshMCPServer(mesh=m)
        s._initialized = True
        s._client_name = "test"
        resp = _call_tool(s, "session_start", {})
        data = _get_result_data(resp)
        assert data["store_health"]["project_store"] == "not_configured"
        m.close()

    def test_project_context_forwarded(self, server: MemoryMeshMCPServer) -> None:
        """project_context param should be forwarded to mesh.session_start."""
        resp = _call_tool(server, "session_start", {"project_context": "working on auth"})
        assert not _is_error(resp)

    def test_bad_project_context_type(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "session_start", {"project_context": 123})
        assert _is_error(resp)


class TestToolReviewMemories:
    """Tests for the review_memories tool."""

    def test_response_structure(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "review_memories", {})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert "quality_score" in data
        assert "total_reviewed" in data
        assert "issue_count" in data
        assert "issues" in data

    def test_scope_filter(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "review_memories", {"scope": "project"})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert data["scanned_scope"] == "project"

    def test_invalid_scope(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "review_memories", {"scope": "invalid"})
        assert _is_error(resp)


class TestToolStatus:
    """Tests for the status tool."""

    def test_version_matches(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "status", {})
        data = _get_result_data(resp)
        assert data["version"] == __version__

    def test_project_configured(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "status", {})
        data = _get_result_data(resp)
        assert data["project_store"]["status"] == "ok"
        assert "path" in data["project_store"]

    def test_project_not_configured(self, tmp_path) -> None:
        m = MemoryMesh(
            global_path=tmp_path / "global.db",
            embedding="none",
        )
        s = MemoryMeshMCPServer(mesh=m)
        s._initialized = True
        resp = _call_tool(s, "status", {})
        data = _get_result_data(resp)
        assert data["project_store"]["status"] == "not_configured"
        m.close()

    def test_global_store_ok(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "status", {})
        data = _get_result_data(resp)
        assert data["global_store"]["status"] == "ok"


class TestToolConfigureProject:
    """Tests for the configure_project tool."""

    def test_valid_path(self, server: MemoryMeshMCPServer, tmp_path) -> None:
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        resp = _call_tool(server, "configure_project", {"path": str(project_dir)})
        assert not _is_error(resp)
        data = _get_result_data(resp)
        assert "project_root" in data
        assert "project_db" in data

    def test_missing_path(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "configure_project", {})
        assert _is_error(resp)

    def test_empty_path(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "configure_project", {"path": ""})
        assert _is_error(resp)

    def test_nonexistent_dir(self, server: MemoryMeshMCPServer) -> None:
        resp = _call_tool(server, "configure_project", {"path": "/nonexistent/path/xyz"})
        assert _is_error(resp)
        assert "does not exist" in _get_error_message(resp).lower()

    def test_tilde_expansion(self, server: MemoryMeshMCPServer, tmp_path) -> None:
        """Paths with ~ should be expanded."""
        # We can't easily test real ~ expansion, but verify the code path doesn't crash
        resp = _call_tool(server, "configure_project", {"path": "~/nonexistent_xyz_test"})
        # It'll be an error because the dir doesn't exist, but tilde was expanded
        assert _is_error(resp)


# ==================================================================
# Priority 5 — Protocol Handlers
# ==================================================================


class TestHandleInitialize:
    """Tests for the initialize protocol handler."""

    def test_protocol_version(self, uninitialized_server: MemoryMeshMCPServer, tmp_path) -> None:
        with patch.dict(os.environ, {"MEMORYMESH_PATH": str(tmp_path / "p.db")}):
            result = uninitialized_server._handle_initialize({})
        assert result["protocolVersion"] == "2024-11-05"

    def test_capabilities(self, uninitialized_server: MemoryMeshMCPServer, tmp_path) -> None:
        with patch.dict(os.environ, {"MEMORYMESH_PATH": str(tmp_path / "p.db")}):
            result = uninitialized_server._handle_initialize({})
        assert "tools" in result["capabilities"]
        assert "prompts" in result["capabilities"]

    def test_server_info(self, uninitialized_server: MemoryMeshMCPServer, tmp_path) -> None:
        with patch.dict(os.environ, {"MEMORYMESH_PATH": str(tmp_path / "p.db")}):
            result = uninitialized_server._handle_initialize({})
        assert result["serverInfo"]["name"] == "memorymesh"
        assert result["serverInfo"]["version"] == __version__

    def test_sets_initialized_flag(
        self, uninitialized_server: MemoryMeshMCPServer, tmp_path
    ) -> None:
        assert uninitialized_server._initialized is False
        with patch.dict(os.environ, {"MEMORYMESH_PATH": str(tmp_path / "p.db")}):
            uninitialized_server._handle_initialize({})
        assert uninitialized_server._initialized is True

    def test_extracts_client_name(
        self, uninitialized_server: MemoryMeshMCPServer, tmp_path
    ) -> None:
        with patch.dict(os.environ, {"MEMORYMESH_PATH": str(tmp_path / "p.db")}):
            uninitialized_server._handle_initialize({"clientInfo": {"name": "cursor"}})
        assert uninitialized_server._client_name == "cursor"

    def test_default_client_name(self, uninitialized_server: MemoryMeshMCPServer, tmp_path) -> None:
        with patch.dict(os.environ, {"MEMORYMESH_PATH": str(tmp_path / "p.db")}):
            uninitialized_server._handle_initialize({})
        assert uninitialized_server._client_name == "unknown"

    def test_project_root_from_roots(
        self, uninitialized_server: MemoryMeshMCPServer, tmp_path
    ) -> None:
        """When roots are provided, project root should be detected from them."""
        project_dir = str(tmp_path / "myproject")
        # Mock detect_project_root to isolate from URI parsing (which
        # differs across platforms) and test that _handle_initialize
        # forwards roots and stores the result.
        with (
            patch(
                "memorymesh.mcp_server.detect_project_root",
                return_value=project_dir,
            ) as mock_detect,
            patch.dict(os.environ, {"MEMORYMESH_EMBEDDING": "none"}, clear=False),
        ):
            roots = [{"uri": f"file://{project_dir}"}]
            uninitialized_server._handle_initialize({"roots": roots})
            mock_detect.assert_called_once()
            # Verify roots were forwarded to detect_project_root.
            assert mock_detect.call_args[0][0] == roots
        assert uninitialized_server._project_root == project_dir


class TestHandleInitialized:
    """Tests for the initialized notification handler."""

    def test_returns_empty_dict(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_initialized({})
        assert result == {}


class TestHandlePing:
    """Tests for the ping handler."""

    def test_returns_empty_dict(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_ping({})
        assert result == {}


class TestHandleToolsList:
    """Tests for the tools/list handler."""

    def test_returns_all_tools(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_tools_list({})
        assert len(result["tools"]) == 10

    def test_expected_tool_names(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_tools_list({})
        names = {t["name"] for t in result["tools"]}
        expected = {
            "remember",
            "recall",
            "forget",
            "forget_all",
            "memory_stats",
            "session_start",
            "update_memory",
            "review_memories",
            "status",
            "configure_project",
        }
        assert names == expected

    def test_tools_have_input_schema(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_tools_list({})
        for tool in result["tools"]:
            assert "inputSchema" in tool, f"Tool {tool['name']} missing inputSchema"


class TestHandlePromptsList:
    """Tests for the prompts/list handler."""

    def test_returns_one_prompt(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_prompts_list({})
        assert len(result["prompts"]) == 1

    def test_prompt_named_memory_context(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_prompts_list({})
        assert result["prompts"][0]["name"] == "memory-context"


class TestHandlePromptsGet:
    """Tests for the prompts/get handler."""

    def test_unknown_prompt_error(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_prompts_get({"name": "nonexistent"})
        assert "error" in result
        assert result["error"]["code"] == -32602

    def test_no_mesh_error(self, uninitialized_server: MemoryMeshMCPServer) -> None:
        result = uninitialized_server._handle_prompts_get({"name": "memory-context"})
        assert "error" in result
        assert result["error"]["code"] == -32603

    def test_with_context(self, server: MemoryMeshMCPServer) -> None:
        _call_tool(server, "remember", {"text": "user likes dark mode"})
        result = server._handle_prompts_get(
            {"name": "memory-context", "arguments": {"context": "theme"}}
        )
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"

    def test_without_context(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_prompts_get({"name": "memory-context"})
        assert "messages" in result

    def test_empty_store(self, server: MemoryMeshMCPServer) -> None:
        result = server._handle_prompts_get({"name": "memory-context"})
        text = result["messages"][0]["content"]["text"]
        assert "no memories" in text.lower()


# ==================================================================
# Priority 6 — Dispatch & Guards
# ==================================================================


class TestHandleMessage:
    """Tests for the top-level message dispatcher."""

    def test_known_method(self, server: MemoryMeshMCPServer) -> None:
        """A known method with an id should produce a stdout response."""
        import io

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            server._handle_message({"jsonrpc": "2.0", "id": 1, "method": "ping"})
        msg = json.loads(buf.getvalue().strip())
        assert msg["id"] == 1
        assert "result" in msg

    def test_unknown_method_with_id(self, server: MemoryMeshMCPServer) -> None:
        """An unknown method with an id should produce an error response."""
        import io

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            server._handle_message({"jsonrpc": "2.0", "id": 2, "method": "unknown/method"})
        msg = json.loads(buf.getvalue().strip())
        assert msg["error"]["code"] == -32601

    def test_unknown_method_without_id(self, server: MemoryMeshMCPServer) -> None:
        """An unknown notification (no id) should be silently ignored."""
        import io

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            server._handle_message({"jsonrpc": "2.0", "method": "unknown/notification"})
        assert buf.getvalue() == ""

    def test_missing_method(self, server: MemoryMeshMCPServer) -> None:
        import io

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            server._handle_message({"jsonrpc": "2.0", "id": 3})
        msg = json.loads(buf.getvalue().strip())
        assert msg["error"]["code"] == -32600

    def test_non_dict_message(self, server: MemoryMeshMCPServer) -> None:
        import io

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            server._handle_message("not a dict")  # type: ignore[arg-type]
        msg = json.loads(buf.getvalue().strip())
        assert msg["error"]["code"] == -32600

    def test_handler_exception(self, server: MemoryMeshMCPServer) -> None:
        """If a handler raises, return internal error."""
        import io

        buf = io.StringIO()
        with (
            patch.object(server, "_handle_ping", side_effect=RuntimeError("boom")),
            patch("sys.stdout", buf),
        ):
            server._handle_message({"jsonrpc": "2.0", "id": 4, "method": "ping"})
        msg = json.loads(buf.getvalue().strip())
        assert msg["error"]["code"] == -32603


class TestGetHandler:
    """Tests for method-to-handler lookup."""

    def test_all_methods_have_handlers(self, server: MemoryMeshMCPServer) -> None:
        methods = [
            "initialize",
            "initialized",
            "ping",
            "tools/list",
            "tools/call",
            "prompts/list",
            "prompts/get",
            "notifications/initialized",
        ]
        for method in methods:
            assert server._get_handler(method) is not None, f"No handler for {method}"

    def test_unknown_returns_none(self, server: MemoryMeshMCPServer) -> None:
        assert server._get_handler("nonexistent/method") is None

    def test_initialized_alias(self, server: MemoryMeshMCPServer) -> None:
        """notifications/initialized and initialized use the same handler."""
        h1 = server._get_handler("initialized")
        h2 = server._get_handler("notifications/initialized")
        assert h1 is not None
        assert h2 is not None
        # Both should be the same bound method
        assert h1.__func__ == h2.__func__


class TestToolsCallGuards:
    """Tests for pre-flight checks in _handle_tools_call."""

    def test_before_initialize(self, uninitialized_server: MemoryMeshMCPServer) -> None:
        resp = uninitialized_server._handle_tools_call({"name": "status", "arguments": {}})
        assert _is_error(resp)
        assert "not initialized" in _get_error_message(resp).lower()

    def test_no_mesh(self) -> None:
        s = MemoryMeshMCPServer()
        s._initialized = True
        s._mesh = None
        resp = s._handle_tools_call({"name": "status", "arguments": {}})
        assert _is_error(resp)
        assert "not available" in _get_error_message(resp).lower()

    def test_unknown_tool(self, server: MemoryMeshMCPServer) -> None:
        resp = server._handle_tools_call({"name": "nonexistent_tool", "arguments": {}})
        assert _is_error(resp)
        assert "unknown tool" in _get_error_message(resp).lower()


# ==================================================================
# Priority 7 — Factory & main()
# ==================================================================


class TestCreateMeshFromEnv:
    """Tests for _create_mesh_from_env factory method."""

    def test_default_embedding(self, tmp_path) -> None:
        env = {
            "MEMORYMESH_PATH": str(tmp_path / "p.db"),
            "MEMORYMESH_EMBEDDING": "none",
        }
        with patch.dict(os.environ, env, clear=False):
            mesh = MemoryMeshMCPServer._create_mesh_from_env()
        assert mesh is not None
        mesh.close()

    def test_memorymesh_path_env(self, tmp_path) -> None:
        db_path = str(tmp_path / "env_test.db")
        env = {"MEMORYMESH_PATH": db_path, "MEMORYMESH_EMBEDDING": "none"}
        with patch.dict(os.environ, env, clear=False):
            mesh = MemoryMeshMCPServer._create_mesh_from_env()
        assert mesh.project_path == db_path
        mesh.close()

    def test_project_root_param(self, tmp_path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        env = {"MEMORYMESH_EMBEDDING": "none"}
        # Remove MEMORYMESH_PATH from env so project_root is used
        clean_env = {k: v for k, v in os.environ.items() if k != "MEMORYMESH_PATH"}
        clean_env.update(env)
        with patch.dict(os.environ, clean_env, clear=True):
            mesh = MemoryMeshMCPServer._create_mesh_from_env(project_root=str(project_dir))
        expected = os.path.join(str(project_dir), ".memorymesh", "memories.db")
        assert mesh.project_path == expected
        mesh.close()

    def test_path_overrides_root(self, tmp_path) -> None:
        """MEMORYMESH_PATH should take precedence over project_root."""
        explicit_path = str(tmp_path / "explicit.db")
        env = {
            "MEMORYMESH_PATH": explicit_path,
            "MEMORYMESH_EMBEDDING": "none",
        }
        with patch.dict(os.environ, env, clear=False):
            mesh = MemoryMeshMCPServer._create_mesh_from_env(project_root=str(tmp_path))
        assert mesh.project_path == explicit_path
        mesh.close()

    def test_global_path_env(self, tmp_path) -> None:
        gpath = str(tmp_path / "custom_global.db")
        env = {
            "MEMORYMESH_GLOBAL_PATH": gpath,
            "MEMORYMESH_EMBEDDING": "none",
            "MEMORYMESH_PATH": str(tmp_path / "p.db"),
        }
        with patch.dict(os.environ, env, clear=False):
            mesh = MemoryMeshMCPServer._create_mesh_from_env()
        assert mesh.global_path == gpath
        mesh.close()

    def test_ollama_model_env(self, tmp_path) -> None:
        """MEMORYMESH_OLLAMA_MODEL should be forwarded."""
        env = {
            "MEMORYMESH_EMBEDDING": "none",
            "MEMORYMESH_OLLAMA_MODEL": "nomic-embed-text",
            "MEMORYMESH_PATH": str(tmp_path / "p.db"),
        }
        with patch.dict(os.environ, env, clear=False):
            mesh = MemoryMeshMCPServer._create_mesh_from_env()
        # Should not raise -- the model param is only used when embedding=ollama
        mesh.close()

    def test_weights_from_env(self, tmp_path) -> None:
        env = {
            "MEMORYMESH_EMBEDDING": "none",
            "MEMORYMESH_PATH": str(tmp_path / "p.db"),
            "MEMORYMESH_WEIGHT_SIMILARITY": "0.8",
            "MEMORYMESH_WEIGHT_RECENCY": "0.1",
        }
        with patch.dict(os.environ, env, clear=False):
            mesh = MemoryMeshMCPServer._create_mesh_from_env()
        # Should not raise
        mesh.close()


class TestMain:
    """Tests for the main() entry point."""

    def test_debug_logging(self, tmp_path) -> None:
        """MEMORYMESH_DEBUG should set DEBUG level."""
        env = {
            "MEMORYMESH_DEBUG": "1",
            "MEMORYMESH_EMBEDDING": "none",
            "MEMORYMESH_PATH": str(tmp_path / "p.db"),
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("memorymesh.mcp_server.MemoryMeshMCPServer") as mock_server_cls,
        ):
            mock_server_cls.return_value.run.side_effect = KeyboardInterrupt
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_keyboard_interrupt(self, tmp_path) -> None:
        env = {
            "MEMORYMESH_EMBEDDING": "none",
            "MEMORYMESH_PATH": str(tmp_path / "p.db"),
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("memorymesh.mcp_server.MemoryMeshMCPServer") as mock_server_cls,
        ):
            mock_server_cls.return_value.run.side_effect = KeyboardInterrupt
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


# ==================================================================
# Priority 8 — Edge Cases
# ==================================================================


class TestToolRememberLimits:
    """Edge cases for memory count limits."""

    def test_memory_count_limit(self, server: MemoryMeshMCPServer) -> None:
        """When count >= MAX_MEMORY_COUNT, remember should be rejected."""
        with patch.object(server._mesh, "count", return_value=MAX_MEMORY_COUNT):
            resp = _call_tool(server, "remember", {"text": "over limit"})
        assert _is_error(resp)
        assert "limit" in _get_error_message(resp).lower()

    def test_on_conflict_skip(self, server: MemoryMeshMCPServer) -> None:
        """on_conflict=skip should return a skip message when contradicted."""
        # First store a memory
        _call_tool(server, "remember", {"text": "the sky is blue"})
        # Store a contradicting memory with skip -- may or may not skip
        # depending on contradiction detection, but should not error
        resp = _call_tool(
            server,
            "remember",
            {"text": "the sky is blue", "on_conflict": "skip"},
        )
        assert not _is_error(resp)


class TestToolCallExceptionHandling:
    """Exception handling in tool dispatch."""

    def test_handler_exception_returns_error(self, server: MemoryMeshMCPServer) -> None:
        """If a tool handler raises, return a generic error."""
        with patch.object(server, "_tool_status", side_effect=ValueError("boom")):
            resp = _call_tool(server, "status", {})
        assert _is_error(resp)
        assert "error" in _get_error_message(resp).lower()

    def test_runtime_error_in_remember(self, server: MemoryMeshMCPServer) -> None:
        """RuntimeError from mesh.remember should be forwarded."""
        with patch.object(server._mesh, "remember", side_effect=RuntimeError("no project")):
            resp = _call_tool(server, "remember", {"text": "will fail"})
        assert _is_error(resp)
        assert "no project" in _get_error_message(resp).lower()
