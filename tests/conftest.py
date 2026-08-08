from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

import pytest
from fastmcp.server.auth import AccessToken
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from radius.auth import keys
from radius.config import MEMORY, Settings
from radius.db import QUERIES, connect, migrate, reset_memory


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


@pytest.fixture(autouse=True)
def fresh_memory_db():
    """The in-memory database outlives a connection, so it must not outlive a test."""
    reset_memory()
    yield
    reset_memory()


@pytest.fixture
def config(tmp_path) -> Settings:
    """Settings pointed entirely at a throwaway directory, with the corpus in RAM."""
    return Settings(
        env="test",
        root=tmp_path,
        db_path=Path(MEMORY),
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


@pytest.fixture
def corpus(seeded_config: Settings, monkeypatch) -> Settings:
    """The seeded corpus, with the tools pointed at it.

    Every tool calls `connect()` with no config, so the patch is what stops
    them reaching the database named by the environment.
    """
    monkeypatch.setattr(
        "radius.server.tools.connect", partial(connect, config=seeded_config)
    )
    return seeded_config


@pytest.fixture
def empty_corpus(config: Settings, monkeypatch) -> Settings:
    """Migrated but unseeded — the state before a first ingest."""
    migrate(config=config)
    monkeypatch.setattr("radius.server.tools.connect", partial(connect, config=config))
    return config


BASE_TIME = datetime(2026, 3, 2, 12, 0, 0)
BASE_ID = 2080000000000000000
TWITTER_TIME = "%a %b %d %H:%M:%S +0000 %Y"


def add_authors(config: Settings, authors: list[tuple]) -> None:
    """Insert authors as `ingest` does — id, handle, display_name, avatar."""
    with connect(config=config) as con:
        for author in authors:
            con.execute(QUERIES["UPSERT"]["AUTHOR"], author)


def add_bookmarks(
    config: Settings, count: int, author_id: str = "1", first: int = 0
) -> None:
    """Add ``count`` bookmarks for one author, stamped as `ingest` stores them.

    ``first`` offsets the generated ids so two authors can be filled without
    colliding on the tweet primary key.
    """
    with connect(config=config) as con:
        for n in range(first, first + count):
            stamp = (BASE_TIME + timedelta(days=n)).strftime(TWITTER_TIME)
            con.execute(
                QUERIES["UPSERT"]["TWEET"],
                (str(BASE_ID + n), author_id, f"bookmark {n}", stamp, None, None),
            )
