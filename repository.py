from typing import Literal
from helper import read_query

SearchMode = Literal["exact", "fuzzy"]

SEARCH_QUERIES: dict[SearchMode, str] = {
    "exact": read_query("select_tweet_fts"),
    "fuzzy": read_query("select_tweet_fuzzy"),
}

KEY_QUERIES = {
    "insert": read_query("insert_key"),
    "select": read_query("select_key"),
    "select-all": read_query("select_key_all"),
    "revoke": read_query("update_key_revoke"),
    "get-hash": read_query("select_key_hash"),
}

QUERIES = {
    "UPSERT": {
        "TWEET": read_query("upsert_tweet"),
        "AUTHOR": read_query("upsert_author"),
        "MEDIA": read_query("upsert_media"),
    },
    "SELECT": {
        "AUTHOR": read_query("select_author"),
    },
}
