"""Tests for the web dashboard."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

from memorymesh import MemoryMesh
from memorymesh.dashboard import run_dashboard


@pytest.fixture
def dashboard_server(tmp_path):
    """Start a dashboard server in a background thread with test data."""
    proj_db = str(tmp_path / "project" / "memories.db")
    glob_db = str(tmp_path / "global" / "global.db")
    mesh = MemoryMesh(path=proj_db, global_path=glob_db, embedding="none")

    # Add test data.
    mesh.remember("Test memory one", scope="project", importance=0.8)
    mesh.remember("Test memory two", scope="global", importance=0.5)
    mesh.remember(
        "Test memory three",
        scope="project",
        importance=0.3,
        metadata={"category": "decision"},
    )

    server = run_dashboard(mesh, port=0, open_browser=False, blocking=False)
    assert server is not None
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"

    # Give the server thread a moment to bind.
    time.sleep(0.1)

    yield base_url, mesh, server

    server.shutdown()
    server.server_close()
    mesh.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(url: str) -> tuple[int, object]:
    """GET request, return ``(status, parsed_json_or_text)``."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body


def _delete(url: str) -> tuple[int, object]:
    """DELETE request."""
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, json.loads(body)


def _patch(url: str, data: dict) -> tuple[int, object]:
    """PATCH request with JSON body."""
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body)
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")
        return e.code, json.loads(resp_body)


# ---------------------------------------------------------------------------
# HTML serving
# ---------------------------------------------------------------------------


