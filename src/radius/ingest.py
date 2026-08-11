"""Bookmark export -> SQLite upserts."""

import json
from pathlib import Path

from radius.config import Settings, settings
from radius.db import QUERIES, connect, migrate
from radius.embed import embed_tweets

STORE = "bookmarks.jsonl"


def load_bookmarks(path: Path) -> list[dict]:
    """Read an export as a flat list of tweets.

    ``.jsonl`` is what :mod:`radius.sync` writes — one tweet per line, each
    carrying the id of the tweet it replies to. Anything else is read as the
    older shape, a single object with a ``data`` array.
    """
    with open(path, "r", encoding="utf-8") as file:
        if path.suffix == ".jsonl":
            return [json.loads(line) for line in file if line.strip()]
        return json.load(file)["data"]


def _edges(tweet: dict) -> tuple[str | None, str | None]:
    """The tweet this one answers, and the one it quotes."""
    return tweet.get("in_reply_to"), (tweet.get("quotedTweet") or {}).get("id")


def _held(edge: str | None, present: set[str]) -> str | None:
    """An edge only if this export carries what it points at.

    Both columns are foreign keys onto ``tweets(id)`` and libSQL enforces
    those, so one naming a tweet outside the export would abort the whole
    batch. Losing an edge costs less than losing every row.
    """
    return edge if edge in present else None


def _in_dependency_order(bookmarks: list[dict]) -> list[dict]:
    """Referenced tweets before the ones naming them.

    Within a single sync a parent is always written before its replies, but a
    bookmark and the tweet it quotes can land in the store runs apart, in
    either order. The foreign keys are checked per row as it is inserted, so
    the order the file happens to be in is not something to rely on.
    """
    by_id = {each["id"]: each for each in bookmarks}
    ordered: list[dict] = []
    placed: set[str] = set()

    def place(tweet: dict, seen: set[str]) -> None:
        if tweet["id"] in placed or tweet["id"] in seen:
            return
        seen.add(tweet["id"])
        for edge in _edges(tweet):
            if edge in by_id:
                place(by_id[edge], seen)
        placed.add(tweet["id"])
        ordered.append(tweet)

    for each in bookmarks:
        place(each, set())
    return ordered


def ingest(
    source: Path | None = None,
    db_path: Path | None = None,
    config: Settings | None = None,
) -> int:
    """Upsert every bookmark in ``source``. Returns the number of tweets seen.

    Writes go straight to Turso when it is configured, so ingested bookmarks are
    live for every reader the moment this returns. Each statement is a network
    round trip, which is why a backfill takes minutes and an incremental run
    takes seconds.
    """
    config = config or settings()
    source = source or config.root / STORE
    bookmarks = load_bookmarks(source)

    migrate(db_path, config)

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

    embeddings = dict(zip(
        (each["id"] for each in bookmarks),
        embed_tweets([each["text"] for each in bookmarks]),
    ))
    present = {each["id"] for each in bookmarks}

    tweets = [
        (
            each["id"],
            each["author"]["id"],
            each["text"],
            each["createdAt"],
            _held(replies_to, present),
            _held(quotes, present),
            embeddings[each["id"]],
        )
        for each in _in_dependency_order(bookmarks)
        for replies_to, quotes in [_edges(each)]
    ]
    media = [
        (each["id"], item["url"], item["type"])
        for each in bookmarks
        for item in each.get("media", [])
    ]

    with connect(db_path, config) as con:
        # Authors first: tweets carry a foreign key to them.
        con.executemany(QUERIES["UPSERT"]["AUTHOR"], authors)
        con.executemany(QUERIES["UPSERT"]["TWEET"], tweets)
        if media:
            con.executemany(QUERIES["UPSERT"]["MEDIA"], media)

    return len(bookmarks)


if __name__ == "__main__":
    print(f"ingested {ingest()} bookmarks")
