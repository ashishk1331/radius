"""The Turso-first data layer: mode selection, row mapping, and search."""

import pytest

from radius.config import Settings
from radius.db import QUERIES, SEARCH_EXACT, SELECT_ALL, connect, mode
from radius.db import query as run_query
from radius.search import FUZZY_THRESHOLD, rank_fuzzy


def variant(config: Settings, **overrides) -> Settings:
    return Settings(**{**config.__dict__, **overrides})


def test_mode_is_local_for_a_file_without_a_turso_url(config: Settings):
    """The local file is a test/offline fallback, not a second home for data."""
    on_disk = variant(config, db_path=config.root / "bookmarks.db")

    assert mode(on_disk) == "local"


def test_mode_is_memory_when_the_db_path_is_the_memory_marker(config: Settings):
    assert mode(config) == "memory"


def test_a_turso_url_outranks_an_in_memory_db_path(config: Settings):
    """`connect` checks the URL first, so the mode has to agree with it."""
    remote = variant(config, turso_url="libsql://db.turso.io")

    assert mode(remote) == "remote"


def test_a_turso_url_means_remote(config: Settings):
    assert mode(variant(config, turso_url="libsql://db.turso.io")) == "remote"


def test_query_maps_rows_to_dicts(seeded_config: Settings):
    """libSQL has no row_factory, so `query` is what makes rows addressable."""
    with connect(config=seeded_config) as con:
        rows = run_query(con, SELECT_ALL)

    assert len(rows) == 2
    assert all(isinstance(row, dict) for row in rows)
    assert rows[0]["handle"] == "ferris"


def test_exact_search_ranks_via_fts5(seeded_config: Settings):
    with connect(config=seeded_config) as con:
        rows = run_query(con, SEARCH_EXACT, ("rust", 5))

    assert [row["id"] for row in rows] == ["100"]
    assert rows[0]["score"] > 0, "score is negated bm25, so higher is better"


def test_fuzzy_scoring_ranks_and_thresholds():
    rows = [
        {"id": "1", "content": "rust is blazing fast"},
        {"id": "2", "content": "sqlite is a fine database"},
    ]

    ranked = rank_fuzzy(rows, "blazing", top_k=5)

    assert [row["id"] for row in ranked] == ["1"]
    assert ranked[0]["score"] >= FUZZY_THRESHOLD


def test_fuzzy_respects_top_k():
    rows = [{"id": str(n), "content": "matching text"} for n in range(10)]

    assert len(rank_fuzzy(rows, "matching text", top_k=3)) == 3


def test_fuzzy_returns_nothing_below_threshold():
    rows = [{"id": "1", "content": "completely unrelated words"}]

    assert rank_fuzzy(rows, "zzzzqqqq", top_k=5) == []


def test_connection_rolls_back_on_error(seeded_config: Settings):
    with pytest.raises(RuntimeError), connect(config=seeded_config) as con:
        con.execute(
            QUERIES["UPSERT"]["TWEET"],
            ("300", "1", "should not persist", "2026-01-03", None, None),
        )
        raise RuntimeError("boom")

    with connect(config=seeded_config) as con:
        remaining = run_query(con, SELECT_ALL)

    assert "300" not in {row["id"] for row in remaining}


def test_migrate_reports_turso_as_the_target_when_configured(config: Settings):
    """The reported target is the database of record, not a local path."""
    remote = variant(config, turso_url="libsql://db.turso.io")

    assert mode(remote) == "remote"
    assert remote.turso_url == "libsql://db.turso.io"
