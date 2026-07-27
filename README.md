![Hand illustration placed on the left side of the banner](banner.webp)

# radius

**Your bookmarks, as a searchable corpus your AI agent can actually query.**

radius turns a flat pile of saved bookmarks into relational SQLite data and
serves it to any MCP-speaking client over an authenticated HTTP server. No
third-party API access. No passwords stored or scripted. One SQLite file you
own, on hardware you control.

```
bookmark → ingestion → SQLite (FTS5) → search → MCP (JWT) → agent
```

---

**Contents**

[Overview](#overview) · [How it works](#how-it-works) · [Quickstart](#quickstart) ·
[Concepts](#concepts) · [Configuration](#configuration) · [CLI reference](#cli-reference) ·
[MCP API reference](#mcp-api-reference) · [Authentication](#authentication) ·
[Data model](#data-model) · [Operations](#operations) · [Security](#security) ·
[Troubleshooting](#troubleshooting) · [Development](#development) · [Roadmap](#roadmap)

---

## Overview

Bookmarks are a bet on your future self that usually loses — a flat list with
no real search and no way to see how anything relates to anything else. radius
exists to make that bet pay off: ask an agent *"what have I saved about X"* and
get an actual answer, grounded in your own saved data.

**Who it's for.** One person, one corpus, one machine. radius is a personal
tool that happens to speak a standard protocol — not a multi-tenant service.

**What you get today**

| Capability | Detail |
|---|---|
| Ingestion | Cookie-based CLI export → idempotent SQLite upserts, safe to re-run |
| Storage | Real tables — authors, tweets, media — not a JSON blob |
| Search | FTS5 lexical (`exact`) and rapidfuzz similarity (`fuzzy`) |
| Interface | Streamable-HTTP MCP server, `fetch_bookmarks` + `whoami` |
| Auth | RS256 JWTs signed by a local key pair, verified against a published JWKS |
| Authorization | Per-tool scopes — a token opens only what it was minted for |

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
`200`. Then point your MCP client at `http://127.0.0.1:9000/mcp` with that
token as its bearer credential. Consult your client's own docs for connector
configuration — that changes faster than a README can track.

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
| `exact` (default) | SQLite FTS5 | Tokenized lexical match; the query is **FTS5 query syntax** | Negated bm25 relevance |
| `fuzzy` | rapidfuzz `partial_ratio` | Character-level similarity over full content | 0–100, only ≥ 85 returned |

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
| `RADIUS_DB_PATH` | `bookmarks.db` | SQLite corpus location |
| `RADIUS_HOST` | `127.0.0.1` | Server bind address |
| `RADIUS_PORT` | `9000` | Server port |
| `JWT_ISSUER` | `http://127.0.0.1:9000` | Written as `iss`, and required to match on verify |
| `JWT_AUDIENCE` | `radius-mcp` | Written as `aud`, and required to match on verify |
| `JWT_TOKEN_TTL` | `3600` | Default token lifetime in seconds |
| `JWKS_URI` | *unset* | Fetch verification keys over HTTP instead of reading the local public key |
| `RADIUS_PRIVATE_KEY` | `keys/private.pem` | Signing key (mode 0600, never committed) |
| `RADIUS_PUBLIC_KEY` | `keys/public.pem` | Verification key |
| `RADIUS_JWKS_PATH` | `public/.well-known/jwks.json` | Where the published JWKS is written |

Changing `JWT_ISSUER` or `JWT_AUDIENCE` invalidates every token already issued —
that is intentional, and is one way to cut off access.

## CLI reference

Everything runs through one entrypoint. Prefix with `uv run` unless the package
is installed on your `PATH`.

### `radius serve`

Runs the MCP server over streamable HTTP.

| Flag | Description |
|---|---|
| `--host HOST` | Override `RADIUS_HOST` |
| `--port PORT` | Override `RADIUS_PORT` |

### `radius ingest [FILE]`

Loads bookmarks from a raw JSON export. Applies the schema first, so there is no
separate migrate step. Defaults to `bookmarks.json` in the project root.

| Flag | Description |
|---|---|
| `--db PATH` | Target database, overriding `RADIUS_DB_PATH` |

### `radius migrate`

Applies the schema on its own. Every statement is `IF NOT EXISTS`, so it is
re-runnable.

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
| `POST` | `/mcp` | **Bearer token** | MCP streamable-HTTP endpoint |
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

Because it's plain SQLite, the corpus is queryable directly whenever the MCP
layer is more ceremony than you need:

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

`bookmarks.db` is the whole corpus and is gitignored — it holds your data, so it
is not committed. Back it up like any other file you'd hate to lose:

```bash
sqlite3 bookmarks.db ".backup 'bookmarks-$(date +%F).db'"
```

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

## Development

```bash
uv sync           # install, including dev dependencies
uv run pytest     # 21 tests
uvx ruff check src tests
uvx ruff format src tests
```

The test suite covers key generation and token round-trips, rejection of
tampered/expired/foreign-audience tokens, HTTP-level `401`s against a live ASGI
app, and per-tool scope filtering — including an invariant test that fails if a
tool is ever registered without an auth check.

```
radius/
├── src/radius/
│   ├── server.py           # MCP server: tools + their scope guards
│   ├── config.py           # env-driven settings
│   ├── cli.py              # the `radius` command
│   ├── models.py           # Author / Tweet / Media / SearchResult
│   ├── search.py           # FUZZY_SCORE, registered as a SQLite function
│   ├── ingest.py           # raw JSON → SQLite upserts
│   ├── auth/
│   │   ├── keys.py         # RSA key pair + JWKS
│   │   ├── tokens.py       # mint and inspect tokens
│   │   ├── scopes.py       # the scope vocabulary
│   │   └── verifier.py     # the JWTVerifier the server runs on
│   └── db/
│       ├── connection.py   # connections, pragmas, migrations
│       ├── queries.py      # SQL loader
│       ├── migration.sql   # schema
│       └── sql/            # one file per query
├── tests/
├── keys/                   # generated, gitignored
├── bookmarks.db            # the corpus itself, gitignored
└── pyproject.toml
```

Adding a tool is two lines in `server.py` — a function, and a registration
carrying `auth=require_scopes(...)`. New scopes go in `auth/scopes.py`, which is
also what makes them accepted by `token issue`.

## Roadmap

| Planned | Notes |
|---|---|
| Semantic search | `sqlite-vec` embeddings fused with FTS5 via reciprocal rank fusion |
| Thread reconstruction | Reply and quote chains via recursive SQL — schema columns already exist |
| Author lookup | `get_author_bookmarks` over the existing `authors` join |
| Remote hosting | Deployment as a remote MCP server |

## License

MIT.
