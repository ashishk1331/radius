"""The documentation pages and the static files they pull in.

The site is four pages composed from shared fragments, so what matters is that
every page resolves its includes, that each one carries the nav to reach the
others, and that the split did not leave a diagram behind.
"""

import os
import re

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


@pytest.mark.parametrize("template", sorted(web.PAGES.values()))
def test_every_fragment_is_composed_into_every_page(template):
    assert "{{" not in web.page(template)


@pytest.mark.parametrize("template", sorted(web.PAGES.values()))
def test_every_page_carries_the_shared_parts(template):
    """A page that forgot an include would render without a way out of itself."""
    rendered = web.page(template)

    assert '<link rel="stylesheet" href="/styles.css">' in rendered
    assert 'class="brand"' in rendered
    assert "<nav " in rendered
    assert "<footer " in rendered


@pytest.mark.parametrize("template", sorted(web.PAGES.values()))
def test_every_page_ends_with_the_help_section(template):
    """Help is shared rather than living on one page a reader may never reach."""
    rendered = web.page(template)

    assert 'id="help"' in rendered
    assert "github.com/ashishk1331/radius/issues/new" in rendered


@pytest.mark.parametrize("template", sorted(web.PAGES.values()))
def test_every_page_has_a_pager(template):
    assert 'class="links pager"' in web.page(template)


def test_the_pager_puts_back_before_next():
    """Source order is what places them: back on the left, next on the right."""
    rendered = web.page(web.PAGES["/tools"])
    pager = rendered.split('class="links pager"')[1]

    back = pager.index('href="/start"')
    forward = pager.index('href="/operate"')

    assert back < forward


def test_the_first_and_last_pages_only_go_one_way():
    home = web.page(web.PAGES["/"]).split('class="links pager"')[1]
    operate = web.page(web.PAGES["/operate"]).split('class="links pager"')[1]

    assert "&rarr;" in home and "&larr;" not in home
    assert "&larr;" in operate and "&rarr;" not in operate


@pytest.mark.parametrize("template", sorted(web.PAGES.values()))
def test_every_page_shows_the_logo_beside_the_wordmark(template):
    """Including the landing page, which also carries the larger hero emblem."""
    assert '<span class="mark"' in web.page(template)


@pytest.mark.parametrize("template", sorted(web.PAGES.values()))
def test_every_page_links_to_every_other_page(template):
    rendered = web.page(template)

    for path in web.PAGES:
        assert f'href="{path}"' in rendered


def test_both_diagrams_survived_the_split():
    """One diagram per page now, so neither is reachable from the other.

    Counted by viewBox rather than by `</svg>`, which also matches icons.
    """
    home = web.page(web.PAGES["/"])
    operate = web.page(web.PAGES["/operate"])

    assert home.count('viewBox="0 0 776 78"') == 1
    assert 'viewBox="0 0 776 198"' not in home

    assert operate.count('viewBox="0 0 776 198"') == 1
    assert 'viewBox="0 0 776 78"' not in operate


def test_fragments_keep_the_indentation_of_their_placeholder():
    assert "\n          <svg " in web.homepage()


def test_a_fragment_cannot_escape_the_static_directory():
    with pytest.raises(FileNotFoundError):
        web.fragment("../../../etc/passwd")


async def test_every_page_is_public(client):
    for path in web.PAGES:
        response = await client.get(path)

        assert response.status_code == 200, path
        assert "text/html" in response.headers["content-type"], path


async def test_the_homepage_still_answers_at_the_root(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert "</svg>" in response.text


async def test_an_unknown_page_is_not_served(client):
    """Only the mapped paths render, so a template cannot be named by URL."""
    response = await client.get("/index.html")

    assert response.status_code == 404


async def test_the_asset_urls_carry_a_version(client):
    """Without it a refresh renders new HTML against a still-cached stylesheet."""
    response = await client.get("/")

    assert re.search(r'href="/styles\.css\?v=\d+"', response.text)
    assert re.search(r'src="/app\.js\?v=\d+"', response.text)


async def test_the_version_changes_when_the_stylesheet_does(client, keyed_config):
    """An edit gives the file a newer mtime, which is what moves the token."""
    before = await client.get("/")

    styles = keyed_config.root / "public" / "styles.css"
    styles.write_text("body { color: blue; }")
    os.utime(styles, (2**31, 2**31))

    after = await client.get("/")

    assert before.text != after.text
    assert "?v=2147483648" in after.text


async def test_a_versioned_asset_still_serves(client):
    response = await client.get("/styles.css?v=123")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


async def test_the_stylesheet_and_script_are_public(client):
    styles = await client.get("/styles.css")
    script = await client.get("/app.js")

    assert styles.status_code == 200
    assert "text/css" in styles.headers["content-type"]
    assert script.status_code == 200
    assert styles.headers["cache-control"] == web.PAGE_CACHE
