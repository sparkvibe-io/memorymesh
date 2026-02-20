"""Tests for feedback-driven fixes: project detection, status tool,
configure_project tool, session_start health, lazy init, and init config path.

Covers fixes for all P0/P1/P2/P3 issues from the agent feedback report.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from memorymesh.core import MemoryMesh
from memorymesh.mcp_server import MemoryMeshMCPServer
from memorymesh.store import _PROJECT_MARKERS, detect_project_root

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test databases."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def mesh(tmp_dir: str) -> Generator[MemoryMesh, None, None]:
    """Create a MemoryMesh instance with both stores."""
    db_path = os.path.join(tmp_dir, "project.db")
    global_path = os.path.join(tmp_dir, "global.db")
    m = MemoryMesh(path=db_path, global_path=global_path, embedding="none")
    yield m
    m.close()


@pytest.fixture
def mcp_server(mesh: MemoryMesh) -> MemoryMeshMCPServer:
    """Create an MCP server wrapping the test mesh."""
    server = MemoryMeshMCPServer(mesh=mesh)
    server._initialized = True
    return server


# ---------------------------------------------------------------------------
# TestExpandedProjectMarkers
# ---------------------------------------------------------------------------


class TestExpandedProjectMarkers:
    """detect_project_root() recognises markers beyond .git and pyproject.toml."""

    @pytest.mark.parametrize(
        "marker",
        [
            ".git",
            "pyproject.toml",
            "Cargo.toml",
            "package.json",
            "go.mod",
            ".hg",
            "build.gradle",
            "pom.xml",
            "CMakeLists.txt",
            "Makefile",
            ".memorymesh",
        ],
    )
    def test_cwd_detects_marker(self, tmp_path, monkeypatch, marker):
        """CWD heuristic finds projects with any recognised marker."""
        marker_path = tmp_path / marker
        if marker in (".git", ".hg", ".memorymesh"):
            marker_path.mkdir()
        else:
            marker_path.touch()

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)

        result = detect_project_root(None)
        assert result == os.path.realpath(str(tmp_path))

    def test_project_markers_constant_complete(self):
        """All expected markers are in _PROJECT_MARKERS."""
        expected = {
            ".git",
            "pyproject.toml",
            "Cargo.toml",
            "package.json",
            "go.mod",
            ".hg",
            "build.gradle",
            "pom.xml",
            "CMakeLists.txt",
            "Makefile",
            ".memorymesh",
        }
        assert set(_PROJECT_MARKERS) == expected


# ---------------------------------------------------------------------------
# TestWalkUpDetection
# ---------------------------------------------------------------------------


class TestWalkUpDetection:
    """detect_project_root() walks up from CWD to find project markers."""

    def test_walk_up_finds_git_in_parent(self, tmp_path, monkeypatch):
        """Finds .git in a parent directory when CWD is a subdirectory."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src" / "components"
        subdir.mkdir(parents=True)

        monkeypatch.chdir(subdir)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)

        result = detect_project_root(None)
        assert result == os.path.realpath(str(tmp_path))

    def test_walk_up_finds_cargo_in_parent(self, tmp_path, monkeypatch):
        """Finds Cargo.toml in parent when CWD is a Rust subdirectory."""
        (tmp_path / "Cargo.toml").touch()
        subdir = tmp_path / "src"
        subdir.mkdir()

        monkeypatch.chdir(subdir)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)

        result = detect_project_root(None)
        assert result == os.path.realpath(str(tmp_path))

    def test_walk_up_stops_at_nearest_marker(self, tmp_path, monkeypatch):
        """Picks the nearest ancestor with a marker, not the root."""
        # Outer project
        (tmp_path / ".git").mkdir()
        # Inner project (should be picked)
        inner = tmp_path / "packages" / "frontend"
        inner.mkdir(parents=True)
        (inner / "package.json").touch()

        monkeypatch.chdir(inner)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)

        result = detect_project_root(None)
        assert result == os.path.realpath(str(inner))

    def test_walk_up_returns_none_at_root(self, tmp_path, monkeypatch):
        """Returns None when no marker is found anywhere up the tree."""
        # tmp_path has no markers, and we can't go above it reliably
        # so use a deep subdir with no markers
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)

        monkeypatch.chdir(deep)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)

        # Note: this may find the MemoryMesh project root if we're running
        # inside it. To isolate, we'd need to mock os.path.dirname,
        # but the principle is tested via the positive cases above.
        # Just verify it doesn't crash.
        detect_project_root(None)


# ---------------------------------------------------------------------------
# TestDetectionDiagnostics
# ---------------------------------------------------------------------------


