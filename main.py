from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fields import Tweet
from typing import List
import sqlite3 as sql
from repository import SearchMode, SEARCH_QUERIES
from helper import fuzzy_score
from dotenv import load_dotenv
import os

load_dotenv()

JWKS_URI = os.getenv("JWKS_URI", "http://localhost:8000/.well-known/jwks.json")
JWT_ISSUER = os.getenv("JWT_ISSUER", "http://localhost:8000")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "mcp-production-api")

verifier = JWTVerifier(
    jwks_uri=JWKS_URI,
    issuer=JWT_ISSUER,
    audience=JWT_AUDIENCE,
)


mcp = FastMCP(name="Radius", auth=verifier)


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
