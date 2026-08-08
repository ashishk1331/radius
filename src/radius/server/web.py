"""The website — the documentation homepage and the static files around it.

These routes carry no token and serve nothing from the corpus. They exist so a
browser landing on the deployment finds a page, and so MCP clients can fetch the
icons the server advertises. On Vercel the same files are served statically from
``public/``; these routes are what make `radius serve` match that locally.

The page is split by how each piece reaches the browser. Anything fetched by URL
— the stylesheet, the script, the fonts, the icons — lives in ``public/`` so
Vercel serves it straight from its CDN. The HTML template and the SVG fragments
it composes stay in the package, because the homepage is rendered by the
function, and because an inlined diagram inherits the page's theme variables
where one loaded through ``<img>`` could not.
"""

import re
from functools import lru_cache, partial

from fastmcp import FastMCP
from mcp.types import Icon
from starlette.requests import Request
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    Response,
)

from radius.config import PACKAGE_ROOT, Settings

STATIC_DIR = PACKAGE_ROOT / "static"

ICON_SIZES = (48, 96, 256)
ICON_THEMES = (("light", ""), ("dark", "-dark"))
MCP_ICON_FILES = frozenset(
    f"logo{suffix}-{size}.png" for _, suffix in ICON_THEMES for size in ICON_SIZES
)
FONT_FILES = frozenset({"figtree-latin.woff2", "figtree-latin-ext.woff2"})

ASSET_CACHE = "public, max-age=604800"
FONT_CACHE = "public, max-age=31536000, immutable"
PAGE_CACHE = "public, max-age=3600"

SITE_ASSETS = {
    "favicon.ico": ASSET_CACHE,
    "favicon-16x16.png": ASSET_CACHE,
    "favicon-32x32.png": ASSET_CACHE,
    "apple-touch-icon.png": ASSET_CACHE,
    "android-chrome-192x192.png": ASSET_CACHE,
    "android-chrome-512x512.png": ASSET_CACHE,
    "site.webmanifest": ASSET_CACHE,
    "styles.css": PAGE_CACHE,
    "app.js": PAGE_CACHE,
}

INCLUDE = re.compile(r"^([ \t]*)\{\{\s*([\w./-]+)\s*\}\}[ \t]*$", re.MULTILINE)


def fragment(name: str) -> str:
    """Read one template fragment, refusing any name that escapes ``static/``."""
    path = (STATIC_DIR / name).resolve()
    if not path.is_relative_to(STATIC_DIR.resolve()) or not path.is_file():
        raise FileNotFoundError(f"no template fragment named {name!r}")
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def homepage() -> str:
    """The rendered page, with every ``{{ fragment }}`` composed in.

    Diagrams live in their own files so one can be edited without scrolling
    past the rest of the page. They are resolved once, here, rather than on
    each request.
    """
    template = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    def resolve(match: re.Match) -> str:
        indent = match.group(1)
        body = fragment(match.group(2))
        return "\n".join(indent + line if line else line for line in body.split("\n"))

    return INCLUDE.sub(resolve, template)


def server_icons(config: Settings) -> list[Icon]:
    """Light and dark logo variants, at the sizes MCP clients pick between."""
    base = config.issuer.rstrip("/")
    return [
        Icon(
            src=f"{base}/mcp-icons/logo{suffix}-{size}.png",
            mimeType="image/png",
            sizes=[f"{size}x{size}"],
            theme=theme,
        )
        for theme, suffix in ICON_THEMES
        for size in ICON_SIZES
    ]


def public_asset(config: Settings, *parts: str, cache: str = ASSET_CACHE) -> Response:
    """Serve a file from ``public/``, which Vercel serves statically in prod."""
    path = config.root.joinpath("public", *parts)
    if not path.is_file():
        return PlainTextResponse("not found", status_code=404)
    return FileResponse(path, headers={"Cache-Control": cache})


async def site_asset_route(
    config: Settings, name: str, cache: str, request: Request
) -> Response:
    return public_asset(config, name, cache=cache)


def register_routes(mcp: FastMCP, config: Settings) -> None:
    """Mount the homepage, the stylesheet and script, the icons, and the fonts."""

    @mcp.custom_route("/", methods=["GET"])
    async def home_route(request: Request) -> HTMLResponse:
        return HTMLResponse(homepage())

    @mcp.custom_route("/mcp-icons/{name}", methods=["GET"])
    async def mcp_icon_route(request: Request) -> Response:
        name = request.path_params["name"]
        if name not in MCP_ICON_FILES:
            return PlainTextResponse("not found", status_code=404)
        return public_asset(config, "mcp-icons", name)

    @mcp.custom_route("/fonts/{name}", methods=["GET"])
    async def font_route(request: Request) -> Response:
        name = request.path_params["name"]
        if name not in FONT_FILES:
            return PlainTextResponse("not found", status_code=404)
        return public_asset(config, "fonts", name, cache=FONT_CACHE)

    for asset, cache in SITE_ASSETS.items():
        mcp.custom_route(f"/{asset}", methods=["GET"], name=f"asset-{asset}")(
            partial(site_asset_route, config, asset, cache)
        )
