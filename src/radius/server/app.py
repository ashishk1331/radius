"""Assembling the server: the MCP surface, the website, and the process lifecycle.

Two layers of protection sit in front of every tool and resource:

1. The ``JWTVerifier`` passed as ``auth`` — FastMCP rejects any MCP request
   whose bearer token is missing, malformed, expired, or signed by an unknown
   key, before tool code runs.
2. ``auth=require_scopes(...)`` on each registration — a valid token still only
   opens what its ``scope`` claim covers.
"""

from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from starlette.requests import Request
from starlette.responses import JSONResponse

from radius.auth import keys, scopes, verifier
from radius.config import Settings, settings
from radius.server import web
from radius.server.resources import BOOKMARK_URI, get_bookmark
from radius.server.tools import (
    fetch_bookmarks,
    list_authors,
    recent_bookmarks,
    bookmarks_by_author,
    whoami,
)


def create_server(config: Settings | None = None) -> FastMCP:
    """Build the server with its verifier and per-tool scope requirements."""
    config = config or settings()

    mcp = FastMCP(
        name="Radius",
        auth=verifier.build(config),
        website_url=config.issuer.rstrip("/"),
        icons=web.server_icons(config),
    )

    read_only = require_scopes(scopes.READ_BOOKMARKS)
    mcp.tool(fetch_bookmarks, tags={"bookmarks"}, auth=read_only)
    mcp.tool(recent_bookmarks, tags={"bookmarks"}, auth=read_only)
    mcp.tool(list_authors, tags={"bookmarks"}, auth=read_only)
    mcp.tool(bookmarks_by_author, tags={"bookmarks"}, auth=read_only)
    mcp.tool(whoami, tags={"bookmarks"}, auth=read_only)
    mcp.resource(uri=BOOKMARK_URI, tags={"bookmarks"}, auth=read_only)(get_bookmark)

    # Public routes: FastMCP wraps only the MCP endpoint in its auth
    # middleware, so these stay reachable without a token — which is what a
    # JWKS document and a health check both need to be.
    @mcp.custom_route("/.well-known/jwks.json", methods=["GET"])
    async def jwks_route(request: Request) -> JSONResponse:
        return JSONResponse(keys.load_jwks(config))

    @mcp.custom_route("/health", methods=["GET"])
    async def health_route(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    web.register_routes(mcp, config)

    return mcp


_server: FastMCP | None = None


def get_server() -> FastMCP:
    """The process-wide server, built on first use.

    Construction reads key material, so it is deferred rather than done at
    import time — importing this module should not fail on a machine that has
    not run `radius keys init` yet.
    """
    global _server
    if _server is None:
        _server = create_server()
    return _server


def asgi_app():
    """ASGI factory for uvicorn, which needs an import string to reload."""
    return get_server().http_app()


def run() -> None:
    config = settings()
    get_server().run(transport="http", host=config.host, port=config.port)
