from fastmcp import FastMCP
from fields import Tweet
from typing import List
import sqlite3 as sql
from repository import SearchMode, SEARCH_QUERIES
from helper import fuzzy_score


mcp = FastMCP("Radius")


@mcp.tool
def fetch_bookmarks(
    query: str, search_mode: SearchMode = "exact", top_k: int = 5
) -> List[Tweet]:
    """
    Fetch the top k similar tweets (saved bookmarks) to the passed query.

    Args:
        query: String to be search.
        search_mode: Strategy to use ('exact' or 'fuzzy'). Defaults to 'exact'.
        top_k: Top k similar to tweets/bookmarks. Defaults to 5.
    """
    with sql.connect("bookmarks.db") as con:
        con.create_function("FUZZY_SCORE", 2, fuzzy_score)
        con.row_factory = sql.Row
        cur = con.execute(SEARCH_QUERIES[search_mode], (query, top_k))
        results = []
        for row in cur.fetchall():
            results.append(dict(row))
        return results


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=9000)
