"""The ``radius`` command line: serve, migrate, ingest, and manage tokens."""

import argparse
import json
from pathlib import Path

from joserfc.errors import JoseError

from radius.auth import keys, scopes, tokens
from radius.config import settings


def cmd_serve(args: argparse.Namespace) -> None:
    from radius.server import get_server

    config = settings()
    host = args.host or config.host
    port = args.port or config.port

    print(f"Radius MCP on http://{host}:{port}/mcp  (issuer {config.issuer})")
    get_server().run(transport="http", host=host, port=port)


def cmd_migrate(args: argparse.Namespace) -> None:
    from radius.db import migrate

    print(f"Schema applied to {migrate(args.db)}")


def cmd_ingest(args: argparse.Namespace) -> None:
    from radius.ingest import ingest

    count = ingest(args.source, args.db)
    print(f"Ingested {count} bookmarks")


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
    token = tokens.issue(args.client, args.scope, args.ttl)
    config = settings()
    print(
        f"Client:    {args.client}\n"
        f"Scopes:    {' '.join(args.scope or scopes.DEFAULT_SCOPES)}\n"
        f"Audience:  {config.audience}\n"
        f"Expires:   in {args.ttl or config.token_ttl}s\n\n"
        f"{token}\n"
    )


def cmd_token_inspect(args: argparse.Namespace) -> None:
    print(json.dumps(tokens.inspect(args.token), indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="radius",
        description="Search your bookmarks, and serve them to agents over MCP.",
    )
    sub = parser.add_subparsers(title="commands", dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the MCP server.")
    serve.add_argument("--host", help="Override RADIUS_HOST.")
    serve.add_argument("--port", type=int, help="Override RADIUS_PORT.")
    serve.set_defaults(func=cmd_serve)

    migrate = sub.add_parser("migrate", help="Create or update the SQLite schema.")
    migrate.add_argument("--db", type=Path, help="Database path.")
    migrate.set_defaults(func=cmd_migrate)

    ingest = sub.add_parser("ingest", help="Load bookmarks from a raw JSON export.")
    ingest.add_argument("source", nargs="?", type=Path, help="Path to the JSON export.")
    ingest.add_argument("--db", type=Path, help="Database path.")
    ingest.set_defaults(func=cmd_ingest)

    key_parser = sub.add_parser("keys", help="Manage the token signing key pair.")
    key_sub = key_parser.add_subparsers(dest="keys_command", required=True)

    key_init = key_sub.add_parser("init", help="Generate the key pair and JWKS.")
    key_init.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing key. Invalidates every issued token.",
    )
    key_init.set_defaults(func=cmd_keys_init)

    key_show = key_sub.add_parser("show", help="Print the public JWKS document.")
    key_show.set_defaults(func=cmd_keys_show)

    token_parser = sub.add_parser("token", help="Issue and inspect client tokens.")
    token_sub = token_parser.add_subparsers(dest="token_command", required=True)

    token_issue = token_sub.add_parser("issue", help="Mint a token for a client.")
    token_issue.add_argument(
        "-c",
        "--client",
        required=True,
        help="Client identifier, used as the token subject (e.g. 'claude-desktop').",
    )
    token_issue.add_argument(
        "-s",
        "--scope",
        action="append",
        choices=list(scopes.ALL_SCOPES),
        help=f"Scope to grant, repeatable. Defaults to {' '.join(scopes.DEFAULT_SCOPES)}.",
    )
    token_issue.add_argument(
        "--ttl", type=int, help="Lifetime in seconds. Defaults to JWT_TOKEN_TTL."
    )
    token_issue.set_defaults(func=cmd_token_issue)

    token_inspect = token_sub.add_parser(
        "inspect", help="Verify a token and print its claims."
    )
    token_inspect.add_argument("token")
    token_inspect.set_defaults(func=cmd_token_inspect)

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
