from typing import Literal

SearchMode = Literal["exact", "fuzzy"]

with open("queries/select_tweet_fts.sql", "r") as q:
    fts_query = q.read()
with open("queries/select_tweet_fuzzy.sql", "r") as q:
    fuzzy_query = q.read()

SEARCH_QUERIES: dict[SearchMode, str] = {
    "exact": fts_query,
    "fuzzy": fuzzy_query,
}
