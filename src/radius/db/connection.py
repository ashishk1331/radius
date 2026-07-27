"""libSQL connections.

Turso is the corpus. When ``TURSO_DATABASE_URL`` is set — which is the normal
configuration, locally and in production alike — every connection talks to it
directly. There is no local mirror to drift out of date, and no second copy of
the data to reason about.

Without a URL, radius falls back to a plain local libSQL file. That exists so
the test suite and offline work need neither credentials nor a network, not as
a parallel home for your bookmarks.

Two things the stdlib ``sqlite3`` module gives you are absent here, and the rest
of the codebase is written accordingly: there is no ``row_factory`` (use
:func:`query`, which maps rows to dicts) and no ``create_function`` (fuzzy
scoring happens in Python — see :mod:`radius.search`).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import libsql

from radius.config import Settings, settings
from radius.db import queries

Mode = Literal["local", "remote"]


def mode(config: Settings | None = None) -> Mode:
    """Which database the current configuration points at."""
    config = config or settings()
    return "remote" if config.turso_url else "local"


@contextmanager
def connect(
    path: Path | None = None, config: Settings | None = None
) -> Iterator[libsql.Connection]:
    """Open a connection, commit on clean exit, roll back on error, always close."""
    config = config or settings()

    if config.turso_url:
        con = libsql.connect(config.turso_url, auth_token=config.turso_auth_token)
    else:
        con = libsql.connect(str(path or config.db_path))

    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def query(con: libsql.Connection, sql: str, params: tuple = ()) -> list[dict]:
    """Run a read and map rows to dicts, since libSQL has no ``row_factory``."""
    cursor = con.execute(sql, params)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def migrate(path: Path | None = None, config: Settings | None = None) -> Path | str:
    """Apply the schema. Every statement is idempotent, so this is re-runnable."""
    config = config or settings()

    with connect(path, config) as con:
        con.executescript(queries.migration())

    return config.turso_url or (path or config.db_path)
