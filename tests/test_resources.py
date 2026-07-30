"""The ``bookmark://<id>`` resource — registration, scope, and what a read returns.

Resources are read by the client rather than called by the model, so what
matters here is that the URI resolves to JSON a client can cite, and that the
same scope guarding the tools also guards the read.
"""

import json
from functools import partial

import pytest
from conftest import authenticated_as
from fastmcp.exceptions import ResourceError

from radius.auth import scopes
from radius.config import Settings
from radius.db import connect
from radius.server import BOOKMARK_URI, create_server


pytestmark = pytest.mark.anyio


@pytest.fixture
def server(keyed_config: Settings, seeded_config: Settings, monkeypatch):
    """A server whose reads hit the seeded throwaway database."""
    monkeypatch.setattr(
        "radius.server.resources.connect", partial(connect, config=seeded_config)
    )
    return create_server(keyed_config)


async def templates(server) -> set[str]:
    listed = await server.list_resource_templates()
    return {template.uri_template for template in listed}


async def read(server, uri: str) -> dict:
    result = await server.read_resource(uri)
    return json.loads(result.contents[0].content)


async def test_the_bookmark_resource_is_registered(server):
    registered = await server._local_provider.list_resource_templates()

    assert {template.uri_template for template in registered} == {BOOKMARK_URI}


async def test_every_registered_resource_declares_an_auth_check(server):
    """A resource added without `auth=` would be readable by any valid token."""
    registered = await server._local_provider.list_resource_templates()

    assert [t.uri_template for t in registered if not t.auth] == []


async def test_the_resource_is_visible_with_the_right_scope(server):
    with authenticated_as(scopes.READ_BOOKMARKS):
        assert await templates(server) == {BOOKMARK_URI}


async def test_the_resource_is_hidden_without_the_scope(server):
    with authenticated_as("some:other-scope"):
        assert await templates(server) == set()

    assert await templates(server) == set()


async def test_reading_a_bookmark_returns_it_with_its_author(server):
    with authenticated_as(scopes.READ_BOOKMARKS):
        bookmark = await read(server, "bookmark://100")

    assert bookmark == {
        "id": "100",
        "display_name": "Ferris",
        "handle": "ferris",
        "content": "rust is blazing fast",
        "created_at": "2026-01-01",
    }


async def test_reading_an_unknown_bookmark_reports_the_miss(server):
    with authenticated_as(scopes.READ_BOOKMARKS):
        with pytest.raises(ResourceError, match="No bookmark found with id: 999"):
            await server.read_resource("bookmark://999")
