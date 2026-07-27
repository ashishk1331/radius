"""Minting and inspecting radius access tokens."""

import secrets
import time

from joserfc import jwk, jwt
from joserfc.errors import JoseError

from radius.auth import keys
from radius.auth import scopes as scopes_module
from radius.config import Settings, settings


def issue(
    subject: str,
    scopes: list[str] | None = None,
    ttl: int | None = None,
    config: Settings | None = None,
) -> str:
    """Sign a token for ``subject`` (a client name, e.g. "claude-desktop")."""
    config = config or settings()
    granted = scopes_module.validate(list(scopes or scopes_module.DEFAULT_SCOPES))
    lifetime = ttl if ttl is not None else config.token_ttl

    key = keys.load_private_key(config)
    now = int(time.time())

    claims = {
        "sub": subject,
        "iss": config.issuer,
        "aud": config.audience,
        "iat": now,
        "exp": now + lifetime,
        "jti": secrets.token_urlsafe(16),
        "scope": " ".join(granted),
    }

    return jwt.encode({"alg": keys.ALGORITHM, "kid": keys.key_id(key)}, claims, key)


def inspect(token: str, config: Settings | None = None) -> dict:
    """Verify a token locally and return its claims. Raises on any failure."""
    config = config or settings()
    public_key = jwk.RSAKey.import_key(keys.load_public_pem(config))

    try:
        decoded = jwt.decode(token, public_key, algorithms=[keys.ALGORITHM])
    except JoseError as exc:
        raise ValueError(f"token is not valid: {exc}") from exc

    registry = jwt.JWTClaimsRegistry(
        iss={"essential": True, "value": config.issuer},
        aud={"essential": True, "value": config.audience},
        exp={"essential": True},
        sub={"essential": True},
    )
    registry.validate(decoded.claims)

    return decoded.claims
