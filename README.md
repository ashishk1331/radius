![Hand illustration placed on the left side of the banner](banner.webp)

# radius

A local-first pipeline that turns your saved bookmarks into a searchable,
relational corpus — and exposes it to AI agents (like Claude) through an
authenticated MCP server.

No third-party API access required. No passwords stored or scripted anywhere.
Runs on a single SQLite file you own.

```
bookmark → cron ingestion → SQLite (FTS5 + vectors) → hybrid search → MCP → agent
```

## What this is

`radius` pulls your bookmarks on a schedule using your browser's existing
logged-in session (cookies), stores them as real relational data — not a flat
JSON blob — and makes that corpus queryable two ways: directly via SQL, and
remotely via an MCP server that an agent can call to search, reconstruct
threads, and look up authors.

- **Ingestion** — a cron job + cookie-based CLI tool, no password automation
- **Storage** — SQLite, with tweets/authors/hashtags/mentions as proper tables
- **Search** — FTS5 (exact/lexical) + `sqlite-vec` (semantic) combined via
  reciprocal rank fusion
- **Relationships** — reply chains and quote chains via recursive SQL, no
  graph database required
- **Interface** — an MCP server exposing `search_bookmarks`, `get_thread`,
  `get_author_bookmarks`
- **Auth** — hashed, per-client API keys with revocation and rate limiting
- **Hosting** — deployed on Vercel as a remote, streamable-HTTP MCP server

## Why

Bookmarks are a bet on your future self that usually loses — a flat list with
no real search and no way to see how anything relates to anything else.
`radius` exists to make that bet pay off: ask an agent "what have I saved
about X" and get an actual answer, grounded in your own saved data.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌────────────────────┐
│  cron job    │────▶│ ingest.py    │────▶│  bookmarks.sqlite  │
│ (cookie CLI) │     │ (upserts)    │     │  tables + FTS5 +   │
└──────────────┘     └──────────────┘     │  vector index      │
                                          └─────────┬──────────┘
                                                    │
                                          ┌─────────▼──────────┐
                                          │  hybrid_search /   │
                                          │  relationship CTEs │
                                          └─────────┬──────────┘
                                                    │
                                          ┌─────────▼───────────┐
                                          │  MCP server (auth)  │
                                          │  deployed on Vercel │
                                          └─────────┬───────────┘
                                                    │
                                          ┌─────────▼───────────┐
                                          │  Claude / any MCP   │
                                          │  client             │
                                          └─────────────────────┘
```

## Prerequisites

- Python 3.11+
- Node.js + npm (for the Vercel CLI)
- SQLite3 CLI
- A cookie-based CLI tool already installed and authenticated against your
  bookmarking platform (this repo doesn't install or configure one for you)
- A [Vercel](https://vercel.com) account, free tier is enough

## Setup

**1. Clone and install**

```bash
git clone <this-repo-url> radius
cd radius
pip install -r requirements.txt --break-system-packages
npm install -g vercel
```

**2. Authenticate the ingestion tool**

Log into your bookmarking platform in a real browser (2FA on). `radius`
never scripts a login — it reads the session that's already there.

**3. One-time backfill**

Existing bookmarks won't show up via incremental sync alone. Run a full pull
once, by hand, before turning on cron:

```bash
bookmark-cli bookmarks --json --all --max-pages 500 > raw/backfill-initial.json
python3 ingest.py raw/backfill-initial.json
```

**4. Schedule ongoing sync**

```bash
crontab -e
# every 6 hours
0 */6 * * * /path/to/radius/scripts/bookmark-sync.sh >> ~/logs/radius-sync.log 2>&1
```

**5. Generate an API key**

```bash
python3 scripts/generate_key.py --client-name "claude-desktop"
```

Save the printed key — only its hash is stored, so it can't be recovered
later.

**6. Test locally**

```bash
vercel dev
curl -X POST http://localhost:3000/api/mcp \
  -H "Authorization: Bearer <your-key>" \
  -H "Content-Type: application/json" \
  -d '{"tool": "search_bookmarks", "arguments": {"query": "test"}}'
```

**7. Deploy**

```bash
vercel --prod
```

**8. Connect an MCP client**

Point Claude (or any MCP-speaking client) at your deployed URL with the API
key as a bearer token. Check your client's current docs for exact connector
configuration — this changes across clients faster than a README can track.

## MCP tools exposed

| Tool | Description |
|---|---|
| `search_bookmarks` | Hybrid full-text + semantic search, returns full content ranked by fused relevance |
| `get_thread` | Reconstructs the full reply chain a bookmark belongs to |
| `get_author_bookmarks` | All bookmarked tweets from a given author |

## Storage

The SQLite file is committed to this repo and read by the deployed Vercel
functions (read-only in production). All writes happen from the ingestion
cron job running locally, which commits and pushes the updated file. See
`docs/` for the tradeoffs against a managed storage backend if you need
on-demand, real-time sync instead.

## Security

- No raw password is ever stored or scripted — only session cookies
- API keys are stored as salted hashes, never in plaintext
- Every endpoint requires a valid, non-revoked key except `/health`
- Keys are issued per client, so one leak can be revoked without affecting
  others
- Rate limiting is enforced per key
- All secrets live in Vercel's environment variable store, never committed

See `docs/security-checklist.md` for the full list.

## Repository structure

```
radius/
├── api/
│   └── mcp.py            # MCP server entrypoint
├── lib/
│   ├── search.py          # hybrid_search, top_k_bookmarks
│   ├── graph.py           # thread/relation queries
│   └── auth.py            # key verification, rate limiting
├── scripts/
│   ├── bookmark-sync.sh   # cron entrypoint
│   └── generate_key.py    # API key issuance
├── ingest.py               # raw JSON -> SQLite upserts
├── bookmarks.sqlite        # the corpus itself
├── requirements.txt
└── vercel.json
```

## Status

Personal project, single-user by default. Static API key auth is the
supported model; see `docs/auth-notes.md` if you ever need to extend this to
multiple users, which would call for a full OAuth 2.1 flow instead.

## License

MIT — see `LICENSE`.