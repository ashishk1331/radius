"""The MCP resources — addressable bookmarks a client reads by URI.

Where a tool is called by the model, a resource is fetched by the client, so
``bookmark://<id>`` is what makes a bookmark citable and re-readable after its
search result has scrolled out of context. Returning a plain ``dict`` lets
FastMCP serialise it as ``application/json``.
"""

from radius.db import QUERIES, connect
from radius.db import query as run_query

BOOKMARK_URI = "bookmark://{id}"


def get_bookmark(id: str) -> dict:
    """
    Fetch a single saved bookmark by id, with its author.

    Args:
        id: Id of the bookmark to fetch.
    """
    with connect() as con:
        rows = run_query(con, QUERIES["SELECT"]["TWEET"], (id,))

    if not rows:
        raise ValueError(f"No bookmark found with id: {id}")

    return rows[0]
