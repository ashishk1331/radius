"""OAuth-style scopes carried in the ``scope`` claim of a radius token.

A token only unlocks the tools whose scopes it was minted with, so a client
that just needs search never receives anything broader.
"""

READ_BOOKMARKS = "bookmarks:read"

ALL_SCOPES: tuple[str, ...] = (READ_BOOKMARKS,)

# What `radius token issue` grants when no --scope is passed.
DEFAULT_SCOPES: tuple[str, ...] = (READ_BOOKMARKS,)


def validate(scopes: list[str]) -> list[str]:
    """Reject typos at mint time rather than at call time."""
    unknown = sorted(set(scopes) - set(ALL_SCOPES))
    if unknown:
        raise ValueError(
            f"unknown scope(s): {', '.join(unknown)}. "
            f"known scopes: {', '.join(ALL_SCOPES)}"
        )
    return scopes