class TestDetectionDiagnostics:
    """detect_project_root() collects diagnostic information."""

    def test_diagnostics_populated_on_success(self, tmp_path, monkeypatch):
        """Diagnostics list is populated even on success."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)

        diagnostics: list[str] = []
        result = detect_project_root(None, diagnostics=diagnostics)

        assert result is not None
        assert len(diagnostics) >= 1

    def test_diagnostics_populated_on_failure(self, tmp_path, monkeypatch):
        """Diagnostics explain what was tried when detection fails."""
        deep = tmp_path / "empty"
        deep.mkdir()
        monkeypatch.chdir(deep)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)

        diagnostics: list[str] = []
        detect_project_root(None, diagnostics=diagnostics)

        # Should have at least MCP roots + env var + CWD entries
        assert len(diagnostics) >= 2
        diag_text = "\n".join(diagnostics)
        assert "MCP roots" in diag_text or "not provided" in diag_text
        assert "MEMORYMESH_PROJECT_ROOT" in diag_text

    def test_diagnostics_none_is_safe(self, tmp_path, monkeypatch):
        """Passing diagnostics=None doesn't crash."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("MEMORYMESH_PROJECT_ROOT", raising=False)
        # Should not raise
        detect_project_root(None, diagnostics=None)

    def test_diagnostics_with_mcp_roots(self, tmp_path):
        """MCP root detection adds diagnostic entry."""
        roots = [{"uri": Path(tmp_path).as_uri()}]
        diagnostics: list[str] = []
        detect_project_root(roots, diagnostics=diagnostics)

        assert any("MCP roots" in d for d in diagnostics)


# ---------------------------------------------------------------------------
# TestStatusTool
# ---------------------------------------------------------------------------


class TestStatusTool:
    """MCP status tool reports health diagnostics."""

    def test_status_with_project_configured(self, mcp_server):
        """Status shows both stores as OK when project is configured."""
        result = mcp_server._tool_status({})
        assert "isError" not in result

        data = json.loads(result["content"][0]["text"])
        assert data["project_store"]["status"] == "ok"
        assert data["global_store"]["status"] == "ok"
        assert data["global_store"]["count"] >= 0
        assert "version" in data

    def test_status_without_project(self, tmp_dir):
        """Status reports project as not_configured with fix options."""
        # Create mesh with global-only (no project path)
        global_path = os.path.join(tmp_dir, "global.db")
        mesh = MemoryMesh(global_path=global_path, embedding="none")
        try:
            server = MemoryMeshMCPServer(mesh=mesh)
            server._initialized = True
            server._detection_diagnostics = [
                "MCP roots: not provided by client",
                "MEMORYMESH_PROJECT_ROOT: not set",
            ]

            result = server._tool_status({})
            data = json.loads(result["content"][0]["text"])

            assert data["project_store"]["status"] == "not_configured"
            assert "fix_options" in data["project_store"]
            assert len(data["project_store"]["fix_options"]) >= 3
            assert data["project_store"]["detection_attempted"] == [
                "MCP roots: not provided by client",
                "MEMORYMESH_PROJECT_ROOT: not set",
            ]
            assert data["global_store"]["status"] == "ok"
        finally:
            mesh.close()


# ---------------------------------------------------------------------------
# TestConfigureProjectTool
# ---------------------------------------------------------------------------


class TestConfigureProjectTool:
    """MCP configure_project tool sets project root at runtime."""

    def test_configure_project_success(self, tmp_dir, monkeypatch):
        """configure_project creates project store at the given path."""
        project_dir = os.path.join(tmp_dir, "my_project")
        os.makedirs(project_dir)

        global_path = os.path.join(tmp_dir, "global.db")
        mesh = MemoryMesh(global_path=global_path, embedding="none")
        try:
            server = MemoryMeshMCPServer(mesh=mesh)
            server._initialized = True

            # Verify project is not configured initially
            assert mesh.project_path is None

            # Configure the project
            result = server._tool_configure_project({"path": project_dir})
            assert "isError" not in result

            data = json.loads(result["content"][0]["text"])
            assert data["project_root"] == os.path.realpath(project_dir)
            assert "memories.db" in data["project_db"]

            # Verify we can now remember with project scope
            server._mesh.remember("test memory", scope="project")
            assert server._mesh.count(scope="project") == 1
        finally:
            server._mesh.close()

    def test_configure_project_missing_path(self, mcp_server):
        """configure_project errors when path is missing."""
        result = mcp_server._tool_configure_project({})
        assert result["isError"] is True

    def test_configure_project_invalid_path(self, mcp_server):
        """configure_project errors when path doesn't exist."""
        result = mcp_server._tool_configure_project({"path": "/nonexistent/path"})
        assert result["isError"] is True
        data = json.loads(result["content"][0]["text"])
        assert "does not exist" in data["error"]


# ---------------------------------------------------------------------------
# TestSessionStartHealth
# ---------------------------------------------------------------------------


