"""A local note of which tokens have been issued.

Verification stays stateless. A request is accepted on its signature and its
claims alone, and nothing here is read to serve one — so this is the
operator's own record of who holds a token and when it lapses, not a list of
what the server would honour. Deleting a line revokes nothing, and a token
minted before this file existed will never appear in it.

It sits beside the key material rather than in the corpus. The corpus is
Turso, shared by every deployment and falling back to ``:memory:``, so a
record kept there would be either published or silently discarded.

The token itself is never written. Only the claims that say what it is are:
the subject, the scopes, and the two timestamps.
"""

import json

from radius.config import Settings, settings

FIELDS = ("jti", "sub", "scope", "iat", "exp")


def record(claims: dict, config: Settings | None = None) -> None:
    """Append one issued token's claims, creating the ledger if needed."""
    config = config or settings()
    config.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    entry = json.dumps({field: claims.get(field) for field in FIELDS})
    with open(config.ledger_path, "a", encoding="utf-8") as file:
        file.write(f"{entry}\n")


def read(config: Settings | None = None) -> list[dict]:
    """Every recorded issue, oldest first. No ledger reads as none."""
    config = config or settings()
    if not config.ledger_path.exists():
        return []

    with open(config.ledger_path, "r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]
