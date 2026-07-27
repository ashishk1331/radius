"""SQL loaded from ``db/sql`` so queries stay editable as real .sql files."""

from pathlib import Path
from typing import Literal

SQL_DIR = Path(__file__).resolve().parent / "sql"
MIGRATION_PATH = Path(__file__).resolve().parent / "migration.sql"

SearchMode = Literal["exact", "fuzzy"]


def read(name: str) -> str:
    return (SQL_DIR / f"{name}.sql").read_text()


def migration() -> str:
    return MIGRATION_PATH.read_text()


SEARCH_QUERIES: dict[SearchMode, str] = {
    "exact": read("select_tweet_fts"),
    "fuzzy": read("select_tweet_fuzzy"),
}

QUERIES = {
    "UPSERT": {
        "TWEET": read("upsert_tweet"),
        "AUTHOR": read("upsert_author"),
        "MEDIA": read("upsert_media"),
    },
    "SELECT": {
        "AUTHOR": read("select_author"),
    },
}
