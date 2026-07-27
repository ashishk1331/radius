import argparse
import secrets, hashlib, hmac
import sqlite3 as sql
from tabulate import tabulate

from repository import KEY_QUERIES

def generate_key():
    raw = "bmk_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, key_hash

def verify_key(provided_key, conn) -> bool:
    if not provided_key:
        return False

    provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()

    row = conn.execute(KEY_QUERIES["get-hash"], (provided_hash,)).fetchone()

    if row is None:
        return False
    
    return hmac.compare_digest(row[0], provided_hash)

def handle_list(args):
    with sql.connect("bookmarks.db") as con:
        con.row_factory = sql.Row

        rows = con.execute(KEY_QUERIES["select-all"]).fetchall()

        if len(rows) == 0:
            print("No keys created yet!")
            return

        rows = [dict(row) for row in rows]

        print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))

def prettify_key(key):
    N = len(key) + 4
    first = f"+{"-"*N}+"
    second = f"|{" "*N}|"
    itself = f"|  {key}  |"
    return "\n".join([first, second, itself, second, first])

def handle_generate(args):
    name = args.client_name
    key, hash = generate_key()

    with sql.connect("bookmarks.db") as con:
        con.execute(KEY_QUERIES["insert"], (hash, name))

    print(
        "Key created:", 
        prettify_key(key), 
        "You won't be able see this again!", 
        sep="\n", end="\n\n",
    )

def handle_revoke(args):
    name = args.client_name

    with sql.connect("bookmarks.db") as con:
        con.execute(KEY_QUERIES["revoke"], (name, ))

    print(f"'{name}' revoked.")

def main():
    parser = argparse.ArgumentParser(
        description="Manage secrets for MCP clients.",
    )

    sub_parser = parser.add_subparsers(
        title="commands",
        dest="command",
        required=True,
        help="Available commands."
    )

    parser_list = sub_parser.add_parser(
        "list",
        help="List all saved secrets."
    )
    parser_list.set_defaults(func=handle_list)

    parser_generate = sub_parser.add_parser(
        "generate",
        help="Generate a new secret."
    )
    parser_generate.add_argument(
        "-n", "--client-name",
        type=str,
        required=True,
        help="The client identifier for the secret (e.g., 'claude-desktop')"
    )
    parser_generate.set_defaults(func=handle_generate)

    parser_revoke = sub_parser.add_parser(
        "revoke",
        help="Revoke a secret using associated client name."
    )
    parser_revoke.add_argument(
        "-n", "--client-name",
        type=str,
        required=True,
        help="The client identifier for the secret (e.g., 'claude-desktop')"
    )
    parser_revoke.set_defaults(func=handle_revoke)

    args = parser.parse_args()

    args.func(args)

if __name__ == "__main__":
    main()