"""SQLite connections, configured the same way everywhere."""

import sqlite3 as sql
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from radius.config import settings
from radius.db import queries
from radius.search import fuzzy_score


@contextmanager
def connect(
    path: Path | None = None, *, readonly: bool = False
) -> Iterator[sql.Connection]:
    """Open a connection with radius' conventions applied.

    Commits on clean exit, rolls back on exception, and always closes — the
    bare ``sqlite3.connect`` context manager does neither of the last two.
    """
    db_path = path or settings().db_path

    if readonly:
        con = sql.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        con = sql.connect(db_path)

    try:
        con.row_factory = sql.Row
        con.execute("PRAGMA foreign_keys = ON;")
        con.create_function("FUZZY_SCORE", 2, fuzzy_score, deterministic=True)
        with con:
            yield con
    finally:
        con.close()


def migrate(path: Path | None = None) -> Path:
    """Apply the schema. Every statement is idempotent, so this is re-runnable."""
    db_path = path or settings().db_path
    with connect(db_path) as con:
        con.executescript(queries.migration())
    return db_path
