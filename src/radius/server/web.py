"""The website — the documentation homepage and the static files around it.

These routes carry no token and serve nothing from the corpus. They exist so a
browser landing on the deployment finds a page, and so MCP clients can fetch the
icons the server advertises. On Vercel the same files are served statically from
``public/``; these routes are what make `radius serve` match that locally.

The site is split by how each piece reaches the browser. Anything fetched by URL
— the stylesheet, the script, the fonts, the icons — lives in ``public/`` so
Vercel serves it straight from its CDN. The HTML templates and the fragments
they compose stay in the package, because the pages are rendered by the
function, and because an inlined diagram inherits the page's theme variables
where one loaded through ``<img>`` could not.

Documentation is four pages rather than one, so a reader lands on the part they
came for instead of scrolling past the rest. ``parts/`` holds what every page
repeats — the head, the topbar, the nav, the footer — composed by the same
``{{ fragment }}`` mechanism the diagrams use.
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

# URL path -> template. The nav links these in this order, and nothing outside
# the mapping is renderable, so a request cannot name an arbitrary file.
PAGES = {
    "/": "index.html",
    "/start": "start.html",
    "/tools": "tools.html",
    "/operate": "operate.html",
}


def fragment(name: str) -> str:
    """Read one template fragment, refusing any name that escapes ``static/``."""
    path = (STATIC_DIR / name).resolve()
    if not path.is_relative_to(STATIC_DIR.resolve()) or not path.is_file():
        raise FileNotFoundError(f"no template fragment named {name!r}")
    return path.read_text(encoding="utf-8").strip()


# The two assets that change while you are looking at the page. Neither has a
# hash in its filename, so a browser holding a still-fresh copy will not even
# ask whether it changed — a plain refresh renders new HTML against old CSS.
# Stamping the URL with the file's mtime makes it a different URL instead,
# which no cached entry can answer.
VERSIONED = ("/styles.css", "/app.js")


def asset_version(config: Settings) -> str:
    """A token that changes whenever the stylesheet or the script does."""
    stamps = [
        int(path.stat().st_mtime)
        for name in VERSIONED
        if (path := config.root / "public" / name.lstrip("/")).is_file()
    ]
    return str(max(stamps)) if stamps else "0"


@lru_cache(maxsize=4 * len(PAGES))
def page(template: str, version: str = "") -> str:
    """One rendered page, with every ``{{ fragment }}`` composed in.

    Diagrams and the parts every page repeats live in their own files, so one
    can be edited without scrolling past the rest. They are resolved once,
    here, rather than on each request — keyed by ``version`` so a changed
    asset renders a fresh page rather than serving the cached one.
    """
    source = fragment(template)

    def resolve(match: re.Match) -> str:
        indent = match.group(1)
        body = fragment(match.group(2))
        return "\n".join(indent + line if line else line for line in body.split("\n"))

    rendered = INCLUDE.sub(resolve, source)

    if version:
        for asset in VERSIONED:
            rendered = rendered.replace(f'"{asset}"', f'"{asset}?v={version}"')

    return rendered


def homepage() -> str:
    """The rendered landing page."""
    return page(PAGES["/"])


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


async def page_route(config: Settings, template: str, request: Request) -> HTMLResponse:
    return HTMLResponse(page(template, asset_version(config)))


def register_routes(mcp: FastMCP, config: Settings) -> None:
    """Mount the doc pages, the stylesheet and script, the icons, and the fonts."""

    for path, template in PAGES.items():
        mcp.custom_route(path, methods=["GET"], name=f"page-{template}")(
            partial(page_route, config, template)
        )

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
