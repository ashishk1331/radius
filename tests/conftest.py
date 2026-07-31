from contextlib import contextmanager

import pytest
from fastmcp.server.auth import AccessToken
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from radius.auth import keys
from radius.config import Settings
from radius.db import QUERIES, connect, migrate


@contextmanager
def authenticated_as(*granted: str, subject: str = "claude-desktop"):
    """Put an access token with ``granted`` scopes into the request context."""
    token = AccessToken(
        token="opaque",
        client_id=subject,
        scopes=list(granted),
        claims={"sub": subject, "iss": "http://test-issuer", "exp": 2**31},
    )
    reset = auth_context_var.set(AuthenticatedUser(token))
    try:
        yield
    finally:
        auth_context_var.reset(reset)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def config(tmp_path) -> Settings:
    """Settings pointed entirely at a throwaway directory."""
    return Settings(
        env="test",
        root=tmp_path,
        db_path=tmp_path / "bookmarks.db",
        turso_url=None,
        turso_auth_token="",
        private_key_path=tmp_path / "keys" / "private.pem",
        public_key_path=tmp_path / "keys" / "public.pem",
        jwks_path=tmp_path / "public" / ".well-known" / "jwks.json",
        public_key_pem=None,
        jwks_uri=None,
        issuer="http://test-issuer",
        audience="radius-test",
        token_ttl=3600,
        host="127.0.0.1",
        port=9000,
    )


@pytest.fixture
def keyed_config(config: Settings) -> Settings:
    keys.generate(config)
    return config


@pytest.fixture
def seeded_config(config: Settings) -> Settings:
    """A local libSQL database with two bookmarks in it."""
    migrate(config=config)
    with connect(config=config) as con:
        con.execute(
            QUERIES["UPSERT"]["AUTHOR"], ("1", "ferris", "Ferris", "http://img")
        )
        con.execute(
            QUERIES["UPSERT"]["TWEET"],
            ("100", "1", "rust is blazing fast", "2026-01-01", None, None),
        )
        con.execute(
            QUERIES["UPSERT"]["TWEET"],
            ("200", "1", "sqlite is a fine database", "2026-01-02", None, None),
        )
    return config
