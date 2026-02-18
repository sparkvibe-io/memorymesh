"""Web dashboard for MemoryMesh -- view, search, and manage memories in a browser.

Provides a lightweight HTTP server with a JSON API and a self-contained
single-page web application (SPA).  Uses **only the Python standard library**
(``http.server``, ``json``, ``urllib.parse``) -- no frameworks required.

Usage::

    from memorymesh.dashboard import run_dashboard
    run_dashboard(mesh, port=8765, open_browser=True)
"""

from __future__ import annotations

import json
import logging
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .core import MemoryMesh
from .dashboard_html import DASHBOARD_HTML
from .memory import GLOBAL_SCOPE, PROJECT_SCOPE

logger = logging.getLogger(__name__)


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the MemoryMesh dashboard.

    Serves the SPA at ``/`` and provides a JSON API under ``/api/``.
    The ``mesh`` class attribute is set by :func:`run_dashboard` before
    the server starts.
    """

    mesh: MemoryMesh  # Set via subclass in run_dashboard

    # noinspection PyPep8Naming
    def log_message(self, format: str, *args: Any) -> None:
        """Redirect HTTP logs to the module logger."""
        logger.debug(format, *args)

    # noinspection PyPep8Naming
    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        if path == "" or path == "/":
            self._serve_html()
        elif path == "/api/stats":
            self._api_stats(query)
        elif path == "/api/memories":
            self._api_list_memories(query)
        elif path.startswith("/api/memories/"):
            memory_id = path[len("/api/memories/") :]
            self._api_get_memory(memory_id)
        else:
            self._send_json({"error": "Not found"}, status=404)

    # noinspection PyPep8Naming
    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/memories/"):
            memory_id = path[len("/api/memories/") :]
            self._api_delete_memory(memory_id)
        else:
            self._send_json({"error": "Not found"}, status=404)

    # noinspection PyPep8Naming
    def do_PATCH(self) -> None:
        """Handle PATCH requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/memories/"):
            memory_id = path[len("/api/memories/") :]
            self._api_update_memory(memory_id)
        else:
            self._send_json({"error": "Not found"}, status=404)

    # -- Page serving -------------------------------------------------

    def _serve_html(self) -> None:
        """Serve the SPA HTML page."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

    # -- API endpoints ------------------------------------------------

    def _api_stats(self, query: dict[str, list[str]]) -> None:
        """GET /api/stats -- return memory statistics."""
        scope = self._get_scope(query)
        total = self.mesh.count(scope=scope)
        project_count = self.mesh.count(scope=PROJECT_SCOPE)
        global_count = self.mesh.count(scope=GLOBAL_SCOPE)
        oldest, newest = self.mesh.get_time_range(scope=scope)

        self._send_json(
            {
                "total": total,
                "project_count": project_count,
                "global_count": global_count,
                "oldest": oldest,
                "newest": newest,
            }
        )

    def _api_list_memories(self, query: dict[str, list[str]]) -> None:
        """GET /api/memories -- list or search memories."""
        scope = self._get_scope(query)
        limit = int(query.get("limit", ["50"])[0])
        offset = int(query.get("offset", ["0"])[0])
        search_values = query.get("search", [None])
        search_text: str | None = search_values[0] if search_values else None

        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        if search_text:
            memories = self.mesh.recall(query=search_text, k=limit, scope=scope)
        else:
            memories = self.mesh.list(limit=limit, offset=offset, scope=scope)

        total = self.mesh.count(scope=scope)

        results = []
        for mem in memories:
            results.append(
                {
                    "id": mem.id,
                    "text": mem.text,
                    "metadata": mem.metadata,
                    "importance": round(mem.importance, 4),
                    "decay_rate": round(mem.decay_rate, 4),
                    "access_count": mem.access_count,
                    "created_at": mem.created_at.isoformat(),
                    "updated_at": mem.updated_at.isoformat(),
                    "scope": mem.scope,
                    "session_id": mem.session_id,
                }
            )

        self._send_json(
            {
                "memories": results,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    def _api_get_memory(self, memory_id: str) -> None:
        """GET /api/memories/:id -- get a single memory by ID."""
        mem = self.mesh.get(memory_id)
        if mem is None:
            self._send_json({"error": "Memory not found"}, status=404)
            return

        emb = mem.embedding
        has_embedding = emb is not None and len(emb) > 0 if emb else False

        self._send_json(
            {
                "id": mem.id,
                "text": mem.text,
                "metadata": mem.metadata,
                "importance": round(mem.importance, 4),
                "decay_rate": round(mem.decay_rate, 4),
                "access_count": mem.access_count,
                "created_at": mem.created_at.isoformat(),
                "updated_at": mem.updated_at.isoformat(),
                "scope": mem.scope,
                "session_id": mem.session_id,
                "has_embedding": has_embedding,
            }
        )

    def _api_delete_memory(self, memory_id: str) -> None:
        """DELETE /api/memories/:id -- delete a memory."""
        deleted = self.mesh.forget(memory_id)
        self._send_json(
            {
                "deleted": deleted,
                "memory_id": memory_id,
            }
        )

    def _api_update_memory(self, memory_id: str) -> None:
        """PATCH /api/memories/:id -- update importance or metadata."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_json({"error": "Empty request body"}, status=400)
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=400)
            return

        mem = self.mesh.get(memory_id)
        if mem is None:
            self._send_json({"error": "Memory not found"}, status=404)
            return

        # Update allowed fields.
        if "importance" in data:
            new_imp = max(0.0, min(1.0, float(data["importance"])))
            mem.importance = new_imp

        if "metadata" in data and isinstance(data["metadata"], dict):
            mem.metadata.update(data["metadata"])

        # Persist changes via the appropriate store.
        store = self.mesh._global_store if mem.scope == GLOBAL_SCOPE else self.mesh._project_store
        if store:
            store.save(mem)

        self._send_json(
            {
                "updated": True,
                "memory_id": memory_id,
            }
        )

    # -- Helpers ------------------------------------------------------

    def _get_scope(self, query: dict[str, list[str]]) -> str | None:
        """Extract scope from query params. Returns ``None`` for ``'all'``."""
        scope = query.get("scope", ["all"])[0]
        if scope == "all":
            return None
        if scope in (PROJECT_SCOPE, GLOBAL_SCOPE):
            return scope
        return None

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        """Send a JSON response with appropriate headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        body = json.dumps(data, ensure_ascii=False)
        self.wfile.write(body.encode("utf-8"))


def run_dashboard(
    mesh: MemoryMesh,
    port: int = 8765,
    open_browser: bool = True,
    blocking: bool = True,
) -> HTTPServer | None:
    """Start the MemoryMesh web dashboard.

    Args:
        mesh: The MemoryMesh instance to serve.
        port: HTTP port to listen on.  Use ``0`` to let the OS pick a
            free port (useful for tests).  Default: ``8765``.
        open_browser: If ``True``, open the dashboard in the default browser.
        blocking: If ``True`` (default), block until the server is stopped
            via Ctrl-C.  If ``False``, run in a daemon thread and return
            the server instance.

    Returns:
        The :class:`HTTPServer` instance if *blocking* is ``False``,
        otherwise ``None`` (blocks until interrupted).
    """

    # Create a handler subclass with the mesh reference attached.
    class _BoundHandler(DashboardHandler):
        pass

    _BoundHandler.mesh = mesh  # type: ignore[attr-defined]

    server = HTTPServer(("127.0.0.1", port), _BoundHandler)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}"

    logger.info("Dashboard starting on %s", url)
    print(f"MemoryMesh Dashboard: {url}")
    print("Press Ctrl+C to stop.")

    if open_browser:
        webbrowser.open(url)

    if blocking:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
        finally:
            server.server_close()
            mesh.close()
        return None
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
