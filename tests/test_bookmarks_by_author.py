"""The ``bookmarks_by_author`` tool — one author's saved bookmarks, bounded by ``k``.

The filter is the whole point of this tool, so what matters is that it selects
on the handle a caller would actually name, that it excludes everyone else, and
that an unmatched handle comes back empty rather than falling through to the
rest of the corpus.
"""

from conftest import BASE_ID, add_authors, add_bookmarks

from radius.config import Settings
from radius.models import TweetResult
from radius.server.tools import DEFAULT_TOP_K, MAX_TOP_K, bookmarks_by_author


def two_authors(config: Settings) -> None:
    """`ferris` keeps the two seeded bookmarks; `gopher` gets three of their own."""
    add_authors(config, [("2", "gopher", "Gopher", "http://gopher.png")])
    add_bookmarks(config, 3, author_id="2")


def test_the_handle_selects_that_authors_bookmarks(corpus: Settings):
    two_authors(corpus)

    assert {bookmark.id for bookmark in bookmarks_by_author("gopher")} == {
        str(BASE_ID + n) for n in range(3)
    }


def test_no_other_authors_bookmarks_come_back(corpus: Settings):
    """`ferris` owns 100 and 200, and neither may leak into a `gopher` query."""
    two_authors(corpus)

    returned = {bookmark.id for bookmark in bookmarks_by_author("gopher")}

    assert returned.isdisjoint({"100", "200"})
    assert {bookmark.handle for bookmark in bookmarks_by_author("gopher")} == {"gopher"}


def test_the_lookup_is_by_handle_not_by_author_id(corpus: Settings):
    """Author `1` has the handle `ferris`; the id must not match on its own."""
    assert bookmarks_by_author("ferris") != []
    assert bookmarks_by_author("1") == []


def test_an_unknown_handle_returns_nothing(corpus: Settings):
    """An unmatched filter must return nothing, not fall back to the whole corpus."""
    assert bookmarks_by_author("nobody") == []


def test_an_author_with_no_bookmarks_returns_nothing(corpus: Settings):
    add_authors(corpus, [("2", "gopher", "Gopher", "http://gopher.png")])

    assert bookmarks_by_author("gopher") == []


def test_the_handle_is_matched_exactly(corpus: Settings):
    """A prefix is not a match — `ferr` must not find `ferris`."""
    assert bookmarks_by_author("ferr") == []
    assert bookmarks_by_author("Ferris") == []


def test_k_defaults_to_five(corpus: Settings):
    add_bookmarks(corpus, 10, author_id="1")

    assert len(bookmarks_by_author("ferris")) == DEFAULT_TOP_K


def test_k_is_capped(corpus: Settings):
    add_bookmarks(corpus, 55, author_id="1")

    assert len(bookmarks_by_author("ferris", k=1000)) == MAX_TOP_K


def test_k_below_the_default_is_widened(corpus: Settings):
    """The floor matches the other tools: a smaller ask is widened, not honoured."""
    add_bookmarks(corpus, 10, author_id="1")

    assert len(bookmarks_by_author("ferris", k=1)) == DEFAULT_TOP_K


def test_k_between_the_floor_and_the_cap_is_honoured(corpus: Settings):
    add_bookmarks(corpus, 30, author_id="1")

    assert len(bookmarks_by_author("ferris", k=20)) == 20


def test_fewer_bookmarks_than_k_returns_what_there_is(corpus: Settings):
    two_authors(corpus)

    assert len(bookmarks_by_author("gopher")) == 3


def test_each_row_maps_to_a_tweet_result_with_its_author(corpus: Settings):
    bookmarks = {bookmark.id: bookmark for bookmark in bookmarks_by_author("ferris")}

    assert all(isinstance(each, TweetResult) for each in bookmarks.values())
    assert bookmarks["200"].content == "sqlite is a fine database"
    assert (bookmarks["200"].handle, bookmarks["200"].display_name) == (
        "ferris",
        "Ferris",
    )
    assert bookmarks["200"].created_at == "2026-01-02"


def test_an_empty_corpus_has_nothing_for_any_handle(empty_corpus: Settings):
    assert bookmarks_by_author("ferris") == []
