"""Per-tool scope enforcement — the second layer behind the JWT verifier.

FastMCP applies each tool's ``auth`` check when listing *and* when calling, so
a token that lacks a scope cannot even see the tools it does not cover.
"""

import pytest
from conftest import authenticated_as
from fastmcp.exceptions import NotFoundError

from radius.auth import scopes
from radius.config import Settings
from radius.server import create_server

pytestmark = pytest.mark.anyio

GUARDED_TOOLS = {
    "fetch_bookmarks",
    "recent_bookmarks",
    "list_authors",
    "bookmarks_by_author",
    "whoami",
}


@pytest.fixture
def server(keyed_config: Settings):
    return create_server(keyed_config)


async def visible(server) -> set[str]:
    return {tool.name for tool in await server.list_tools()}


async def test_all_tools_are_registered(server):
    registered = {tool.name for tool in await server._local_provider.list_tools()}

    assert registered == GUARDED_TOOLS


async def test_tools_are_visible_with_the_right_scope(server):
    with authenticated_as(scopes.READ_BOOKMARKS):
        assert await visible(server) == GUARDED_TOOLS


async def test_tools_are_hidden_from_a_token_without_the_scope(server):
    with authenticated_as():
        assert await visible(server) == set()

    with authenticated_as("some:other-scope"):
        assert await visible(server) == set()


async def test_tools_are_hidden_when_unauthenticated(server):
    assert await visible(server) == set()


async def test_calling_a_tool_without_the_scope_is_refused(server):
    """Denial reads as "unknown tool", so it does not leak what exists."""
    with authenticated_as(), pytest.raises(NotFoundError, match="whoami"):
        await server._call_tool_mcp("whoami", {})


async def test_calling_a_tool_with_the_scope_reaches_the_tool(server):
    with authenticated_as(scopes.READ_BOOKMARKS):
        _content, structured = await server._call_tool_mcp("whoami", {})

    assert structured["client"] == "claude-desktop"
    assert structured["scopes"] == [scopes.READ_BOOKMARKS]


async def test_every_registered_tool_declares_an_auth_check(server):
    """A tool added without `auth=` would be reachable by any valid token."""
    unguarded = [
        tool.name for tool in await server._local_provider.list_tools() if not tool.auth
    ]

    assert unguarded == []
