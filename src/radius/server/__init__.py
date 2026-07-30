"""The Radius MCP server.

Four modules, split by what each one answers to:

* :mod:`radius.server.tools` — the calls the model makes
* :mod:`radius.server.resources` — the URIs a client reads and cites
* :mod:`radius.server.web` — the homepage and its static files
* :mod:`radius.server.app` — assembly, scope guards, and process lifecycle

Everything the rest of the codebase needs is re-exported here, so
``from radius.server import create_server`` keeps working.
"""

from radius.server.app import asgi_app, create_server, get_server, run
from radius.server.resources import BOOKMARK_URI, get_bookmark
from radius.server.tools import MAX_TOP_K, fetch_bookmarks, whoami

__all__ = [
    "BOOKMARK_URI",
    "MAX_TOP_K",
    "asgi_app",
    "create_server",
    "fetch_bookmarks",
    "get_bookmark",
    "get_server",
    "run",
    "whoami",
]


def __getattr__(name: str):
    # Keeps `fastmcp run radius/server:mcp` working against the lazy server.
    if name == "mcp":
        return get_server()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
