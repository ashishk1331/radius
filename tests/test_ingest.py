"""Reading a sync'd export into the corpus.

The export is the JSONL store :mod:`radius.sync` appends to, so what these
check is the join between the two: that a thread written as a chain of lines
comes back as a chain of rows, and that a reply naming a parent the export
does not carry cannot take the rest of the batch down with it.

Embedding is stubbed throughout. It is a 67MB model download and none of it
bears on whether a row lands in the right column.
"""

import json

import pytest

from radius import ingest as ingest_module
from radius.config import Settings
from radius.db import SEARCH_EXACT, connect, query
from radius.ingest import ingest, load_bookmarks


@pytest.fixture(autouse=True)
def without_the_model(monkeypatch):
    monkeypatch.setattr(
        ingest_module, "embed_tweets", lambda tweets: [None] * len(tweets)
    )


def tweet(id: str, text: str = "a tweet", author: str = "1", **extra) -> dict:
    return {
        "id": id,
        "text": text,
        "createdAt": "Wed May 27 16:39:29 +0000 2026",
        "author": {
            "id": author,
            "screenName": f"handle{author}",
            "name": f"Author {author}",
            "profileImageUrl": "http://img",
        },
        **extra,
    }


def store(config: Settings, tweets: list[dict], name: str = "bookmarks.jsonl"):
    path = config.root / name
    path.write_text(
        "\n".join(json.dumps(each) for each in tweets) + "\n", encoding="utf-8"
    )
    return path


def quoting(id: str, quoted: str, **extra) -> dict:
    """A bookmark that quotes another tweet, shaped as the export carries it.

    The embedded object is thin — no author id, no timestamp — which is why
    sync fetches the quoted tweet separately rather than storing this.
    """
    return tweet(
        id,
        quotedTweet={
            "id": quoted,
            "text": "the quoted text",
            "author": {"screenName": "someone", "name": "Someone"},
        },
        **extra,
    )


def rows(config: Settings) -> dict[str, dict]:
    with connect(config=config) as con:
        return {
            row["id"]: row
            for row in query(
                con,
                "SELECT id, content, in_reply_to_id, quoted_tweet_id FROM tweets",
            )
        }


def test_a_reply_is_stored_against_the_tweet_it_answers(config: Settings):
    """The whole point of the export carrying `in_reply_to`."""
    source = store(config, [
        tweet("100", "the bookmark", in_reply_to=None),
        tweet("101", "first reply", in_reply_to="100"),
    ])

    ingest(source, config.db_path, config)

    assert rows(config)["101"]["in_reply_to_id"] == "100"


def test_a_bookmark_is_stored_with_nothing_to_reply_to(config: Settings):
    source = store(config, [tweet("100", "the bookmark", in_reply_to=None)])

    ingest(source, config.db_path, config)

    assert rows(config)["100"]["in_reply_to_id"] is None


def test_a_thread_is_stored_as_a_chain_rather_than_a_fan(config: Settings):
    """Each reply names the one before it, not the bookmark at the head."""
    source = store(config, [
        tweet("100", "head", in_reply_to=None),
        tweet("101", "second", in_reply_to="100"),
        tweet("102", "third", in_reply_to="101"),
    ])

    ingest(source, config.db_path, config)
    stored = rows(config)

    assert stored["101"]["in_reply_to_id"] == "100"
    assert stored["102"]["in_reply_to_id"] == "101"


def test_a_reply_whose_parent_is_missing_keeps_the_row_and_drops_the_edge(
    config: Settings,
):
    """libSQL enforces the foreign key, so the alternative is losing the batch."""
    source = store(config, [
        tweet("100", "the bookmark", in_reply_to=None),
        tweet("101", "reply to something not exported", in_reply_to="999"),
    ])

    assert ingest(source, config.db_path, config) == 2

    stored = rows(config)
    assert stored["101"]["in_reply_to_id"] is None
    assert stored["100"]["content"] == "the bookmark"


def test_re_ingesting_fills_in_a_reply_edge_that_was_missing(config: Settings):
    """The 163 bookmarks already synced carry no `in_reply_to`; a later run adds it."""
    ingest(store(config, [tweet("100"), tweet("101")]), config.db_path, config)
    assert rows(config)["101"]["in_reply_to_id"] is None

    ingest(
        store(config, [tweet("100"), tweet("101", in_reply_to="100")]),
        config.db_path,
        config,
    )

    assert rows(config)["101"]["in_reply_to_id"] == "100"


def test_replies_reach_the_full_text_index(config: Settings):
    """A reply is a row like any other, so search has to see it."""
    source = store(config, [
        tweet("100", "the bookmark", in_reply_to=None),
        tweet("101", "kestrel", in_reply_to="100"),
    ])

    ingest(source, config.db_path, config)

    with connect(config=config) as con:
        found = query(con, SEARCH_EXACT, ("kestrel", 5))

    assert [row["id"] for row in found] == ["101"]


def test_a_quoted_tweet_is_stored_against_the_bookmark_that_quotes_it(
    config: Settings,
):
    source = store(config, [tweet("900", "the quoted tweet"), quoting("100", "900")])

    ingest(source, config.db_path, config)

    assert rows(config)["100"]["quoted_tweet_id"] == "900"


def test_a_quoted_tweet_the_export_lacks_leaves_the_edge_empty(config: Settings):
    """Until sync fetches it, the bookmark carries an id pointing at nothing."""
    source = store(config, [quoting("100", "900")])

    assert ingest(source, config.db_path, config) == 1
    assert rows(config)["100"]["quoted_tweet_id"] is None


def test_a_quoted_tweet_written_after_the_bookmark_is_still_linked(config: Settings):
    """Sync appends it a run later, so the store holds them the wrong way round."""
    source = store(config, [quoting("100", "900"), tweet("900", "the quoted tweet")])

    ingest(source, config.db_path, config)

    assert rows(config)["100"]["quoted_tweet_id"] == "900"


def test_a_reply_written_after_its_parent_is_ordered_before_insert(config: Settings):
    source = store(config, [
        tweet("101", "the reply", in_reply_to="100"),
        tweet("100", "the bookmark"),
    ])

    ingest(source, config.db_path, config)

    assert rows(config)["101"]["in_reply_to_id"] == "100"


def test_a_tweet_quoting_itself_does_not_hang_the_ordering(config: Settings):
    """Nothing should produce this, but a cycle must not spin the sort forever."""
    source = store(config, [quoting("100", "100")])

    assert ingest(source, config.db_path, config) == 1


def test_the_older_json_export_still_loads(config: Settings):
    path = config.root / "bookmarks.json"
    path.write_text(json.dumps({"data": [tweet("100")]}), encoding="utf-8")

    assert ingest(path, config.db_path, config) == 1
    assert "100" in rows(config)


def test_a_jsonl_export_ignores_blank_lines(config: Settings):
    path = config.root / "bookmarks.jsonl"
    path.write_text(f"{json.dumps(tweet('100'))}\n\n", encoding="utf-8")

    assert len(load_bookmarks(path)) == 1
