"""The ``list_authors`` tool — who is in the corpus, how often, and how many.

Unlike the bookmark tools this one does promise an order: authors come back
ranked by how many bookmarks are saved from them. ``n`` trims that ranking,
with ``-1`` meaning the whole of it.
"""

from conftest import add_authors, add_bookmarks

from radius.config import Settings
from radius.models import AuthorResult
from radius.server.tools import list_authors


def ranked(config: Settings) -> None:
    """Three authors with 5, 3 and 2 bookmarks — `gopher`, `cpython`, `ferris`."""
    add_authors(
        config,
        [
            ("2", "gopher", "Gopher", "http://gopher.png"),
            ("3", "cpython", "CPython", "http://py.png"),
        ],
    )
    add_bookmarks(config, 5, author_id="2", first=0)
    add_bookmarks(config, 3, author_id="3", first=5)


def test_list_authors_returns_every_author(corpus: Settings):
    add_authors(
        corpus,
        [
            ("2", "gopher", "Gopher", "http://gopher.png"),
            ("3", "cpython", "CPython", "http://py.png"),
        ],
    )

    assert {author.handle for author in list_authors()} == {
        "ferris",
        "gopher",
        "cpython",
    }


def test_an_author_appears_once_however_many_bookmarks_they_have(corpus: Settings):
    """`ferris` owns both seeded tweets, and 10 more here."""
    add_bookmarks(corpus, 10)

    handles = [author.handle for author in list_authors()]

    assert handles == ["ferris"]


def test_re_ingesting_an_author_updates_rather_than_duplicates(corpus: Settings):
    add_authors(corpus, [("1", "ferris", "Ferris the Crab", "http://img")])

    authors = list_authors()

    assert len(authors) == 1
    assert authors[0].display_name == "Ferris the Crab"


def test_re_ingesting_an_author_refreshes_their_avatar(corpus: Settings):
    """The `ON CONFLICT` clause has to name `avatar`, or a changed one is dropped."""
    add_authors(corpus, [("1", "ferris", "Ferris", "http://new.png")])

    assert list_authors()[0].avatar == "http://new.png"


def test_each_row_maps_to_an_author_result(corpus: Settings):
    ferris = list_authors()[0]

    assert isinstance(ferris, AuthorResult)
    assert (ferris.id, ferris.handle) == ("1", "ferris")
    assert (ferris.display_name, ferris.avatar) == ("Ferris", "http://img")
    assert ferris.count == 2


def test_an_author_without_an_avatar_comes_back_as_none(corpus: Settings):
    """`avatar` is the one nullable column on the table, so it reaches the model."""
    add_authors(corpus, [("2", "gopher", "Gopher", None)])

    gopher = {author.handle: author for author in list_authors()}["gopher"]

    assert gopher.avatar is None


def test_an_empty_corpus_lists_no_authors(empty_corpus: Settings):
    assert list_authors() == []


def test_the_count_is_how_many_bookmarks_are_saved_from_that_author(corpus: Settings):
    """`ferris` starts with the two seeded tweets; `gopher` gets three of their own."""
    add_authors(corpus, [("2", "gopher", "Gopher", "http://gopher.png")])
    add_bookmarks(corpus, 3, author_id="2")

    counts = {author.handle: author.count for author in list_authors()}

    assert counts == {"ferris": 2, "gopher": 3}


def test_the_count_follows_a_newly_saved_bookmark(corpus: Settings):
    add_bookmarks(corpus, 4)

    counts = {author.handle: author.count for author in list_authors()}

    assert counts == {"ferris": 6}


def test_an_author_with_no_bookmarks_is_counted_as_zero(corpus: Settings):
    """The join has to be a LEFT JOIN, or an author with nothing saved vanishes."""
    add_authors(corpus, [("2", "gopher", "Gopher", "http://gopher.png")])

    counts = {author.handle: author.count for author in list_authors()}

    assert counts == {"ferris": 2, "gopher": 0}


def test_authors_are_ordered_by_count_descending(corpus: Settings):
    """Unlike the bookmark tools, this one does sort — `ORDER BY` says so."""
    ranked(corpus)

    assert [(a.handle, a.count) for a in list_authors()] == [
        ("gopher", 5),
        ("cpython", 3),
        ("ferris", 2),
    ]


def test_n_defaults_to_the_entire_list(corpus: Settings):
    ranked(corpus)

    assert list_authors() == list_authors(-1)
    assert len(list_authors()) == 3


def test_n_returns_only_the_most_saved_authors(corpus: Settings):
    ranked(corpus)

    assert [author.handle for author in list_authors(2)] == ["gopher", "cpython"]


def test_n_takes_from_the_top_of_the_full_ranking(corpus: Settings):
    """Whichever query runs, the prefix has to agree with the unlimited one."""
    ranked(corpus)

    everyone = [author.handle for author in list_authors()]

    assert [author.handle for author in list_authors(1)] == everyone[:1]
    assert [author.handle for author in list_authors(2)] == everyone[:2]


def test_n_larger_than_the_corpus_returns_everyone(corpus: Settings):
    ranked(corpus)

    assert len(list_authors(99)) == 3


def test_n_of_zero_returns_nothing(corpus: Settings):
    """`LIMIT 0` is a real limit, unlike a negative one — asking for none gets none."""
    ranked(corpus)

    assert list_authors(0) == []


def test_any_negative_n_behaves_like_the_default(corpus: Settings):
    """SQLite treats every negative `LIMIT` as unlimited, so -5 is not an error."""
    ranked(corpus)

    assert len(list_authors(-5)) == 3


def test_the_count_survives_the_limited_query(corpus: Settings):
    """The two queries are separate files; the counts must not drift apart."""
    ranked(corpus)

    assert [(a.handle, a.count) for a in list_authors(3)] == [
        (a.handle, a.count) for a in list_authors()
    ]
