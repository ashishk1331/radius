"""RSA key material and the JWKS built from it.

radius is its own token issuer: one local RSA key pair signs every token, and
the public half is published as a JWKS document so verifiers — including this
server — can validate signatures without holding the private key.
"""

import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jwk

from radius.config import Settings, settings

ALGORITHM = "RS256"


class MissingKeyError(RuntimeError):
    """Raised when key material is needed but has not been generated yet."""

    def __init__(self, path: Path):
        super().__init__(
            f"no key found at {path}. Run `radius keys init` to generate one."
        )


def generate(config: Settings | None = None, *, force: bool = False) -> Path:
    """Create the key pair and JWKS on disk. Returns the JWKS path."""
    config = config or settings()

    if config.private_key_path.exists() and not force:
        raise FileExistsError(
            f"{config.private_key_path} already exists. "
            "Pass --force to replace it (this invalidates every issued token)."
        )

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    config.private_key_path.parent.mkdir(parents=True, exist_ok=True)
    config.private_key_path.write_bytes(private_pem)
    config.private_key_path.chmod(0o600)

    config.public_key_path.write_bytes(public_pem)

    config.jwks_path.parent.mkdir(parents=True, exist_ok=True)
    config.jwks_path.write_text(json.dumps(build_jwks(public_pem.decode()), indent=2))

    return config.jwks_path


def load_private_key(config: Settings | None = None) -> jwk.RSAKey:
    config = config or settings()
    if not config.private_key_path.exists():
        raise MissingKeyError(config.private_key_path)
    return jwk.RSAKey.import_key(config.private_key_path.read_text())


def load_public_pem(config: Settings | None = None) -> str:
    config = config or settings()
    if not config.public_key_path.exists():
        raise MissingKeyError(config.public_key_path)
    return config.public_key_path.read_text()


def key_id(key: jwk.RSAKey) -> str:
    """RFC 7638 thumbprint — stable across public/private halves of a pair."""
    return key.thumbprint()


def build_jwks(public_pem: str) -> dict:
    key = jwk.RSAKey.import_key(public_pem)
    return {
        "keys": [
            {
                **key.as_dict(private=False),
                "kid": key_id(key),
                "alg": ALGORITHM,
                "use": "sig",
            }
        ]
    }


def load_jwks(config: Settings | None = None) -> dict:
    """Read the published JWKS, rebuilding it from the public key if unusable."""
    config = config or settings()

    if config.jwks_path.exists():
        try:
            return json.loads(config.jwks_path.read_text())
        except json.JSONDecodeError:
            pass  # empty or truncated on disk — the key pair is the source of truth

    return build_jwks(load_public_pem(config))
