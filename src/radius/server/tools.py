"""The MCP tools — the calls the model makes on its own initiative.

Every tool here is registered in :mod:`radius.server.app` behind a scope check.
Nothing in this module reads the token itself except :func:`whoami`, which
exists to report it.
"""

from fastmcp.server.dependencies import get_access_token

from radius import search
from radius.db import (
    SEARCH_EXACT,
    QUERIES,
    SEARCH_MODES,
    SELECT_ALL,
    SearchMode,
    connect,
)
from radius.db import query as run_query
from radius.models import SearchResult, TweetResult

MAX_TOP_K = 50
DEFAULT_TOP_K = 5


def fetch_bookmarks(
    query: str, search_mode: SearchMode = "exact", top_k: int = DEFAULT_TOP_K
) -> list[SearchResult]:
    """
    Fetch the top k similar tweets (saved bookmarks) to the passed query.

    Args:
        query: String to be search.
        search_mode: Strategy to use ('exact' or 'fuzzy'). Defaults to 'exact'.
        top_k: Top k similar to tweets/bookmarks. Defaults to 5. Maximum 50.
    """
    if search_mode not in SEARCH_MODES:
        raise ValueError(f"search_mode must be one of {sorted(SEARCH_MODES)}")

    limit = max(DEFAULT_TOP_K, min(top_k, MAX_TOP_K))

    with connect() as con:
        if search_mode == "exact":
            rows = run_query(con, SEARCH_EXACT, (query, limit))
        else:
            rows = search.rank_fuzzy(run_query(con, SELECT_ALL), query, limit)

    return [SearchResult.from_row(row) for row in rows]


def recent_bookmarks(n: int = DEFAULT_TOP_K) -> list[TweetResult]:
    """
    Fetch the recent `n` tweets (saved bookmarks).

    Args:
        n: Recent `n` tweets/bookmarks. Defaults to 5. Maximum 50.
    """
    limit = max(DEFAULT_TOP_K, min(n, MAX_TOP_K))

    with connect() as con:
        rows = run_query(con, QUERIES["SELECT"]["TWEET_RECENT_N"], (limit,))

    return [TweetResult.from_row(row) for row in rows]


def whoami() -> dict:
    """Report the client identity and scopes carried by the current token."""
    token = get_access_token()
    if token is None:  # unreachable while a verifier is configured
        raise RuntimeError("no access token in context")

    return {
        "client": token.claims.get("sub"),
        "scopes": list(token.scopes),
        "issuer": token.claims.get("iss"),
        "expires_at": token.claims.get("exp"),
    }
