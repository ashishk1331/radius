"""The ``recent_bookmarks`` tool — the size of the window and the shape of a row.

The tool takes no query and makes no ordering promise: it returns the top ``n``
records the table hands back. What is worth pinning is how ``n`` is bounded and
that every row arrives as a ``TweetResult`` with its author joined.
"""

from conftest import BASE_ID, add_bookmarks

from radius.config import Settings
from radius.models import TweetResult
from radius.server.tools import DEFAULT_TOP_K, MAX_TOP_K, recent_bookmarks


def test_recent_bookmarks_defaults_to_five(corpus: Settings):
    add_bookmarks(corpus, 10)

    assert len(recent_bookmarks()) == DEFAULT_TOP_K


def test_n_is_capped_so_a_large_ask_cannot_drain_the_table(corpus: Settings):
    add_bookmarks(corpus, 55)

    assert len(recent_bookmarks(n=1000)) == MAX_TOP_K


def test_n_below_the_default_still_returns_the_default(corpus: Settings):
    """The floor matches `fetch_bookmarks`: a smaller ask is widened, not honoured."""
    add_bookmarks(corpus, 10)

    assert len(recent_bookmarks(n=1)) == DEFAULT_TOP_K


def test_n_between_the_floor_and_the_cap_is_honoured(corpus: Settings):
    add_bookmarks(corpus, 30)

    assert len(recent_bookmarks(n=20)) == 20


def test_a_short_table_returns_everything_it_has(corpus: Settings):
    assert len(recent_bookmarks()) == 2


def test_every_row_returned_is_a_bookmark_from_the_table(corpus: Settings):
    add_bookmarks(corpus, 10)

    returned = {bookmark.id for bookmark in recent_bookmarks()}

    assert returned <= {"100", "200"} | {str(BASE_ID + n) for n in range(10)}
    assert len(returned) == DEFAULT_TOP_K


def test_each_row_maps_to_a_tweet_result_with_its_author(corpus: Settings):
    """`TweetResult`, not `SearchResult`: recency has no relevance score to report."""
    bookmarks = {bookmark.id: bookmark for bookmark in recent_bookmarks()}

    assert all(isinstance(each, TweetResult) for each in bookmarks.values())
    assert bookmarks["200"].content == "sqlite is a fine database"
    assert (bookmarks["200"].handle, bookmarks["200"].display_name) == (
        "ferris",
        "Ferris",
    )
    assert bookmarks["200"].created_at == "2026-01-02"
