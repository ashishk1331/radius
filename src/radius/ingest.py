"""Raw bookmark JSON -> SQLite upserts."""

import json
from pathlib import Path

from radius.config import settings
from radius.db import QUERIES, connect, migrate


def load_bookmarks(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def ingest(source: Path | None = None, db_path: Path | None = None) -> int:
    """Upsert every bookmark in ``source``. Returns the number of tweets seen."""
    source = source or settings().root / "bookmarks.json"
    bookmarks = load_bookmarks(source)["data"]

    migrate(db_path)

    with connect(db_path) as con:
        # Authors first: tweets carry a foreign key to them.
        for each in bookmarks:
            author = each["author"]
            con.execute(
                QUERIES["UPSERT"]["AUTHOR"],
                (
                    author["id"],
                    author["screenName"],
                    author["name"],
                    author["profileImageUrl"],
                ),
            )

        for each in bookmarks:
            con.execute(
                QUERIES["UPSERT"]["TWEET"],
                (
                    each["id"],
                    each["author"]["id"],
                    each["text"],
                    each["createdAt"],
                    None,
                    None,
                ),
            )

            for media in each.get("media", []):
                con.execute(
                    QUERIES["UPSERT"]["MEDIA"],
                    (each["id"], media["url"], media["type"]),
                )

    return len(bookmarks)


if __name__ == "__main__":
    print(f"ingested {ingest()} bookmarks")
