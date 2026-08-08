"""The homepage and the static files it pulls in."""

import httpx
import pytest

from radius.config import Settings
from radius.server import create_server, web

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client(keyed_config: Settings):
    public = keyed_config.root / "public"
    public.mkdir(parents=True, exist_ok=True)
    (public / "styles.css").write_text("body { color: red; }")
    (public / "app.js").write_text("const a = 1;")

    app = create_server(keyed_config).http_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://radius.test",
            follow_redirects=True,
        ) as http_client,
    ):
        yield http_client


def test_every_fragment_is_composed_into_the_page():
    page = web.homepage()

    assert "{{" not in page
    assert page.count("</svg>") == 2
    assert 'viewBox="0 0 776 78"' in page
    assert 'viewBox="0 0 776 198"' in page


def test_fragments_keep_the_indentation_of_their_placeholder():
    page = web.homepage()

    assert "\n          <svg " in page


def test_a_fragment_cannot_escape_the_static_directory():
    with pytest.raises(FileNotFoundError):
        web.fragment("../../../etc/passwd")


async def test_the_homepage_is_public(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "</svg>" in response.text


async def test_the_stylesheet_and_script_are_public(client):
    styles = await client.get("/styles.css")
    script = await client.get("/app.js")

    assert styles.status_code == 200
    assert "text/css" in styles.headers["content-type"]
    assert script.status_code == 200
    assert styles.headers["cache-control"] == web.PAGE_CACHE