class TestDashboardHTML:
    def test_serves_html_at_root(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, body = _get(base_url)
        assert status == 200
        assert "MemoryMesh" in body

    def test_html_contains_dashboard_elements(self, dashboard_server):
        base_url, _, _ = dashboard_server
        _status, body = _get(base_url)
        assert "memory-list" in body

    def test_serves_html_with_trailing_slash(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, body = _get(f"{base_url}/")
        assert status == 200
        assert "MemoryMesh" in body


# ---------------------------------------------------------------------------
# Stats API
# ---------------------------------------------------------------------------


class TestStatsAPI:
    def test_stats_returns_counts(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _get(f"{base_url}/api/stats")
        assert status == 200
        assert data["total"] == 3
        assert data["project_count"] == 2
        assert data["global_count"] == 1

    def test_stats_with_scope(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _get(f"{base_url}/api/stats?scope=project")
        assert status == 200
        assert "total" in data

    def test_stats_has_time_range(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _get(f"{base_url}/api/stats")
        assert status == 200
        assert "oldest" in data
        assert "newest" in data


# ---------------------------------------------------------------------------
# Memories list / search API
# ---------------------------------------------------------------------------


class TestMemoriesAPI:
    def test_list_all_memories(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _get(f"{base_url}/api/memories")
        assert status == 200
        assert len(data["memories"]) == 3
        assert data["total"] == 3

    def test_list_with_limit(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _get(f"{base_url}/api/memories?limit=1")
        assert status == 200
        assert len(data["memories"]) == 1

    def test_list_with_offset(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _get(f"{base_url}/api/memories?limit=2&offset=2")
        assert status == 200
        assert len(data["memories"]) == 1

    def test_list_with_scope_filter(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _get(f"{base_url}/api/memories?scope=global")
        assert status == 200
        assert len(data["memories"]) == 1
        assert data["memories"][0]["scope"] == "global"

    def test_search_memories(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _get(f"{base_url}/api/memories?search=memory+one")
        assert status == 200
        assert len(data["memories"]) >= 1

    def test_get_single_memory(self, dashboard_server):
        base_url, mesh, _ = dashboard_server
        memories = mesh.list(limit=1)
        mem_id = memories[0].id

        status, data = _get(f"{base_url}/api/memories/{mem_id}")
        assert status == 200
        assert data["id"] == mem_id

    def test_get_nonexistent_memory(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, _data = _get(f"{base_url}/api/memories/nonexistent123")
        assert status == 404

    def test_memory_has_all_fields(self, dashboard_server):
        base_url, _, _ = dashboard_server
        _status, data = _get(f"{base_url}/api/memories")
        mem = data["memories"][0]
        assert "id" in mem
        assert "text" in mem
        assert "importance" in mem
        assert "scope" in mem
        assert "created_at" in mem
        assert "updated_at" in mem
        assert "metadata" in mem
        assert "access_count" in mem
        assert "decay_rate" in mem
        assert "session_id" in mem

    def test_get_memory_has_embedding_field(self, dashboard_server):
        base_url, mesh, _ = dashboard_server
        memories = mesh.list(limit=1)
        mem_id = memories[0].id

        status, data = _get(f"{base_url}/api/memories/{mem_id}")
        assert status == 200
        assert "has_embedding" in data

    def test_limit_is_clamped(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _get(f"{base_url}/api/memories?limit=9999")
        assert status == 200
        assert data["limit"] == 500


# ---------------------------------------------------------------------------
# Delete API
# ---------------------------------------------------------------------------


class TestDeleteAPI:
    def test_delete_memory(self, dashboard_server):
        base_url, mesh, _ = dashboard_server
        memories = mesh.list(limit=1)
        mem_id = memories[0].id
        initial_count = mesh.count()

        status, data = _delete(f"{base_url}/api/memories/{mem_id}")
        assert status == 200
        assert data["deleted"] is True
        assert mesh.count() == initial_count - 1

    def test_delete_nonexistent(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, data = _delete(f"{base_url}/api/memories/nonexistent123")
        assert status == 200
        assert data["deleted"] is False


# ---------------------------------------------------------------------------
# Patch API
# ---------------------------------------------------------------------------


class TestPatchAPI:
    def test_update_importance(self, dashboard_server):
        base_url, mesh, _ = dashboard_server
        memories = mesh.list(limit=1)
        mem_id = memories[0].id

        status, data = _patch(
            f"{base_url}/api/memories/{mem_id}",
            {"importance": 0.99},
        )
        assert status == 200
        assert data["updated"] is True

        # Verify the change persisted.
        updated = mesh.get(mem_id)
        assert updated is not None
        assert abs(updated.importance - 0.99) < 0.01

    def test_update_nonexistent(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, _data = _patch(
            f"{base_url}/api/memories/nonexistent123",
            {"importance": 0.5},
        )
        assert status == 404

    def test_update_clamps_importance(self, dashboard_server):
        base_url, mesh, _ = dashboard_server
        memories = mesh.list(limit=1)
        mem_id = memories[0].id

        status, _data = _patch(
            f"{base_url}/api/memories/{mem_id}",
            {"importance": 5.0},  # should be clamped to 1.0
        )
        assert status == 200
        updated = mesh.get(mem_id)
        assert updated is not None
        assert updated.importance <= 1.0

    def test_update_metadata(self, dashboard_server):
        base_url, mesh, _ = dashboard_server
        memories = mesh.list(limit=1)
        mem_id = memories[0].id

        status, _data = _patch(
            f"{base_url}/api/memories/{mem_id}",
            {"metadata": {"tag": "test-tag"}},
        )
        assert status == 200
        updated = mesh.get(mem_id)
        assert updated is not None
        assert updated.metadata.get("tag") == "test-tag"

    def test_empty_body_returns_400(self, dashboard_server):
        base_url, _, _ = dashboard_server
        # Send a PATCH with Content-Length: 0.
        req = urllib.request.Request(
            f"{base_url}/api/memories/someid",
            data=b"",
            method="PATCH",
        )
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                resp.read()
        except urllib.error.HTTPError as e:
            status = e.code
            e.read()
        assert status == 400


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


class TestNotFound:
    def test_unknown_api_path(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, _ = _get(f"{base_url}/api/unknown")
        assert status == 404

    def test_unknown_top_level_path(self, dashboard_server):
        base_url, _, _ = dashboard_server
        status, _ = _get(f"{base_url}/nonexistent")
        assert status == 404
