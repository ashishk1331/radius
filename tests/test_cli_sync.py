"""``radius sync`` — pull new bookmarks, then load them.

Neither half is exercised for real here. What matters is the wiring: that the
database is opened before anything is fetched, that both halves are pointed at
the same store, and that a run which would throw its results away is refused
rather than discovered thirty minutes in.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from radius import cli
from radius.config import MEMORY, Settings
from radius.db import connect, query


@pytest.fixture
def local(config: Settings, tmp_path) -> Settings:
    """A configuration that keeps its rows, unlike the in-memory default."""
    return replace(config, db_path=tmp_path / "corpus.db")


@pytest.fixture
def wired(monkeypatch, local: Settings):
    """Stand in for the two halves, recording what the command asked of them."""
    calls = {}

    def fake_sync(start, force, store):
        calls["sync"] = {"start": start, "force": force, "store": store}
        Path(store).write_text(
            json.dumps({
                "id": "100",
                "text": "a tweet",
                "createdAt": "Wed May 27 16:39:29 +0000 2026",
                "author": {
                    "id": "1",
                    "screenName": "ferris",
                    "name": "Ferris",
                    "profileImageUrl": "http://img",
                },
                "in_reply_to": None,
            }) + "\n",
            encoding="utf-8",
        )
        return 1

    monkeypatch.setattr(cli, "settings", lambda: local)
    monkeypatch.setattr(cli, "sync", fake_sync)
    monkeypatch.setattr("radius.ingest.embed_tweets", lambda tweets: [None] * len(tweets))
    return calls


def run(*argv: str) -> None:
    args = cli.build_parser().parse_args(["sync", *argv])
    args.func(args)


def test_sync_pulls_then_loads_what_it_pulled(wired, local: Settings, capsys):
    run("--db", str(local.db_path))

    with connect(local.db_path, local) as con:
        stored = query(con, "SELECT id FROM tweets")

    assert [row["id"] for row in stored] == ["100"]
    assert "Fetched 1 new bookmarks" in capsys.readouterr().out


def test_both_halves_are_pointed_at_the_same_store(wired, local: Settings, tmp_path):
    store = tmp_path / "elsewhere.jsonl"

    run("--db", str(local.db_path), "--store", str(store))

    assert wired["sync"]["store"] == store
    assert store.exists()


def test_the_window_arguments_reach_sync(wired, local: Settings):
    run("--db", str(local.db_path), "--start", "7", "--force")

    assert wired["sync"]["start"] == 7
    assert wired["sync"]["force"] is True


def test_a_run_that_would_be_discarded_is_refused(monkeypatch, config: Settings):
    """`:memory:` is the unconfigured default, and it keeps nothing."""
    monkeypatch.setattr(cli, "settings", lambda: config)
    monkeypatch.setattr(cli, "sync", lambda **kwargs: pytest.fail("fetched anyway"))

    assert str(config.db_path) == MEMORY
    with pytest.raises(RuntimeError, match="discarded"):
        run()


def test_the_refusal_can_be_overridden(monkeypatch, config: Settings, capsys):
    monkeypatch.setattr(cli, "settings", lambda: config)
    monkeypatch.setattr(cli, "sync", lambda **kwargs: 0)
    monkeypatch.setattr("radius.ingest.embed_tweets", lambda tweets: [])
    (config.root / "bookmarks.jsonl").write_text("", encoding="utf-8")

    run("--allow-memory")

    assert "memory mode" in capsys.readouterr().out


def test_the_database_is_opened_before_anything_is_fetched(
    monkeypatch, local: Settings
):
    """A pull costs minutes of rate-limited calls; failing after it wastes them."""
    order = []
    monkeypatch.setattr(cli, "settings", lambda: local)
    monkeypatch.setattr(cli, "migrate", lambda db, config: order.append("migrate"))
    monkeypatch.setattr(cli, "sync", lambda **kwargs: order.append("sync") or 0)
    monkeypatch.setattr(cli, "ingest", lambda *a, **k: order.append("ingest") or 0)

    run()

    assert order == ["migrate", "sync", "ingest"]
