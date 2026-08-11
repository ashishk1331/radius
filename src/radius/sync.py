"""Pull bookmarks and their author's own replies into a JSONL store.

The store is what :mod:`radius.ingest` reads. One tweet per line: a bookmark
carries ``in_reply_to: null`` and each reply carries the id of the tweet it
answers, so a self-thread reads back as a chain rather than a flat fan.

There is no cursor to page with, so each round asks the CLI for twice as many
bookmarks as the last and stops once a round turns up nothing new. Every call
sleeps first, which is what makes an interrupted run likely: the store is
appended to and flushed a thread at a time, and whatever half-written line a
kill leaves behind is skipped on the next run rather than stopping it.
"""

import json
import shlex
import subprocess as subp
import time
from functools import wraps
from pathlib import Path
from random import random
from typing import Any, TextIO

BOOKMARKS_CMD = "twitter bookmarks --full-text --json --max {count}"
TWEETS_CMD = "twitter tweet {id} --json"
ROOT_DIR = Path(__file__).parent.parent.parent
BOOKMARKS_STORE = ROOT_DIR / "bookmarks.jsonl"

START = 4
LARGEST = 12
TIMEOUT = 120


def _nth(n: float) -> int:
    return int(1 * (2**n))


def _wait_and_run(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        sleep_time = _nth(random() * 2 + 1)
        print(f"Sleeping for {sleep_time}s")
        time.sleep(sleep_time)
        print(f"Woke up! Running {fn.__name__}")
        return fn(*args, **kwargs)

    return wrapper


def _read(command: str) -> list[Any]:
    """Run the CLI and return its ``data`` array, or nothing if it gave none.

    A sync is a long run of calls with sleeps between them. One refusal, one
    timeout or one unexpected payload should cost that call rather than the
    run and everything already written.
    """
    try:
        result = subp.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            check=True,
            timeout=TIMEOUT,
        )
    except subp.CalledProcessError as error:
        print(f"Command failed: {(error.stderr or '').strip() or error}")
        return []
    except subp.TimeoutExpired:
        print(f"Command gave up after {TIMEOUT}s.")
        return []
    except FileNotFoundError:
        raise RuntimeError(
            f"{shlex.split(command)[0]!r} is not on PATH. Sync shells out to the "
            "twitter CLI to read your bookmarks; install it and sign in first."
        ) from None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Unable to decode the data.")
        return []

    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, list) else []


def _already_synced_bookmarks_ids(store: Path) -> set[str]:
    """Every id in the store, skipping whatever a killed run left half-written."""
    if not store.exists():
        return set()

    seen = set()
    with open(store, "r", encoding="utf-8") as file:
        for number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                seen.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                print(f"Skipping unreadable line {number} of the store.")
    return seen


def _write(file: TextIO, tweet: dict, in_reply_to: str | None) -> None:
    file.write(
        json.dumps({**tweet, "in_reply_to": in_reply_to}, ensure_ascii=False) + "\n"
    )


def _quoted_id(tweet: dict) -> str | None:
    return (tweet.get("quotedTweet") or {}).get("id")


def _write_thread(
    file: TextIO, head: dict, replies: list[Any], visited: set[str]
) -> None:
    """Write a tweet and the replies continuing it, each naming the one before."""
    visited.add(head["id"])
    _write(file, head, None)

    last = head
    for each in replies:
        if each["id"] in visited:
            last = each
            continue
        visited.add(each["id"])
        _write(file, each, last["id"])
        last = each


def _own_replies(thread: list[Any], id: str, author_id: str | None) -> list[Any]:
    """The author's own continuations of ``id``, up to the first from anyone else.

    The endpoint answers with the whole thread, the tweet asked for included,
    so the root is dropped here rather than left for a caller to notice —
    relying on the visited set for that would work by accident, and only while
    the caller happened to have recorded the id first.
    """
    _to_fill_tweets = []
    for tweet in thread:
        if tweet.get("id") == id:
            continue
        if tweet.get("author", {}).get("id") != author_id:
            break
        _to_fill_tweets.append(tweet)
    return _to_fill_tweets


@_wait_and_run
def _fetch_tweet_replies(id: str, author_id: str) -> list[Any]:
    return _own_replies(_read(TWEETS_CMD.format(id=id)), id, author_id)


@_wait_and_run
def _fetch_quoted_tweet(id: str) -> tuple[dict | None, list[Any]]:
    """A quoted tweet and its author's replies to it.

    A bookmark carries the tweet it quotes as ``id``, ``text`` and a handle —
    no author id and no timestamp, which is not enough to store as a row of
    its own. The thread endpoint answers with the full tweet as part of the
    thread, so the one call that finds the replies also supplies the tweet.
    """
    thread = _read(TWEETS_CMD.format(id=id))
    root = next((each for each in thread if each.get("id") == id), None)
    if root is None:
        return None, []
    return root, _own_replies(thread, id, root.get("author", {}).get("id"))


@_wait_and_run
def _fetch_bookmarks(n: int) -> list[Any]:
    return _read(BOOKMARKS_CMD.format(count=_nth(n)))


def sync(
    start: int = START, force: bool = False, store: Path | None = None
) -> int:
    """Append every bookmark the store does not already hold. Returns how many.

    ``force`` keeps widening the window past the first round that finds
    nothing new, for when the newest bookmarks are already held but older
    ones are not.
    """
    store = store or BOOKMARKS_STORE
    _visited = _already_synced_bookmarks_ids(store)
    written = 0

    for window in range(start, LARGEST + 1):
        _to_fill_tweets = []

        for tweet in _fetch_bookmarks(window):
            if tweet["id"] in _visited:
                continue
            _visited.add(tweet["id"])
            _to_fill_tweets.append(tweet)

        if not _to_fill_tweets:
            if force:
                continue
            break

        with open(store, "a", encoding="utf-8") as file:
            for tweet in _to_fill_tweets:
                _write_thread(
                    file,
                    tweet,
                    _fetch_tweet_replies(tweet["id"], tweet["author"]["id"]),
                    _visited,
                )

                quoted = _quoted_id(tweet)
                if quoted and quoted not in _visited:
                    root, replies = _fetch_quoted_tweet(quoted)
                    if root is not None:
                        _write_thread(file, root, replies, _visited)

                file.flush()

        written += len(_to_fill_tweets)
        print(f"Written {len(_to_fill_tweets)} bookmarks.")

    return written


if __name__ == "__main__":
    print(f"synced {sync()} bookmarks")
