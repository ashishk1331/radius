import pytest

from radius.auth import keys
from radius.config import Settings


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
        private_key_path=tmp_path / "keys" / "private.pem",
        public_key_path=tmp_path / "keys" / "public.pem",
        jwks_path=tmp_path / "public" / ".well-known" / "jwks.json",
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
