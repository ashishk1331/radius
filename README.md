![Hand illustration placed on the left side of the banner](banner.webp)

# radius

**Your bookmarks, as a searchable corpus your AI agent can actually query.**

radius turns a flat pile of saved bookmarks into relational libSQL data and
serves it to any MCP-speaking client over an authenticated HTTP server. No
third-party API access. No passwords stored or scripted. One database — a
Turso instance you own — read by your laptop and your deployment alike, with
nothing to keep in step between them.

```
bookmark → ingestion → Turso (libSQL + FTS5) → search → MCP (JWT) → agent
```

---

**Contents**

[Overview](#overview) · [How it works](#how-it-works) · [Quickstart](#quickstart) ·
[Using radius](#using-radius) · [Concepts](#concepts) ·
[Configuration](#configuration) · [CLI reference](#cli-reference) ·
[MCP API reference](#mcp-api-reference) · [Authentication](#authentication) ·
[Data model](#data-model) · [Operations](#operations) ·
[Deploying to Vercel](#deploying-to-vercel) · [Security](#security) ·
[Troubleshooting](#troubleshooting) · [Development](#development) · [Roadmap](#roadmap)

---

## Overview

Bookmarks are a bet on your future self that usually loses — a flat list with
no real search and no way to see how anything relates to anything else. radius
exists to make that bet pay off: ask an agent *"what have I saved about X"* and
get an actual answer, grounded in your own saved data.

**Who it's for.** One person, one corpus. radius is a personal tool that
happens to speak a standard protocol — not a multi-tenant service.

**What you get today**

| Capability | Detail |
|---|---|
| Ingestion | Cookie-based CLI export → idempotent libSQL upserts, safe to re-run |
| Storage | One Turso database. Real tables — authors, tweets, media — not a JSON blob |
| Search | FTS5 lexical (`exact`) and rapidfuzz similarity (`fuzzy`) |
| Interface | Streamable-HTTP MCP server, `fetch_bookmarks` + `whoami` |
| Auth | RS256 JWTs signed by a local key pair, verified against a published JWKS |
| Authorization | Per-tool scopes — a token opens only what it was minted for |
| Hosting | Runs locally, or as a single Python Function on Vercel |

**What it deliberately does not do.** Script a login, store a password, store a
credential of any kind, phone home, or require a cloud account to run.

## How it works

```
┌──────────────┐     ┌──────────────┐     ┌────────────────────┐
│  cron job    │────▶│   ingest     │────▶│    bookmarks.db    │
│ (cookie CLI) │     │  (upserts)   │     │  tables + FTS5     │
└──────────────┘     └──────────────┘     └─────────┬──────────┘
                                                    │
                                          ┌─────────▼──────────┐
                                          │  exact / fuzzy     │
                                          │  search queries    │
                                          └─────────┬──────────┘
                                                    │
                                          ┌─────────▼───────────┐
                                          │  MCP server         │
                                          │  JWT + tool scopes  │
                                          └─────────┬───────────┘
                                                    │
                                          ┌─────────▼───────────┐
                                          │  Claude / any MCP   │
                                          │  client             │
                                          └─────────────────────┘
```

Writes only ever happen locally, from the ingestion job. The server reads the
database read-only.

## Quickstart

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/), and a
cookie-based bookmark export CLI you've already installed and authenticated
(radius does not install or configure one for you).

```bash
# 1. Install
git clone <this-repo-url> radius && cd radius
uv sync
cp .env.example .env.local

# 2. Generate the token signing key
uv run radius keys init

# 3. Load your bookmarks (applies the schema automatically)
bookmark-cli bookmarks --json --all --max-pages 500 > bookmarks.json
uv run radius ingest bookmarks.json

# 4. Mint a token for your client
uv run radius token issue --client claude-desktop

# 5. Serve
uv run radius serve
```

Verify it's up and guarded:

```bash
curl http://127.0.0.1:9000/health                  # 200, public
curl -i -X POST http://127.0.0.1:9000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"c","version":"0"}}}'
# → 401 Unauthorized, with a WWW-Authenticate challenge
```

Add `-H "Authorization: Bearer <your-token>"` to the same call and it returns
`200`. Now connect a client — see below.

## Using radius

### Connect Claude Code

```bash
uv run radius serve                                    # in one terminal

TOKEN=$(uv run radius token issue -c claude-code --ttl 2592000 | tail -2 | head -1)
claude mcp add --transport http radius http://127.0.0.1:9000/mcp \
  --header "Authorization: Bearer $TOKEN"
```

Confirm it took:

```bash
claude mcp list
# radius: http://127.0.0.1:9000/mcp (HTTP) - ✔ Connected
```

Remove it again with `claude mcp remove radius`.

### Connect another MCP client

Any client that speaks streamable HTTP needs two things: the URL
`http://127.0.0.1:9000/mcp`, and the header
`Authorization: Bearer <your-token>`. Where you put those varies by client and
changes faster than a README can track — check your client's current connector
docs. Clients that only speak stdio need a stdio-to-HTTP bridge in front of
radius.

### Ask your bookmarks something

Once connected, the point is that you stop thinking about tools at all. The
agent picks `fetch_bookmarks` on its own:

> *What have I saved about local-first software?*

> *Find that thread I bookmarked about SQLite performance — I think it
> mentioned WAL mode.*

> *Who do I bookmark most often about Rust?*

Two habits make results better. Say the mode when you know the wording is
approximate — *"search my bookmarks fuzzily for parsr"* — and ask for more
results when you're surveying rather than looking something up, since the
default is 5 and the ceiling is 50.

`whoami` is there for when a client misbehaves: *"call whoami"* tells you which
token it is actually using and when that token expires.

### Call the tools directly

No agent required — useful for scripting or debugging:

```python
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

TOKEN = "<your-token>"


async def main():
    transport = StreamableHttpTransport("http://127.0.0.1:9000/mcp", auth=TOKEN)
    async with Client(transport) as client:
        result = await client.call_tool(
            "fetch_bookmarks", {"query": "rust", "search_mode": "exact", "top_k": 3}
        )
        for row in result.structured_content["result"]:
            print(f"[{row['score']:.2f}] @{row['handle']}: {row['content'][:70]}")


asyncio.run(main())
```

For a plain SQL query against the same data, skip the server entirely — see
[Data model](#data-model).

### When the token expires

Tokens default to a one-hour life, which is fine for a scripted call and
annoying for a client you leave connected. Mint longer-lived ones with `--ttl`
(`2592000` is 30 days), and understand the tradeoff before you do: there is no
per-token revocation, so a long-lived token that leaks stays valid until it
expires or you rotate the key. See [Security](#security).

An expired token shows up as a `401`, or as a client that lists no tools.
Reissue and update the client's header:

```bash
uv run radius token inspect "$TOKEN"   # check `exp` before assuming
```

## Concepts

### The corpus

Every bookmark becomes a row in `tweets`, joined to an `authors` row and any
number of `media` rows. Ingestion is **upsert-based and idempotent**: re-running
it on an overlapping export updates existing rows rather than duplicating them,
so a cron job that re-pulls the last N pages is safe.

### Search modes

`fetch_bookmarks` takes a `search_mode`. Both return the same shape, and in
both, **higher `score` is better**.

| Mode | Engine | Matching | Score |
|---|---|---|---|
| `exact` (default) | FTS5, in the database | Tokenized lexical match; the query is **FTS5 query syntax** | Negated bm25 relevance |
| `fuzzy` | rapidfuzz `partial_ratio`, in Python | Character-level similarity over full content | 0–100, only ≥ 85 returned |

`fuzzy` scores in the application rather than in SQL. libSQL has no
`create_function`, and a hosted database cannot call back into Python
regardless — so it pulls the candidate rows and ranks them in process.

That has a measurable cost against Turso: `exact` ranks inside the database and
returns in ~0.2s warm, while `fuzzy` transfers every row first and takes ~1.5s
over a 200-bookmark corpus. Reach for `exact` by default, and treat `fuzzy` as
the fallback for approximate or misspelled wording.

Pick `exact` for keyword and phrase lookups (`"local first"`, `sql*`,
`AI OR agents`). Pick `fuzzy` when the wording is approximate or misspelled, or
when the query contains characters FTS5 treats as operators — see
[Troubleshooting](#troubleshooting).

### Tokens and scopes

radius is its own token issuer. Access is a signed JWT carrying a `sub` (the
client name), an expiry, and a `scope` claim. Scopes gate individual tools, so a
token can be narrower than "full access".

| Scope | Grants |
|---|---|
| `bookmarks:read` | `fetch_bookmarks`, `whoami` |

Nothing about an issued token is stored server-side — there is no session table,
no key table, no credential store.

## Configuration

Settings resolve from the environment, layered: `.env.<RADIUS_ENV>` first, then
`.env`. Real environment variables always win over both. `RADIUS_ENV` defaults
to `local`, so `.env.local` is what loads unless you say otherwise.

Relative paths resolve against the project root.

| Variable | Default | Purpose |
|---|---|---|
| `RADIUS_ENV` | `local` | Which `.env.<name>` file to load |
| `RADIUS_HOME` | auto-detected | Project root override, for paths and env files |
| `RADIUS_DB_PATH` | `bookmarks.db` | Local file, used only when no Turso URL is set |
| `TURSO_DATABASE_URL` | *unset* | The corpus. Unset falls back to a local file, for tests and offline work |
| `TURSO_AUTH_TOKEN` | *empty* | Turso credential. Needs write access for ingestion |
| `RADIUS_HOST` | `127.0.0.1` | Server bind address |
| `RADIUS_PORT` | `9000` | Server port |
| `JWT_ISSUER` | `http://127.0.0.1:9000` | Written as `iss`, and required to match on verify |
| `JWT_AUDIENCE` | `radius-mcp` | Written as `aud`, and required to match on verify |
| `JWT_TOKEN_TTL` | `3600` | Default token lifetime in seconds |
| `JWKS_URI` | *unset* | Fetch verification keys over HTTP instead of reading the local public key |
| `RADIUS_PRIVATE_KEY` | `keys/private.pem` | Signing key (mode 0600, never committed) |
| `RADIUS_PUBLIC_KEY` | `keys/public.pem` | Verification key |
| `RADIUS_PUBLIC_KEY_PEM` | *unset* | Verification key inline, for hosts with no key file. Wins over the path |
| `RADIUS_JWKS_PATH` | `public/.well-known/jwks.json` | Where the published JWKS is written |

Changing `JWT_ISSUER` or `JWT_AUDIENCE` invalidates every token already issued —
that is intentional, and is one way to cut off access.

## CLI reference

Everything runs through one entrypoint. Prefix with `uv run` unless the package
is installed on your `PATH`.

### `radius serve`

Runs the MCP server over streamable HTTP, and serves the documentation page at
`/`.

| Flag | Description |
|---|---|
| `--host HOST` | Override `RADIUS_HOST` |
| `--port PORT` | Override `RADIUS_PORT` |
| `--no-reload` | Serve once, without the file watcher. Use this in production |

Reload is on by default, watching `src/radius` for `.py`, `.html` and `.sql`
changes. The HTML and SQL are included deliberately: the homepage is cached in
memory and queries are read once at import, so without a restart neither would
pick up an edit.

Reloading runs a supervisor process that re-imports the app on every change, so
pass `--no-reload` when you are running this as a long-lived service rather than
developing against it.

### `radius ingest [FILE]`

Loads bookmarks from a raw JSON export. Applies the schema first, so there is no
separate migrate step. Defaults to `bookmarks.json` in the project root.

| Flag | Description |
|---|---|
| `--db PATH` | Target database, overriding `RADIUS_DB_PATH` |

### `radius migrate`

Applies the schema on its own, to whichever database the configuration points
at. Every statement is `IF NOT EXISTS`, so it is re-runnable. Prints the
connection mode it used.

| Flag | Description |
|---|---|
| `--db PATH` | Target database |

### `radius keys init`

Generates the RSA-2048 key pair and writes the JWKS document. Run once at setup.

| Flag | Description |
|---|---|
| `--force` | Rotate an existing key. **Invalidates every issued token.** |

### `radius keys show`

Prints the public JWKS as JSON. Contains no private material.

### `radius token issue`

Mints a signed token.

| Flag | Description |
|---|---|
| `-c, --client NAME` | **Required.** Client identifier, becomes the `sub` claim |
| `-s, --scope SCOPE` | Scope to grant, repeatable. Defaults to `bookmarks:read` |
| `--ttl SECONDS` | Lifetime, overriding `JWT_TOKEN_TTL` |

Unknown scopes are rejected at mint time rather than silently granted.

### `radius token inspect TOKEN`

Verifies a token against the local public key and prints its claims. Exits
non-zero with an explanation if the signature, issuer, audience, or expiry
fails.

## MCP API reference

### Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/mcp` | **Bearer token** | MCP streamable-HTTP endpoint. Deployed on Vercel this is `/api/mcp` — see [Deploying to Vercel](#deploying-to-vercel) |
| `GET` | `/health` | Public | Liveness check, returns `{"status":"ok"}` |
| `GET` | `/.well-known/jwks.json` | Public | Published verification keys |

The two public routes sit outside the auth middleware by design — a JWKS
document that required a token would be useless, and a health check that
required one would not be a health check.

### `fetch_bookmarks`

Top-k bookmark search. Requires `bookmarks:read`.

**Input**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | *required* | Search string. In `exact` mode this is FTS5 query syntax |
| `search_mode` | `"exact"` \| `"fuzzy"` | `"exact"` | Matching strategy |
| `top_k` | integer | `5` | Result count, clamped to 1–50 |

**Output** — an array of results, ordered by descending `score`:

| Field | Type | Description |
|---|---|---|
| `id` | string | Tweet ID |
| `handle` | string | Author handle |
| `display_name` | string | Author display name |
| `content` | string | Full bookmark text |
| `created_at` | string | Original creation timestamp |
| `score` | number | Relevance, higher is better |

```json
{
  "name": "fetch_bookmarks",
  "arguments": { "query": "rust", "search_mode": "exact", "top_k": 2 }
}
```

```json
[
  {
    "id": "2059675872408260816",
    "handle": "llama_index",
    "display_name": "LlamaIndex 🦙",
    "content": "LiteParse v2.0 is out now, and it is blazing fast…",
    "created_at": "Wed May 27 16:39:29 +0000 2026",
    "score": 4.91
  }
]
```

### `whoami`

Echoes the identity behind the calling token. Requires `bookmarks:read`. Takes
no arguments. Useful for confirming a client is authenticating as who you think
it is.

```json
{
  "client": "claude-desktop",
  "scopes": ["bookmarks:read"],
  "issuer": "http://127.0.0.1:9000",
  "expires_at": 1785148279
}
```

### Errors

| Condition | Response |
|---|---|
| Missing, malformed, expired, or wrongly-signed token | `401` with a `WWW-Authenticate` challenge |
| Wrong `iss` or `aud` | `401` |
| Valid token lacking the tool's scope | Tool is absent from `tools/list`; calling it returns *unknown tool* |
| Invalid FTS5 syntax in `exact` mode | Tool error from SQLite — see [Troubleshooting](#troubleshooting) |

Out-of-scope tools report *unknown tool* rather than *forbidden* so that a
narrow token learns nothing about what it cannot reach.

## Authentication

One local RSA key pair signs every token. The public half is published as a
JWKS, and the server verifies against it.

```
radius token issue ──signs with──▶ keys/private.pem
                                        │
        client ──Bearer JWT──▶ MCP ──verifies with──▶ keys/public.pem
                                        │              (or JWKS_URI)
                                        ▼
                              require_scopes per tool
```

Two independent checks run on every call:

1. **Token verification.** Requests whose token is missing, malformed, expired,
   signed by an unknown key, or carrying the wrong `iss`/`aud` are rejected
   before any tool code runs.
2. **Per-tool scopes.** A valid token still only opens the tools its `scope`
   claim covers.

### Token claims

| Claim | Value |
|---|---|
| `sub` | Client name from `--client` |
| `iss` / `aud` | `JWT_ISSUER` / `JWT_AUDIENCE`, both matched on verify |
| `iat` / `exp` | Issued-at and expiry, from `--ttl` or `JWT_TOKEN_TTL` |
| `jti` | Unique token ID |
| `scope` | Space-separated granted scopes |

Signed RS256; the JWS header carries a `kid` set to the key's RFC 7638
thumbprint.

### Local vs. remote key distribution

Leave `JWKS_URI` **unset** when one process both signs and serves — the
verifier reads `keys/public.pem` directly instead of making an HTTP call to
itself. Set it only when the verifier must fetch keys from a *separate* issuer
process, which is the case if you split signing and serving across hosts.

### Rotation

```bash
uv run radius keys init --force
```

Generates a new pair and republishes the JWKS. Every previously issued token
stops verifying immediately. This is the blunt instrument — see
[Security](#security) for what that means for per-client revocation.

## Data model

```sql
authors(id PK, display_name, handle UNIQUE, avatar)
tweets(id PK, author_id → authors.id, content, created_at,
       in_reply_to_id → tweets.id, quoted_tweet_id → tweets.id)
media(id PK, tweet_id → tweets.id, link, kind, UNIQUE(tweet_id, link))
tweets_fts  -- FTS5 index over tweets.content, kept in sync by triggers
```

`in_reply_to_id` and `quoted_tweet_id` exist in the schema but are not yet
populated by ingestion — they are groundwork for thread reconstruction (see
[Roadmap](#roadmap)).

libSQL is a SQLite fork and the file is a SQLite file, so the corpus stays
queryable with ordinary tooling whenever the MCP layer is more ceremony than
you need:

```bash
sqlite3 bookmarks.db "SELECT handle, content FROM tweets JOIN authors ON author_id = authors.id LIMIT 5"
```

### Expected ingestion input

`radius ingest` reads the JSON shape produced by the bookmark export CLI:

```jsonc
{
  "data": [
    {
      "id": "2059675872408260816",
      "text": "…",
      "createdAt": "Wed May 27 16:39:29 +0000 2026",
      "author": {
        "id": "…", "screenName": "…", "name": "…", "profileImageUrl": "…"
      },
      "media": [{ "url": "…", "type": "photo" }]
    }
  ]
}
```

Additional fields in the export are ignored.

## Operations

### Scheduled sync

```bash
crontab -e
# every 6 hours
0 */6 * * * cd /path/to/radius && uv run radius ingest bookmarks.json >> ~/logs/radius-sync.log 2>&1
```

Your export command belongs in the same job, writing `bookmarks.json` before
`radius ingest` reads it. Because upserts are idempotent, overlapping pulls cost
nothing but time.

### Backfill

Incremental sync alone will not surface bookmarks saved before you started. Run
one full pull by hand before enabling cron:

```bash
bookmark-cli bookmarks --json --all --max-pages 500 > bookmarks.json
uv run radius ingest bookmarks.json
```

### Backup

The corpus lives in Turso, which handles its own durability. What that does not
cover is you: a bad ingestion upserts into the live database just as happily as
a good one, and there is no second copy to fall back to. Keep your
`bookmarks.json` exports, and take a dump before anything destructive:

```bash
turso db shell radius .dump > radius-$(date +%F).sql
```

## Deploying to Vercel

radius deploys as a single Python Function. Vercel's own MCP documentation is
TypeScript-only (`mcp-handler`), but none of it is needed, and no port is
required: the [Python runtime](https://vercel.com/docs/functions/runtimes/python)
runs ASGI apps and runs the lifespan protocol, which is the one thing FastMCP's
session manager needs. This path is deployed and working — a running
deployment answers `tools/call` in about 1.6s including the Turso round trip.

### What deploys, and how it differs

Vercel builds from git. The corpus and the key files are gitignored and never
reach the deployment — the corpus is already in Turso, and the verification key
arrives as an environment variable.

Everything about the Function lives in [`api/mcp.py`](api/mcp.py), which differs
from `radius serve` in three ways:

| | Why |
|---|---|
| Mounted at `/api/mcp` | Vercel has two Python routing behaviours — a file under `api/` becomes a Function at its own path, and a detected framework entrypoint receives every path. `/api/mcp` is correct under both, and matches the URL shape Vercel's MCP docs use |
| `stateless_http=True` | A request may land on any instance, so the transport cannot assume a session an earlier request established |
| `json_response=True` | One ordinary JSON response per POST instead of a streamed SSE event — the simpler contract for a request-scoped Function |

### Pipeline

```
 ┌── local ────────────────────────┐        ┌── Vercel ───────────────┐
 │  cron → radius ingest           │        │  api/mcp.py             │
 │  radius token issue (private ───┼── PEM ─┼─▶ verifies with          │
 │    key never leaves here)       │ public │   RADIUS_PUBLIC_KEY_PEM │
 └───────────────┬─────────────────┘        └────────────┬────────────┘
                 │ writes                        reads   │
                 └──────────▶ Turso ◀────────────────────┘
                            (one database)
```

Data and code deploy on separate tracks: `git push` ships code, ingestion ships
bookmarks. Neither waits on the other.

### 1. Create the database

```bash
turso db create radius
turso db show radius --url          # → TURSO_DATABASE_URL
turso db tokens create radius       # → TURSO_AUTH_TOKEN
```

Put both in `.env.local` and ingest. From here on that hosted database *is* the
corpus — your local runs read the same rows production will:

```bash
uv run radius migrate
uv run radius ingest bookmarks.json
```

### 2. Generate the signing key, if you have not

```bash
uv run radius keys init
```

### 3. Link the project

```bash
npx vercel login
npx vercel link
```

`link` creates `.vercel/` locally and asks which scope and project to use. It is
gitignored.

### 4. Set the environment

Five variables. Add each to the Production environment:

```bash
npx vercel env add TURSO_DATABASE_URL production
npx vercel env add TURSO_AUTH_TOKEN production
npx vercel env add JWT_ISSUER production        # https://<your-app>.vercel.app
npx vercel env add JWT_AUDIENCE production      # radius-mcp
npx vercel env add RADIUS_PUBLIC_KEY_PEM production < keys/public.pem
```

| Variable | Value |
|---|---|
| `TURSO_DATABASE_URL` | your Turso URL |
| `TURSO_AUTH_TOKEN` | your Turso token |
| `RADIUS_PUBLIC_KEY_PEM` | contents of `keys/public.pem` |
| `JWT_ISSUER` | `https://your-app.vercel.app` |
| `JWT_AUDIENCE` | `radius-mcp` |

Only the **public** key goes to Vercel. The private key never leaves your
machine, so tokens can only ever be minted locally.

`JWT_ISSUER` must match the deployed URL exactly. You will not know it until the
first deploy, so it is fine to deploy once, read the URL, then set this and
redeploy.

### 5. Deploy

```bash
npx vercel --prod
```

### 6. Verify

```bash
curl https://<your-app>.vercel.app/api/mcp \
  -X POST -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
# → 401, with a WWW-Authenticate challenge. Auth is live.
```

Then mint a token for the deployed issuer and try it for real:

```bash
TOKEN=$(JWT_ISSUER=https://<your-app>.vercel.app \
  uv run radius token issue -c claude --ttl 2592000 | tail -2 | head -1)

curl https://<your-app>.vercel.app/api/mcp \
  -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"whoami","arguments":{}}}'
```

`whoami` is the fastest end-to-end check: it proves the token verified and the
Function is running, without touching the database. Follow it with a
`fetch_bookmarks` call to prove Turso is reachable too.

Three signals are worth reading carefully, because each isolates a different
layer:

| Response | What it proves |
|---|---|
| `401` with `WWW-Authenticate` | The Function booted and the ASGI lifespan ran. Without the lifespan FastMCP's session manager raises, so a clean rejection means the whole chain is up |
| `/.well-known/jwks.json` returns your key | `RADIUS_PUBLIC_KEY_PEM` survived with its newlines intact. Compare the `kid` against `radius keys show` |
| `whoami` returns your client name | `JWT_ISSUER` matches what you minted against |

### 7. Connect a client

```bash
claude mcp add --transport http radius https://<your-app>.vercel.app/api/mcp \
  --header "Authorization: Bearer $TOKEN"
```

**Keeping it current.** Ingestion runs locally on cron and writes straight to
Turso, so new bookmarks are live the moment the job finishes — no redeploy in
the loop. The deployment only changes when the code does.

## Security

**Credential posture**

- No raw password is ever stored or scripted — only the browser session you
  already established
- No credentials are stored at all: auth is stateless, signed JWTs
- The private key and every `.env` file are gitignored and have never been
  committed

**Access control**

- Everything under `/mcp` requires a valid token; `/health` and the JWKS are
  public by design
- Tokens are issued per client and per scope, and expire on their own
- Unknown scopes are rejected when minting, not silently granted

**Known limitation — revocation is all-or-nothing.** There is no per-token
denylist. Cutting off one leaked token before it expires means rotating the key
(`radius keys init --force`), which invalidates *every* client's token and
requires reissuing them all. Keep `JWT_TOKEN_TTL` short — the default hour is a
reasonable ceiling on the blast radius of a leak. Independently revocable,
long-lived per-client access would need a full OAuth 2.1 flow instead.

**Exposure.** The default bind is `127.0.0.1`. Before binding to `0.0.0.0`,
understand that the corpus is your entire bookmark history and the only thing
between it and the network is a bearer token.

## Troubleshooting

**`401` on every request.** Confirm the token's `iss` and `aud` match the
server's current config — `radius token inspect <token>` prints both. Tokens
minted before an `JWT_ISSUER`/`JWT_AUDIENCE` change, or before a
`keys init --force`, will never verify again.

**`MissingKeyError: no key found at keys/public.pem`.** You have not run
`radius keys init`. Importing the server no longer fails on this, but starting
it does.

**A tool is missing from `tools/list`.** The token lacks that tool's scope. Run
`whoami` to see what it actually carries, and reissue with `--scope` if needed.

**`fts5: syntax error near "+"`.** In `exact` mode the query goes to FTS5
verbatim, so characters it treats as operators (`+`, `-`, `:`, `^`, unbalanced
quotes) are parse errors. Quote the term (`"c++"`) or switch to
`search_mode: "fuzzy"`, which does plain string similarity.

**`fuzzy` returns nothing.** It only returns matches scoring ≥ 85 out of 100.
Below that threshold the results were noise, so there is no partial-credit tier.

**Empty results after ingestion.** Confirm rows actually landed:
`sqlite3 bookmarks.db "SELECT COUNT(*) FROM tweets"`. If that count is zero,
check that the export JSON has a top-level `data` array.

**Ingestion takes minutes.** Every write is a round trip to Turso — roughly
300 ms to a distant region — and a backfill issues one per author, tweet, and
media row. A 200-bookmark backfill lands in a few minutes. Incremental cron
runs only write what changed and finish in seconds, so this is a one-time cost.
Picking a Turso region near you is the cheapest improvement.

**Production returns no bookmarks but works locally.** Almost always means
`TURSO_DATABASE_URL` is missing from the Vercel environment, so the Function
fell back to `local` mode and opened an empty file that ships with no data.
`radius migrate` prints the mode it resolved; `whoami` confirms the deployment
is otherwise healthy.

**`401` in production only.** `JWT_ISSUER` differs between your machine and the
deployment, and it is matched exactly. Mint production tokens with the
production issuer, as shown in [Deploying to Vercel](#deploying-to-vercel).

## Development

```bash
uv sync           # install, including dev dependencies
uv run pytest     # 30 tests
uvx ruff check src tests
uvx ruff format src tests
```

Tests run in `local` mode against throwaway libSQL files, so the suite needs no
Turso account and no network.

It covers key generation and token round-trips, rejection of
tampered/expired/foreign-audience tokens, HTTP-level `401`s against a live ASGI
app, per-tool scope filtering — including an invariant test that fails if a tool
is ever registered without an auth check — and the data layer: mode selection,
row mapping, FTS5 ranking, fuzzy thresholds, and transaction rollback.

```
radius/
├── api/
│   └── mcp.py              # Vercel entrypoint (stateless + JSON responses)
├── src/radius/
│   ├── server/
│   │   ├── app.py          # assembly: verifier, scope guards, lifecycle
│   │   ├── tools.py        # the calls the model makes
│   │   ├── resources.py    # bookmark://<id>, read by the client
│   │   └── web.py          # homepage assembly, icons, fonts, favicons
│   ├── config.py           # env-driven settings
│   ├── cli.py              # the `radius` command
│   ├── models.py           # Author / Tweet / Media / SearchResult
│   ├── search.py           # fuzzy scoring, applied in Python
│   ├── ingest.py           # raw JSON → libSQL upserts
│   ├── static/
│   │   ├── index.html      # the page template, served at /
│   │   └── diagrams/       # SVG fragments inlined into it
│   ├── auth/
│   │   ├── keys.py         # RSA key pair + JWKS
│   │   ├── tokens.py       # mint and inspect tokens
│   │   ├── scopes.py       # the scope vocabulary
│   │   └── verifier.py     # the JWTVerifier the server runs on
│   └── db/
│       ├── connection.py   # Turso / local connections, row mapping
│       ├── queries.py      # SQL loader
│       ├── migration.sql   # schema
│       └── sql/            # one file per query
├── public/                 # styles.css, app.js, icons, fonts, JWKS
├── tests/
├── keys/                   # generated, gitignored
├── bookmarks.db            # the corpus itself, gitignored
├── vercel.json
└── pyproject.toml
```

The page is split by how each piece reaches the browser. `public/` holds
everything fetched by URL, which Vercel serves straight from its CDN; the HTML
template and its `{{ diagrams/name.svg }}` fragments stay in the package, since
an inlined SVG inherits the page's theme variables where one loaded through
`<img>` could not.

Adding a tool is two lines — a function in `server/tools.py`, and a registration
in `server/app.py` carrying `auth=require_scopes(...)`. Resources follow the same
shape from `server/resources.py`. New scopes go in `auth/scopes.py`, which is
also what makes them accepted by `token issue`.

## Roadmap

| Planned | Notes |
|---|---|
| Semantic search | Embeddings fused with FTS5 via reciprocal rank fusion |
| Thread reconstruction | Reply and quote chains via recursive SQL — schema columns already exist |
| Author lookup | `get_author_bookmarks` over the existing `authors` join |

## License

MIT — see [LICENSE](LICENSE). Built by
[Ashish Khare](https://github.com/ashishk1331).
