"""SQL loaded from ``db/sql`` so queries stay editable as real .sql files."""

from pathlib import Path
from typing import Literal

SQL_DIR = Path(__file__).resolve().parent / "sql"
MIGRATION_PATH = Path(__file__).resolve().parent / "migration.sql"

SearchMode = Literal["exact", "fuzzy"]
SEARCH_MODES: tuple[SearchMode, ...] = ("exact", "fuzzy")


def read(name: str) -> str:
    return (SQL_DIR / f"{name}.sql").read_text()


def migration() -> str:
    return MIGRATION_PATH.read_text()


# `exact` ranks in SQL via FTS5. `fuzzy` selects candidates here and scores them
# in Python — see radius.search for why.
SEARCH_EXACT = read("select_tweet_fts")
SELECT_ALL = read("select_tweet_all")

QUERIES = {
    "UPSERT": {
        "TWEET": read("upsert_tweet"),
        "AUTHOR": read("upsert_author"),
        "MEDIA": read("upsert_media"),
    },
    "SELECT": {
        "AUTHOR": read("select_author"),
        "AUTHOR_ALL": read("select_author_all"),
        "AUTHOR_N": read("select_author_n"),
        "TWEET": read("select_tweet"),
        "TWEET_RECENT_N": read("select_tweet_recent"),
        "TWEET_BY_AUTHOR": read("select_tweet_by_author"),
    },
}
