"""The ``radius`` command line: serve, migrate, sync, ingest, and manage tokens."""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import uvicorn
from joserfc.errors import JoseError

from radius.auth import keys, ledger, scopes, tokens
from radius.config import PACKAGE_ROOT, settings
from radius.db import migrate, mode
from radius.ingest import STORE, ingest
from radius.sync import LARGEST, START, sync
from radius.server import get_server


def cmd_serve(args: argparse.Namespace) -> None:
    config = settings()
    host = args.host or config.host
    port = args.port or config.port
    where = f"http://{host}:{port}/mcp  (issuer {config.issuer})"

    if args.reload:
        print(f"Radius MCP on {where}, reloading on changes under {PACKAGE_ROOT}")
        uvicorn.run(
            "radius.server:asgi_app",
            factory=True,
            host=host,
            port=port,
            reload=True,
            reload_dirs=[str(PACKAGE_ROOT)],
            reload_includes=["*.py", "*.html", "*.sql"],
        )
        return

    print(f"Radius MCP on {where}")
    get_server().run(transport="http", host=host, port=port)


def cmd_migrate(args: argparse.Namespace) -> None:
    print(f"Schema applied to {migrate(args.db)} ({mode()} mode)")


def cmd_ingest(args: argparse.Namespace) -> None:
    count = ingest(args.source, args.db)
    print(f"Ingested {count} bookmarks")


def cmd_sync(args: argparse.Namespace) -> None:
    """Pull new bookmarks, then load them into the database.

    The database is opened before a single tweet is fetched. Pulling takes
    minutes of sleeps and rate-limited calls, and discovering at the end of it
    that nothing can be written would waste the whole run.
    """
    config = settings()
    store = args.store or config.root / STORE
    resolved = mode(config)

    if resolved == "memory" and not args.allow_memory:
        raise RuntimeError(
            "the database resolves to :memory:, which is discarded when this "
            "command exits — a sync would fetch your bookmarks and then throw "
            "them away. Set TURSO_DATABASE_URL (or RADIUS_DB_PATH) first, or "
            "pass --allow-memory if that is really what you want."
        )

    print(f"Database: {migrate(args.db, config)} ({resolved} mode)")

    fetched = sync(start=args.start, force=args.force, store=store)
    print(f"Fetched {fetched} new bookmarks into {store}")

    print(f"Ingested {ingest(store, args.db, config)} bookmarks")


def cmd_keys_init(args: argparse.Namespace) -> None:
    config = settings()
    jwks_path = keys.generate(config, force=args.force)
    print(
        f"Private key: {config.private_key_path}  (keep this secret)\n"
        f"Public key:  {config.public_key_path}\n"
        f"JWKS:        {jwks_path}"
    )


def cmd_keys_show(args: argparse.Namespace) -> None:
    print(json.dumps(keys.load_jwks(), indent=2))


def cmd_token_issue(args: argparse.Namespace) -> None:
    config = settings()
    token, claims = tokens.mint(args.client, args.scope, args.ttl, config)
    ledger.record(claims, config)
    print(
        f"Client:    {args.client}\n"
        f"Scopes:    {' '.join(args.scope or scopes.DEFAULT_SCOPES)}\n"
        f"Audience:  {config.audience}\n"
        f"Expires:   in {args.ttl or config.token_ttl}s\n\n"
        f"{token}\n"
    )


def cmd_token_inspect(args: argparse.Namespace) -> None:
    print(json.dumps(tokens.inspect(args.token), indent=2))

def _stamp(epoch: int | None) -> str:
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M") if epoch else "?"


def _table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    widths = [max(len(row[column]) for row in (header, *rows)) for column in range(len(header))]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()
        for row in (header, *rows)
    )


def cmd_token_list(args: argparse.Namespace) -> None:
    """What has been issued, read from the local ledger.

    Not a list of what the server would accept. Tokens are verified by
    signature alone and nothing is stored server-side, so a token missing from
    this file still works and one listed here is not revoked by removing it.
    """
    config = settings()
    now = int(time.time())

    rows = [
        (
            str(entry.get("sub") or "?"),
            str(entry.get("scope") or ""),
            _stamp(entry.get("iat")),
            _stamp(entry.get("exp")),
            "expired" if (entry.get("exp") or 0) <= now else "active",
        )
        for entry in ledger.read(config)
    ]

    if not rows:
        print(f"No tokens recorded in {config.ledger_path}")
        return

    print(_table(("CLIENT", "SCOPES", "ISSUED", "EXPIRES", "STATUS"), rows))


