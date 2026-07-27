"""Raw bookmark JSON -> SQLite upserts."""

import json
from pathlib import Path

from radius.config import settings
from radius.db import QUERIES, connect, migrate


def load_bookmarks(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def ingest(source: Path | None = None, db_path: Path | None = None) -> int:
    """Upsert every bookmark in ``source``. Returns the number of tweets seen.

    Writes go straight to Turso when it is configured, so ingested bookmarks are
    live for every reader the moment this returns. Each statement is a network
    round trip, which is why a backfill takes minutes and an incremental run
    takes seconds.
    """
    source = source or settings().root / "bookmarks.json"
    bookmarks = load_bookmarks(source)["data"]

    migrate(db_path)

    # Batched rather than row-by-row: against Turso every statement is a
    # round trip to the primary (~300ms), so 600 individual upserts take
    # minutes. executemany collapses each group into one.
    authors = [
        (
            each["author"]["id"],
            each["author"]["screenName"],
            each["author"]["name"],
            each["author"]["profileImageUrl"],
        )
        for each in bookmarks
    ]
    tweets = [
        (
            each["id"],
            each["author"]["id"],
            each["text"],
            each["createdAt"],
            None,
            None,
        )
        for each in bookmarks
    ]
    media = [
        (each["id"], item["url"], item["type"])
        for each in bookmarks
        for item in each.get("media", [])
    ]

    with connect(db_path) as con:
        # Authors first: tweets carry a foreign key to them.
        con.executemany(QUERIES["UPSERT"]["AUTHOR"], authors)
        con.executemany(QUERIES["UPSERT"]["TWEET"], tweets)
        if media:
            con.executemany(QUERIES["UPSERT"]["MEDIA"], media)

    return len(bookmarks)


if __name__ == "__main__":
    print(f"ingested {ingest()} bookmarks")
