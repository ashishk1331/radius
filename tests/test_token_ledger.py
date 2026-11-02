"""``radius token list`` and the ledger behind it.

The ledger is a record of what was handed out, not of what would be accepted.
These check that it says so honestly: the token itself never reaches disk, an
absent file is not an error, and nothing in the verification path reads it.
"""

import json

import pytest

from radius import cli
from radius.auth import ledger, tokens
from radius.config import Settings


def run(monkeypatch, config: Settings, *argv: str) -> None:
    monkeypatch.setattr(cli, "settings", lambda: config)
    args = cli.build_parser().parse_args(["token", *argv])
    args.func(args)


def test_issuing_records_the_claims_but_never_the_token(
    monkeypatch, keyed_config: Settings, capsys
):
    run(monkeypatch, keyed_config, "issue", "-c", "claude-code")
    token = capsys.readouterr().out.strip().splitlines()[-1]

    entries = ledger.read(keyed_config)

    assert [entry["sub"] for entry in entries] == ["claude-code"]
    assert entries[0]["scope"] == "bookmarks:read"
    assert token not in keyed_config.ledger_path.read_text()


def test_the_ledger_lists_every_client_that_was_issued_one(
    monkeypatch, keyed_config: Settings, capsys
):
    for client in ("claude-code", "claude-desktop"):
        run(monkeypatch, keyed_config, "issue", "-c", client)
    capsys.readouterr()

    run(monkeypatch, keyed_config, "list")
    printed = capsys.readouterr().out

    assert "CLIENT" in printed
    assert "claude-code" in printed
    assert "claude-desktop" in printed
    assert "active" in printed


def test_a_lapsed_token_is_listed_as_expired(
    monkeypatch, keyed_config: Settings, capsys
):
    """It stays on the record. Expiry is a fact about the token, not a delete."""
    run(monkeypatch, keyed_config, "issue", "-c", "stale", "--ttl", "-1")
    capsys.readouterr()

    run(monkeypatch, keyed_config, "list")

    assert "expired" in capsys.readouterr().out


def test_no_ledger_yet_is_not_an_error(monkeypatch, config: Settings, capsys):
    assert not config.ledger_path.exists()

    run(monkeypatch, config, "list")

    assert "No tokens recorded" in capsys.readouterr().out
    assert ledger.read(config) == []


def test_the_record_is_never_consulted_to_verify(keyed_config: Settings):
    """Deleting a line revokes nothing — the signature is the whole check."""
    token, claims = tokens.mint("claude-code", config=keyed_config)
    ledger.record(claims, keyed_config)

    keyed_config.ledger_path.unlink()

    assert tokens.inspect(token, keyed_config)["sub"] == "claude-code"


def test_only_the_recorded_fields_reach_disk(keyed_config: Settings):
    ledger.record(
        {"sub": "claude-code", "scope": "bookmarks:read", "iss": "http://secret"},
        keyed_config,
    )

    written = json.loads(keyed_config.ledger_path.read_text().strip())

    assert set(written) == set(ledger.FIELDS)
    assert "iss" not in written


def test_a_ledger_written_by_hand_still_reads(config: Settings):
    config.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    config.ledger_path.write_text('{"sub": "a"}\n\n{"sub": "b"}\n', encoding="utf-8")

    assert [entry["sub"] for entry in ledger.read(config)] == ["a", "b"]


@pytest.mark.parametrize("epoch,expected", [(None, "?"), (0, "?")])
def test_a_missing_timestamp_prints_rather_than_raises(epoch, expected):
    assert cli._stamp(epoch) == expected