Commands = argparse._SubParsersAction


def add_serve(sub: Commands) -> None:
    serve = sub.add_parser("serve", help="Run the MCP server.")
    serve.add_argument("--host", help="Override RADIUS_HOST.")
    serve.add_argument("--port", type=int, help="Override RADIUS_PORT.")
    serve.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Restart when a .py, .html or .sql file under the package changes.",
    )
    serve.set_defaults(func=cmd_serve)


def add_migrate(sub: Commands) -> None:
    parser = sub.add_parser("migrate", help="Create or update the SQLite schema.")
    parser.add_argument("--db", type=Path, help="Database path.")
    parser.set_defaults(func=cmd_migrate)


def add_ingest(sub: Commands) -> None:
    parser = sub.add_parser("ingest", help="Load bookmarks from a raw JSON export.")
    parser.add_argument("source", nargs="?", type=Path, help="Path to the JSON export.")
    parser.add_argument("--db", type=Path, help="Database path.")
    parser.set_defaults(func=cmd_ingest)


def add_sync(sub: Commands) -> None:
    parser = sub.add_parser(
        "sync", help="Pull new bookmarks from X, then load them into the database."
    )
    parser.add_argument(
        "--store", type=Path, help=f"JSONL store to append to. Defaults to {STORE}."
    )
    parser.add_argument("--db", type=Path, help="Database path.")
    parser.add_argument(
        "--start",
        type=int,
        default=START,
        metavar="N",
        help=f"Ask for 2**N bookmarks on the first round, doubling to 2**{LARGEST}. "
        f"Defaults to {START}.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Keep widening past the first round that finds nothing new.",
    )
    parser.add_argument(
        "--allow-memory",
        action="store_true",
        help="Sync even when the database is :memory: and the rows will be lost.",
    )
    parser.set_defaults(func=cmd_sync)


def add_keys(sub: Commands) -> None:
    parser = sub.add_parser("keys", help="Manage the token signing key pair.")
    keys_sub = parser.add_subparsers(dest="keys_command", required=True)

    init = keys_sub.add_parser("init", help="Generate the key pair and JWKS.")
    init.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing key. Invalidates every issued token.",
    )
    init.set_defaults(func=cmd_keys_init)

    show = keys_sub.add_parser("show", help="Print the public JWKS document.")
    show.set_defaults(func=cmd_keys_show)


def add_token(sub: Commands) -> None:
    parser = sub.add_parser("token", help="Issue and inspect client tokens.")
    token_sub = parser.add_subparsers(dest="token_command", required=True)

    issue = token_sub.add_parser("issue", help="Mint a token for a client.")
    issue.add_argument(
        "-c",
        "--client",
        required=True,
        help="Client identifier, used as the token subject (e.g. 'claude-desktop').",
    )
    issue.add_argument(
        "-s",
        "--scope",
        action="append",
        choices=list(scopes.ALL_SCOPES),
        help=f"Scope to grant, repeatable. Defaults to {' '.join(scopes.DEFAULT_SCOPES)}.",
    )
    issue.add_argument(
        "--ttl", type=int, help="Lifetime in seconds. Defaults to JWT_TOKEN_TTL."
    )
    issue.set_defaults(func=cmd_token_issue)

    inspect = token_sub.add_parser(
        "inspect", help="Verify a token and print its claims."
    )
    inspect.add_argument("token")
    inspect.set_defaults(func=cmd_token_inspect)

    listing = token_sub.add_parser(
        "list", help="Show what has been issued, from the local record."
    )
    listing.set_defaults(func=cmd_token_list)


REGISTER = (add_serve, add_migrate, add_ingest, add_sync, add_keys, add_token)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="radius",
        description="Search your bookmarks, and serve them to agents over MCP.",
    )
    sub = parser.add_subparsers(title="commands", dest="command", required=True)

    for register in REGISTER:
        register(sub)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (FileExistsError, ValueError, RuntimeError, JoseError) as exc:
        # JoseError covers claim rejections (bad `aud`, `iss`, expiry) that
        # surface from token inspection; report them like any other failure
        # rather than as a traceback.
        raise SystemExit(f"error: {exc}")


if __name__ == "__main__":
    main()
