"""The JWT verifier that guards the MCP server.

FastMCP applies this to every MCP request before a tool is ever reached: a
request without a valid bearer token gets a 401 and never enters tool code.
Per-tool scope checks (see ``radius.server``) run afterwards, so a valid token
still only opens the tools its scopes cover.
"""

from fastmcp.server.auth.providers.jwt import JWTVerifier

from radius.auth import keys
from radius.config import Settings, settings


def build(config: Settings | None = None) -> JWTVerifier:
    """Construct the verifier from whichever key source is configured.

    ``JWKS_URI`` takes precedence, for deployments where the signer and the
    server are different processes. Otherwise the local public key is used
    directly, which avoids the server making an HTTP call to itself.
    """
    config = config or settings()

    common = {
        "issuer": config.issuer,
        "audience": config.audience,
        "algorithm": keys.ALGORITHM,
    }

    if config.jwks_uri:
        return JWTVerifier(jwks_uri=config.jwks_uri, **common)

    return JWTVerifier(public_key=keys.load_public_pem(config), **common)
