"""The Radius MCP server and the tools it exposes.

Two layers of protection sit in front of every tool:

1. The ``JWTVerifier`` passed as ``auth`` — FastMCP rejects any MCP request
   whose bearer token is missing, malformed, expired, or signed by an unknown
   key, before tool code runs.
2. ``auth=require_scopes(...)`` on each tool — a valid token still only opens
   the tools its ``scope`` claim covers.
"""

from functools import lru_cache
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from fastmcp.server.dependencies import get_access_token
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from radius import search
from radius.auth import keys, scopes, verifier
from radius.config import Settings, settings
from radius.db import SEARCH_EXACT, SEARCH_MODES, SELECT_ALL, SearchMode, connect
from radius.db import query as run_query
from radius.models import SearchResult

MAX_TOP_K = 50
STATIC_DIR = Path(__file__).resolve().parent / "static"


@lru_cache(maxsize=1)
def homepage() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


def fetch_bookmarks(
    query: str, search_mode: SearchMode = "exact", top_k: int = 5
) -> list[SearchResult]:
    """
    Fetch the top k similar tweets (saved bookmarks) to the passed query.

    Args:
        query: String to be search.
        search_mode: Strategy to use ('exact' or 'fuzzy'). Defaults to 'exact'.
        top_k: Top k similar to tweets/bookmarks. Defaults to 5.
    """
    if search_mode not in SEARCH_MODES:
        raise ValueError(f"search_mode must be one of {sorted(SEARCH_MODES)}")

    limit = max(1, min(top_k, MAX_TOP_K))

    with connect() as con:
        if search_mode == "exact":
            rows = run_query(con, SEARCH_EXACT, (query, limit))
        else:
            rows = search.rank_fuzzy(run_query(con, SELECT_ALL), query, limit)

    return [SearchResult.from_row(row) for row in rows]


def whoami() -> dict:
    """Report the client identity and scopes carried by the current token."""
    token = get_access_token()
    if token is None:  # unreachable while a verifier is configured
        raise RuntimeError("no access token in context")

    return {
        "client": token.claims.get("sub"),
        "scopes": list(token.scopes),
        "issuer": token.claims.get("iss"),
        "expires_at": token.claims.get("exp"),
    }


def create_server(config: Settings | None = None) -> FastMCP:
    """Build the server with its verifier and per-tool scope requirements."""
    config = config or settings()

    mcp = FastMCP(name="Radius", auth=verifier.build(config))

    read_only = require_scopes(scopes.READ_BOOKMARKS)
    mcp.tool(fetch_bookmarks, tags={"bookmarks"}, auth=read_only)
    mcp.tool(whoami, tags={"bookmarks"}, auth=read_only)

    # Public routes: FastMCP wraps only the MCP endpoint in its auth
    # middleware, so these stay reachable without a token — which is what a
    # JWKS document and a health check both need to be.
    @mcp.custom_route("/.well-known/jwks.json", methods=["GET"])
    async def jwks_route(request: Request) -> JSONResponse:
        return JSONResponse(keys.load_jwks(config))

    @mcp.custom_route("/health", methods=["GET"])
    async def health_route(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @mcp.custom_route("/", methods=["GET"])
    async def home_route(request: Request) -> HTMLResponse:
        return HTMLResponse(homepage())

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


def __getattr__(name: str):
    # Keeps `fastmcp run radius/server.py:mcp` working against the lazy server.
    if name == "mcp":
        return get_server()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def run() -> None:
    config = settings()
    get_server().run(transport="http", host=config.host, port=config.port)


if __name__ == "__main__":
    run()
