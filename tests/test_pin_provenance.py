"""Tests for pin support (Feature 1) and provenance metadata (Feature 3)."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from memorymesh.core import MemoryMesh
from memorymesh.mcp_server import MemoryMeshMCPServer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test databases."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def mesh(tmp_dir: str) -> MemoryMesh:
    """Create a MemoryMesh instance for testing."""
    db_path = os.path.join(tmp_dir, "project.db")
    global_path = os.path.join(tmp_dir, "global.db")
    return MemoryMesh(path=db_path, global_path=global_path, embedding="none")


@pytest.fixture
def mcp_server(mesh: MemoryMesh) -> MemoryMeshMCPServer:
    """Create an MCP server wrapping the test mesh."""
    server = MemoryMeshMCPServer(mesh=mesh)
    server._initialized = True
    return server


# ---------------------------------------------------------------------------
# Pin support tests
# ---------------------------------------------------------------------------


class TestPinSupport:
    """Tests for pin=True in remember()."""

    def test_pin_sets_importance_to_max(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Important pinned memory", pin=True)
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.importance == 1.0

    def test_pin_sets_decay_to_zero(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Pinned memory", pin=True)
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.decay_rate == 0.0

    def test_pin_adds_metadata_flag(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Pinned memory", pin=True)
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.metadata.get("pinned") is True

    def test_pin_overrides_auto_importance(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember(
            "Some text",
            auto_importance=True,
            pin=True,
        )
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.importance == 1.0
        assert mem.decay_rate == 0.0

    def test_pin_overrides_explicit_importance(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Some text", importance=0.3, pin=True)
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.importance == 1.0

    def test_no_pin_default(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Normal memory")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.metadata.get("pinned") is None

    def test_pin_via_mcp(self, mcp_server: MemoryMeshMCPServer) -> None:
        result = mcp_server._tool_remember({"text": "MCP pinned", "pin": True})
        assert "isError" not in result
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        mid = data["memory_id"]
        mem = mcp_server._mesh.get(mid)
        assert mem is not None
        assert mem.importance == 1.0
        assert mem.metadata.get("pinned") is True


# ---------------------------------------------------------------------------
# Privacy guard integration tests (in remember)
# ---------------------------------------------------------------------------


class TestPrivacyInRemember:
    """Tests for privacy guard integration in remember()."""

    def test_secret_detection_adds_warning_metadata(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("API key: sk-abcdefghijklmnopqrstuvwxyz")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.metadata.get("has_secrets_warning") is True
        assert "API key" in mem.metadata.get("detected_secret_types", [])

    def test_redact_replaces_secrets(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember(
            "Use sk-abcdefghijklmnopqrstuvwxyz for auth",
            redact=True,
        )
        mem = mesh.get(mid)
        assert mem is not None
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in mem.text
        assert "[REDACTED]" in mem.text

    def test_no_redact_preserves_text(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("Use sk-abcdefghijklmnopqrstuvwxyz for auth")
        mem = mesh.get(mid)
        assert mem is not None
        assert "sk-abcdefghijklmnopqrstuvwxyz" in mem.text

    def test_safe_text_no_warning(self, mesh: MemoryMesh) -> None:
        mid = mesh.remember("The user prefers dark mode")
        mem = mesh.get(mid)
        assert mem is not None
        assert mem.metadata.get("has_secrets_warning") is None

    def test_redact_via_mcp(self, mcp_server: MemoryMeshMCPServer) -> None:
        result = mcp_server._tool_remember(
            {
                "text": "key sk-abcdefghijklmnopqrstuvwxyz",
                "redact_secrets": True,
            }
        )
        assert "isError" not in result
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        mid = data["memory_id"]
        mem = mcp_server._mesh.get(mid)
        assert mem is not None
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in mem.text


# ---------------------------------------------------------------------------
# Provenance metadata tests
# ---------------------------------------------------------------------------


class TestProvenanceMetadata:
    """Tests for automatic provenance metadata in MCP server."""

    def test_source_auto_populated(self, mcp_server: MemoryMeshMCPServer) -> None:
        result = mcp_server._tool_remember({"text": "Some fact"})
        assert "isError" not in result
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        mid = data["memory_id"]
        mem = mcp_server._mesh.get(mid)
        assert mem is not None
        assert mem.metadata.get("source") == "mcp"

    def test_tool_auto_populated_after_init(self, mesh: MemoryMesh, tmp_dir: str) -> None:
        server = MemoryMeshMCPServer(mesh=mesh)
        # Simulate initialize with clientInfo
        server._handle_initialize(
            {
                "clientInfo": {"name": "claude-code"},
                "protocolVersion": "2024-11-05",
                "capabilities": {},
            }
        )
        # The mesh was re-created during init, need to set up project path
        result = server._tool_remember({"text": "Fact after init"})
        assert "isError" not in result
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        mid = data["memory_id"]
        mem = server._mesh.get(mid)
        assert mem is not None
        assert mem.metadata.get("tool") == "claude-code"

    def test_client_name_stored_on_init(self, mesh: MemoryMesh) -> None:
        server = MemoryMeshMCPServer(mesh=mesh)
        server._handle_initialize(
            {
                "clientInfo": {"name": "cursor"},
                "protocolVersion": "2024-11-05",
                "capabilities": {},
            }
        )
        assert server._client_name == "cursor"

    def test_user_metadata_not_overwritten(self, mcp_server: MemoryMeshMCPServer) -> None:
        # If user provides their own source, it should be preserved.
        result = mcp_server._tool_remember(
            {
                "text": "User-sourced fact",
                "metadata": {"source": "manual"},
            }
        )
        assert "isError" not in result
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        mid = data["memory_id"]
        mem = mcp_server._mesh.get(mid)
        assert mem is not None
        assert mem.metadata.get("source") == "manual"

    def test_default_client_name_unknown(self, mcp_server: MemoryMeshMCPServer) -> None:
        assert mcp_server._client_name == "unknown"
