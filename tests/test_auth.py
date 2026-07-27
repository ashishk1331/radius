import time

import pytest
from joserfc import jwt
from joserfc.errors import InvalidClaimError

from radius.auth import keys, scopes, tokens, verifier
from radius.config import Settings


def test_keys_init_writes_private_public_and_jwks(config: Settings):
    jwks_path = keys.generate(config)

    assert config.private_key_path.exists()
    assert config.public_key_path.exists()
    assert jwks_path.exists()

    jwk_entry = keys.load_jwks(config)["keys"][0]
    assert jwk_entry["kty"] == "RSA"
    assert jwk_entry["alg"] == "RS256"
    assert "d" not in jwk_entry, "private exponent must never reach the JWKS"


def test_keys_init_refuses_to_clobber_without_force(keyed_config: Settings):
    with pytest.raises(FileExistsError):
        keys.generate(keyed_config)

    keys.generate(keyed_config, force=True)  # explicit override is allowed


def test_issued_token_round_trips(keyed_config: Settings):
    token = tokens.issue("claude-desktop", config=keyed_config)
    claims = tokens.inspect(token, config=keyed_config)

    assert claims["sub"] == "claude-desktop"
    assert claims["iss"] == keyed_config.issuer
    assert claims["aud"] == keyed_config.audience
    assert claims["scope"] == scopes.READ_BOOKMARKS
    assert claims["exp"] > time.time()


def test_unknown_scopes_are_rejected_at_mint_time(keyed_config: Settings):
    with pytest.raises(ValueError, match="unknown scope"):
        tokens.issue("claude-desktop", ["bookmarks:delete"], config=keyed_config)


def test_inspect_rejects_a_token_signed_by_another_key(keyed_config: Settings, config):
    token = tokens.issue("claude-desktop", config=keyed_config)
    keys.generate(keyed_config, force=True)  # rotate

    with pytest.raises(ValueError, match="not valid"):
        tokens.inspect(token, config=keyed_config)


def test_inspect_rejects_a_foreign_audience(keyed_config: Settings):
    key = keys.load_private_key(keyed_config)
    now = int(time.time())
    forged = jwt.encode(
        {"alg": "RS256", "kid": keys.key_id(key)},
        {
            "sub": "attacker",
            "iss": keyed_config.issuer,
            "aud": "some-other-service",
            "iat": now,
            "exp": now + 60,
        },
        key,
    )

    with pytest.raises(InvalidClaimError, match="aud"):
        tokens.inspect(forged, config=keyed_config)


def test_verifier_uses_local_public_key_when_no_jwks_uri(keyed_config: Settings):
    built = verifier.build(keyed_config)

    assert built.jwks_uri is None
    assert built.issuer == keyed_config.issuer
    assert built.audience == keyed_config.audience


def test_verifier_prefers_jwks_uri_when_set(keyed_config: Settings):
    remote = Settings(**{**keyed_config.__dict__, "jwks_uri": "https://iss/jwks.json"})

    built = verifier.build(remote)

    assert built.jwks_uri == "https://iss/jwks.json"


def test_missing_key_material_gives_an_actionable_error(config: Settings):
    with pytest.raises(keys.MissingKeyError, match="radius keys init"):
        tokens.issue("claude-desktop", config=config)
