"""The ``recent_bookmarks`` tool — the size of the window and the shape of a row.

The tool takes no query and makes no ordering promise: it returns the top ``n``
records the table hands back. What is worth pinning is how ``n`` is bounded and
that every row arrives as a ``TweetResult`` with its author joined.
"""

from datetime import datetime, timedelta
from functools import partial

import pytest

from radius.config import Settings
from radius.db import QUERIES, connect
from radius.models import TweetResult
from radius.server.tools import DEFAULT_TOP_K, MAX_TOP_K, recent_bookmarks


@pytest.fixture
def seeded(seeded_config: Settings, monkeypatch) -> Settings:
    """`recent_bookmarks` calls `connect()` with no config, so it is patched here."""
    monkeypatch.setattr(
        "radius.server.tools.connect", partial(connect, config=seeded_config)
    )
    return seeded_config


BASE_TIME = datetime(2026, 3, 2, 12, 0, 0)
BASE_ID = 2080000000000000000
TWITTER_TIME = "%a %b %d %H:%M:%S +0000 %Y"


def add_bookmarks(config: Settings, count: int) -> None:
    """Add ``count`` bookmarks, stamped in the same format `ingest` stores."""
    with connect(config=config) as con:
        for n in range(count):
            stamp = (BASE_TIME + timedelta(days=n)).strftime(TWITTER_TIME)
            con.execute(
                QUERIES["UPSERT"]["TWEET"],
                (str(BASE_ID + n), "1", f"bookmark {n}", stamp, None, None),
            )


def test_recent_bookmarks_defaults_to_five(seeded: Settings):
    add_bookmarks(seeded, 10)

    assert len(recent_bookmarks()) == DEFAULT_TOP_K


def test_n_is_capped_so_a_large_ask_cannot_drain_the_table(seeded: Settings):
    add_bookmarks(seeded, 55)

    assert len(recent_bookmarks(n=1000)) == MAX_TOP_K


def test_n_below_the_default_still_returns_the_default(seeded: Settings):
    """The floor matches `fetch_bookmarks`: a smaller ask is widened, not honoured."""
    add_bookmarks(seeded, 10)

    assert len(recent_bookmarks(n=1)) == DEFAULT_TOP_K


def test_n_between_the_floor_and_the_cap_is_honoured(seeded: Settings):
    add_bookmarks(seeded, 30)

    assert len(recent_bookmarks(n=20)) == 20


def test_a_short_table_returns_everything_it_has(seeded: Settings):
    assert len(recent_bookmarks()) == 2


def test_every_row_returned_is_a_bookmark_from_the_table(seeded: Settings):
    add_bookmarks(seeded, 10)

    returned = {bookmark.id for bookmark in recent_bookmarks()}

    assert returned <= {"100", "200"} | {str(BASE_ID + n) for n in range(10)}
    assert len(returned) == DEFAULT_TOP_K


def test_each_row_maps_to_a_tweet_result_with_its_author(seeded: Settings):
    """`TweetResult`, not `SearchResult`: recency has no relevance score to report."""
    bookmarks = {bookmark.id: bookmark for bookmark in recent_bookmarks()}

    assert all(isinstance(each, TweetResult) for each in bookmarks.values())
    assert bookmarks["200"].content == "sqlite is a fine database"
    assert (bookmarks["200"].handle, bookmarks["200"].display_name) == (
        "ferris",
        "Ferris",
    )
    assert bookmarks["200"].created_at == "2026-01-02"
