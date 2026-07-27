"""End-to-end checks that the MCP endpoint is actually guarded."""

import httpx
import pytest

from radius.auth import tokens
from radius.config import Settings
from radius.server import create_server

pytestmark = pytest.mark.anyio

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}

ACCEPT = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
async def client(keyed_config: Settings):
    app = create_server(keyed_config).http_app()
    # The streamable-HTTP session manager only runs inside the app lifespan.
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://radius.test",
            follow_redirects=True,
        ) as http_client,
    ):
        yield http_client


async def initialize(client: httpx.AsyncClient, token: str | None = None):
    headers = dict(ACCEPT)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return await client.post("/mcp/", json=INITIALIZE, headers=headers)


async def test_request_without_a_token_is_rejected(client):
    response = await initialize(client)

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


async def test_request_with_a_garbage_token_is_rejected(client):
    assert (await initialize(client, "not-a-jwt")).status_code == 401


async def test_request_with_an_expired_token_is_rejected(client, keyed_config):
    expired = tokens.issue("claude-desktop", ttl=-60, config=keyed_config)

    assert (await initialize(client, expired)).status_code == 401


async def test_request_with_a_valid_token_is_accepted(client, keyed_config):
    token = tokens.issue("claude-desktop", config=keyed_config)

    assert (await initialize(client, token)).status_code == 200


async def test_jwks_and_health_are_public(client):
    jwks = await client.get("/.well-known/jwks.json")
    health = await client.get("/health")

    assert jwks.status_code == 200
    assert jwks.json()["keys"][0]["kty"] == "RSA"
    assert health.status_code == 200
