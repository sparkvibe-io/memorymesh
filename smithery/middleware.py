"""Smithery config middleware for extracting session configuration.

Smithery passes session configuration as a base64-encoded JSON query parameter.
This middleware extracts and injects it into the ASGI scope for per-request access.
"""

from __future__ import annotations

import base64
import json
import os
from urllib.parse import parse_qs, unquote


class SmitheryConfigMiddleware:
    """ASGI middleware that extracts Smithery config from query parameters.

    Smithery encodes session configuration as ``?config=<base64-json>`` in the
    URL.  This middleware decodes it and sets relevant environment variables
    so the MemoryMesh instance picks up the configuration.
    """

    def __init__(self, app: object) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: object, send: object) -> None:
        if scope.get("type") == "http":
            query = scope.get("query_string", b"").decode()

            if "config=" in query:
                try:
                    config_b64 = unquote(parse_qs(query)["config"][0])
                    config = json.loads(base64.b64decode(config_b64))
                    scope["smithery_config"] = config

                    # Map Smithery config to MemoryMesh environment variables
                    if project_path := config.get("projectPath"):
                        os.environ["MEMORYMESH_PATH"] = (
                            project_path + "/.memorymesh/memories.db"
                        )
                    if global_path := config.get("globalPath"):
                        os.environ["MEMORYMESH_GLOBAL_PATH"] = global_path
                    if embedding := config.get("embedding"):
                        os.environ["MEMORYMESH_EMBEDDING"] = embedding
                except Exception as e:
                    print(f"SmitheryConfigMiddleware: Error parsing config: {e}")
                    scope["smithery_config"] = {}
            else:
                scope["smithery_config"] = {}

        await self.app(scope, receive, send)  # type: ignore[operator]