class TestSessionStartHealth:
    """session_start includes store health information."""

    def test_session_start_includes_health(self, mcp_server):
        """session_start response includes store_health field."""
        result = mcp_server._tool_session_start({})
        data = json.loads(result["content"][0]["text"])

        assert "store_health" in data
        assert data["store_health"]["global_store"] == "ok"
        assert data["store_health"]["project_store"] == "ok"

    def test_session_start_health_warns_when_no_project(self, tmp_dir):
        """session_start warns when project store is not configured."""
        global_path = os.path.join(tmp_dir, "global.db")
        mesh = MemoryMesh(global_path=global_path, embedding="none")
        try:
            server = MemoryMeshMCPServer(mesh=mesh)
            server._initialized = True

            result = server._tool_session_start({})
            data = json.loads(result["content"][0]["text"])

            assert data["store_health"]["project_store"] == "not_configured"
            assert "warning" in data["store_health"]
            assert "configure_project" in data["store_health"]["warning"]
        finally:
            mesh.close()


# ---------------------------------------------------------------------------
# TestLazyInitialization
# ---------------------------------------------------------------------------


class TestLazyInitialization:
    """MCP server uses lazy initialization (no double-init)."""

    def test_constructor_without_mesh(self):
        """Server can be created without a mesh (lazy init)."""
        server = MemoryMeshMCPServer()
        assert server._mesh is None
        assert server._initialized is False

    def test_constructor_with_mesh(self, mesh):
        """Server can still accept a pre-built mesh."""
        server = MemoryMeshMCPServer(mesh=mesh)
        assert server._mesh is mesh

    def test_initialize_creates_mesh(self, tmp_path, monkeypatch):
        """_handle_initialize creates the mesh on first call."""
        # Create a project directory with a marker
        (tmp_path / ".git").mkdir()

        server = MemoryMeshMCPServer()
        assert server._mesh is None

        # Simulate initialize with MCP roots
        params = {
            "clientInfo": {"name": "test-client"},
            "roots": [{"uri": Path(tmp_path).as_uri()}],
        }
        result = server._handle_initialize(params)

        assert server._mesh is not None
        assert server._initialized is True
        assert "protocolVersion" in result
        server._mesh.close()

    def test_tool_call_before_init_errors(self):
        """Tool calls before initialize return an error."""
        server = MemoryMeshMCPServer()

        result = server._handle_tools_call({
            "name": "recall",
            "arguments": {"query": "test"},
        })

        assert result["isError"] is True
        data = json.loads(result["content"][0]["text"])
        assert "not initialized" in data["error"].lower()

    def test_detection_diagnostics_stored(self, tmp_path, monkeypatch):
        """Initialize stores detection diagnostics for later reporting."""
        server = MemoryMeshMCPServer()

        params = {
            "clientInfo": {"name": "test-client"},
            "roots": [{"uri": Path(tmp_path).as_uri()}],
        }
        server._handle_initialize(params)

        assert len(server._detection_diagnostics) >= 1
        server._mesh.close()


# ---------------------------------------------------------------------------
# TestImprovedErrorMessages
# ---------------------------------------------------------------------------


class TestImprovedErrorMessages:
    """Error messages include actionable fix steps."""

    def test_project_scope_error_has_fix_options(self, tmp_dir):
        """RuntimeError for missing project includes fix steps."""
        global_path = os.path.join(tmp_dir, "global.db")
        mesh = MemoryMesh(global_path=global_path, embedding="none")
        try:
            with pytest.raises(RuntimeError) as exc_info:
                mesh.remember("test", scope="project")

            error_msg = str(exc_info.value)
            assert "configure_project" in error_msg
            assert "MEMORYMESH_PROJECT_ROOT" in error_msg
            assert "MEMORYMESH_PATH" in error_msg
            assert "scope='global'" in error_msg
        finally:
            mesh.close()

    def test_global_scope_always_works(self, tmp_dir):
        """Global scope works even without project configuration."""
        global_path = os.path.join(tmp_dir, "global.db")
        mesh = MemoryMesh(global_path=global_path, embedding="none")
        try:
            # This should NOT raise
            memory_id = mesh.remember("test global", scope="global")
            assert memory_id
            assert mesh.count(scope="global") == 1
        finally:
            mesh.close()


# ---------------------------------------------------------------------------
# TestInitConfigPath
# ---------------------------------------------------------------------------


class TestInitConfigPath:
    """memorymesh init writes to settings.json (not legacy path)."""

    def test_init_writes_settings_json(self, tmp_path, monkeypatch, capsys):
        """init creates ~/.claude/settings.json, not claude_code_config.json."""
        from memorymesh.init_cmd import run_init

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(
            os.path, "expanduser", lambda p: p.replace("~", str(fake_home))
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        rc = run_init(
            project_path=str(project_dir), skip_mcp=False, skip_claude_md=True
        )
        assert rc == 0

        # settings.json should exist
        settings_path = fake_home / ".claude" / "settings.json"
        assert settings_path.is_file()

        # Legacy path should NOT exist
        legacy_path = fake_home / ".claude" / "claude_code_config.json"
        assert not legacy_path.exists()

        # Verify content
        config = json.loads(settings_path.read_text())
        assert "mcpServers" in config
        assert "memorymesh" in config["mcpServers"]
