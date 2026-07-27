"""Runtime settings, resolved once from the environment.

Environment files are layered: ``.env.<RADIUS_ENV>`` first, then ``.env``.
Real environment variables always win over both.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent


def project_root() -> Path:
    """Where the data and key files live.

    Explicit ``RADIUS_HOME`` wins. Otherwise walk up from this file looking for
    the repo marker, so running from a subdirectory still finds the database.
    Falls back to the current directory when radius is installed as a wheel.
    """
    if override := os.getenv("RADIUS_HOME"):
        return Path(override).expanduser().resolve()

    for candidate in PACKAGE_ROOT.parents:
        if (candidate / "pyproject.toml").exists():
            return candidate

    return Path.cwd()


def _load_env_files(root: Path) -> str:
    env = os.getenv("RADIUS_ENV", "local")
    load_dotenv(root / f".env.{env}")
    load_dotenv(root / ".env")
    return env


def _path(root: Path, var: str, default: str) -> Path:
    value = Path(os.getenv(var, default)).expanduser()
    return value if value.is_absolute() else root / value


@dataclass(frozen=True)
class Settings:
    env: str
    root: Path

    db_path: Path

    # Turso is the corpus whenever a URL is set — the same database locally and
    # in production. Without one, radius uses db_path as a plain local file,
    # which is there for tests and offline work.
    turso_url: str | None
    turso_auth_token: str

    # Key material. The private key signs tokens; the public half is published
    # as a JWKS so any verifier can check them.
    private_key_path: Path
    public_key_path: Path
    jwks_path: Path

    # Inline PEM, for hosts with no writable filesystem to read a key file
    # from. Takes precedence over public_key_path when set.
    public_key_pem: str | None

    # When set, the verifier fetches keys over HTTP instead of reading
    # public_key_path. Use it in deployments where signing and serving are
    # separate processes; leave it unset locally.
    jwks_uri: str | None

    issuer: str
    audience: str
    token_ttl: int

    host: str
    port: int

    @classmethod
    def load(cls) -> "Settings":
        root = project_root()
        env = _load_env_files(root)
        issuer = os.getenv("JWT_ISSUER", "http://127.0.0.1:9000")

        return cls(
            env=env,
            root=root,
            db_path=_path(root, "RADIUS_DB_PATH", "bookmarks.db"),
            turso_url=os.getenv("TURSO_DATABASE_URL") or None,
            turso_auth_token=os.getenv("TURSO_AUTH_TOKEN", ""),
            private_key_path=_path(root, "RADIUS_PRIVATE_KEY", "keys/private.pem"),
            public_key_path=_path(root, "RADIUS_PUBLIC_KEY", "keys/public.pem"),
            jwks_path=_path(root, "RADIUS_JWKS_PATH", "public/.well-known/jwks.json"),
            public_key_pem=os.getenv("RADIUS_PUBLIC_KEY_PEM") or None,
            jwks_uri=os.getenv("JWKS_URI") or None,
            issuer=issuer,
            audience=os.getenv("JWT_AUDIENCE", "radius-mcp"),
            token_ttl=int(os.getenv("JWT_TOKEN_TTL", "3600")),
            host=os.getenv("RADIUS_HOST", "127.0.0.1"),
            port=int(os.getenv("RADIUS_PORT", "9000")),
        )


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings.load()
