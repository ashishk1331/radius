# AGENTS.md

Guidance for coding agents working in this repository. Humans should read
[README.md](README.md), which covers the same ground in more depth.

Radius is a self-hosted MCP server that makes saved twitter/X bookmarks
searchable by an AI agent. One Python package, one Turso database, RS256
tokens. It is not a library and is not published to PyPI.

## Setup

```bash
uv sync
cp .env.example .env.local
uv run radius keys init
uv run radius migrate
```

`.env.local` is gitignored and holds the Turso credentials. Without
`TURSO_DATABASE_URL` radius falls back to a plain local libSQL file at
`RADIUS_DB_PATH`, which is what the tests use — so nothing here requires
network access to run.

`radius keys init` writes `keys/`, also gitignored. Never commit key material,
and never paste a private key or a Turso token into a chat or a commit.

## Commands

| Command | Purpose |
| --- | --- |
| `uv run pytest` | The full suite. Run before every commit |
| `uv run radius serve` | Run the server. Reloads on change; pass `--no-reload` for a long-lived deployment |
| `uv run radius migrate` | Apply the schema |
| `uv run radius ingest FILE` | Upsert bookmarks from a JSON export |
| `uv run radius keys init` | Generate the RS256 key pair and JWKS |
| `uv run radius token issue -c NAME` | Mint a token for a client |
| `uv run radius token inspect TOKEN` | Verify a token and print its claims |

There is no linter configured. Match the surrounding style rather than
reformatting.

## Layout

```
src/radius/
  server/         app.py assembles it; tools.py, resources.py, web.py
  cli.py          The `radius` command
  config.py       Settings, resolved once from the environment
  ingest.py       Raw bookmark JSON -> upserts
  search.py       Fuzzy ranking (rapidfuzz)
  models.py       Tweet / SearchResult
  auth/           keys, scopes, tokens, verifier
  db/             connection, queries, migration.sql, sql/
  static/         index.html — the documentation homepage, served at /
api/mcp.py        Vercel entrypoint
public/           Favicons, MCP icons, fonts, JWKS. Served statically on Vercel
tests/
```

## Conventions

- **Do not add inline comments.** Code should read on its own; reasoning
  belongs in the commit message. Module and function docstrings are used
  throughout and are welcome — running commentary inside a function body is
  not.
- SQL lives in `.sql` files under `src/radius/db/`, not in string literals.
- Commit messages are conventional-ish (`feat:`, `fix:`, `style:`, `docs:`,
  `refactor:`) with a body explaining why, not what.
- Do not commit or push unless asked.

## Architecture

Two layers guard every tool. The `JWTVerifier` passed as `auth` rejects any
request whose bearer token is missing, malformed, expired, or signed by an
unknown key. Then `auth=require_scopes(...)` on each tool means a valid token
only opens the tools its `scope` claim covers — out-of-scope tools are hidden
from `tools/list` entirely.

Custom routes registered with `mcp.custom_route` sit *outside* the auth
middleware, which is why `/`, `/health`, `/.well-known/jwks.json`, and the
asset routes are reachable without a token. Only the MCP endpoint is guarded.

The server is built lazily via `get_server()`. Constructing it reads key
material, so importing `radius.server` on a machine that has never run
`radius keys init` must not fail.

Search has two modes. `exact` hands the query to SQLite FTS5 and ranks by
bm25 — negated into `score` so higher is better. `fuzzy` scans all rows with
rapidfuzz `partial_ratio` and keeps matches of 85 or above.

## Gotchas

- **libSQL is not sqlite3.** No `create_function`, no `row_factory`. Rows are
  mapped to dicts through `cursor.description` in `db/connection.py`.
- **`iss` and `aud` are matched exactly.** Changing `JWT_ISSUER` or
  `JWT_AUDIENCE`, or re-running `keys init --force`, invalidates every token
  already issued. A 401 in production but not locally is almost always this.
- **`JWT_ISSUER` must equal the deployed URL.** The MCP icon URLs and
  `website_url` are derived from it, so a wrong value breaks more than auth.
- **Every Turso write is a network round trip.** A backfill takes minutes; an
  incremental run takes seconds. This is expected, not a hang.
- **Exact search passes the query to FTS5 verbatim**, so `+ - : ^` and
  unbalanced quotes are parse errors rather than empty results.
- **The homepage is cached in memory** by `@lru_cache`, which is why
  `radius serve` watches `.html` as well as `.py`.
- Vercel needs `[tool.vercel] entrypoint` in `pyproject.toml`; `api/mcp.py` is
  not an auto-detected filename.

## Scope

[ROADMAP.md](ROADMAP.md) lists candidate work, numbered so it can be referred
to by number. It is a list of ideas, not a queue — do not pick items off it
unasked.

## Releasing

Versions are SemVer, tagged `vX.Y.Z`. Add entries to the `[Unreleased]`
section of [CHANGELOG.md](CHANGELOG.md) as you go; at release time rename that
heading to `## [X.Y.Z] - YYYY-MM-DD` (ISO 8601), open a fresh `[Unreleased]`
above it, and update the two link references at the foot of the file.

The version string currently lives in three places — `pyproject.toml`,
`src/radius/__init__.py`, and the topbar in `static/index.html`. Bump all
three together until they are single-sourced, or they will drift.

## Verifying a change

`uv run pytest` covers auth, scopes, and the database. For anything touching
the server or the homepage, also start it and check a real response:

```bash
uv run radius serve &
TOKEN=$(uv run radius token issue -c smoke | grep -E '^ey')
curl -s -X POST http://127.0.0.1:9000/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"whoami","arguments":{}}}'
```

A request without the header must return `401` with a `WWW-Authenticate`
header. That, not the absence of a traceback, is the signal auth is wired up.
