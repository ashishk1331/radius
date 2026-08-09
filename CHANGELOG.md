# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions are [SemVer](https://semver.org/spec/v2.0.0.html), tagged
`vX.Y.Z`.

The public surface is the MCP tool signatures, the scope names and the token
claims. While the major version is `0` those may change in a minor release;
from `1.0.0` on, breaking any of them requires a major bump.

## [Unreleased]

### Added

- A `bookmark://<id>` resource, so a client can cite a bookmark and re-read it
  by URI rather than searching for it again. Guarded by `bookmarks:read`, the
  same scope as the tools.
- `recent_bookmarks(n)` — bookmarks without a search query, for browsing the
  corpus rather than looking something up in it.
- `bookmarks_by_author(handle, k)` — everything saved from one account. The
  handle is matched exactly; one that matches nothing returns an empty list
  rather than widening to the rest of the corpus.
- `list_authors(n)` — who is in the corpus and how many bookmarks are saved
  from each, ranked by count descending. `n` defaults to `-1`, meaning all.
- `TweetResult` and `AuthorResult`, the shapes the three tools above return.
  Neither carries `score`: it belongs to a search, and none of them search.
- `RADIUS_DB_PATH=:memory:` keeps the local fallback in RAM. libSQL gives each
  connection its own in-memory database, so this one is opened once and reused
  for the life of the process rather than reopened per call.

### Changed

- `server.py` is now a `server/` package — `tools.py`, `resources.py`,
  `web.py`, and `app.py` for assembly. `from radius.server import ...` is
  unchanged.
- `fetch_bookmarks` clamps `top_k` to 5–50 rather than 1–50. A request for
  fewer than five results is widened rather than honoured.
- The documentation site is four pages — `/`, `/start`, `/tools`, `/operate` —
  rather than one long scroll, with the head, topbar, nav and footer shared as
  fragments under `static/parts/`. In-page anchors still work within a page;
  links to an anchor that has moved to another page do not.
- Turso credentials belong in `.env.production` rather than `.env.local`, so
  reaching the hosted database is something `RADIUS_ENV=production` opts you
  into. The tests and an unconfigured run both fall back to `:memory:`.

### Fixed

- `upsert_author` left `avatar` out of its `ON CONFLICT` clause, so a changed
  profile image was silently discarded on every re-ingest after the first.

## [0.1.0] - 2026-07-30

### Added

- MCP server over streamable HTTP exposing `fetch_bookmarks` and `whoami`,
  with per-tool scope requirements so a token only opens what it was minted
  for.
- RS256 token issuer. `radius keys init` generates the key pair and publishes
  a JWKS at `/.well-known/jwks.json`; `radius token issue` and
  `radius token inspect` mint and verify.
- Turso as the corpus — the same hosted database locally and in production,
  with a plain local libSQL file as the offline and test fallback.
- Two search modes: SQLite FTS5 with bm25 ranking, and rapidfuzz
  `partial_ratio` for near misses.
- `radius ingest` for upserting a raw bookmark JSON export, batched to limit
  round trips to Turso.
- Vercel deployment as a single Python function, with the entrypoint declared
  in `pyproject.toml`.
- Documentation homepage served at `/`, covering setup, tools, auth,
  deployment and troubleshooting.
- Favicon set, and light and dark logo variants declared to MCP clients at
  48/96/256.
- Self-hosted Figtree, served from `/fonts` with an immutable cache.
- `AGENTS.md`, and a copy-paste setup prompt on the homepage for handing
  installation to an agent.

### Changed

- `radius serve` reloads on file changes by default; pass `--no-reload` for a
  long-lived deployment.
- Homepage restyled to black and white with an `#FF2818` accent, defaulting to
  light with the dark theme retained behind `[data-theme="dark"]`.

### Fixed

- FTS5 results were ordered worst-match-first; bm25 is now negated into a
  `score` so higher is better.
- `Tweet.from_dict` read `author_id` from the wrong key.
- Database connections were never closed. They now commit, roll back and close
  through a context manager.
- Token inspection reported claim rejections as a raw traceback instead of an
  error message.
- Importing `radius.server` failed on a machine that had not yet run
  `keys init`; the server is now built lazily.
- Scrollbar arrows were never actually hidden. Setting `scrollbar-width` and
  `scrollbar-color` opts Chromium into its standard scrollbar, which discards
  every `::-webkit-scrollbar` rule; the standard properties now sit in a
  Firefox-only `@supports` block.
- The header wordmark inherited a small size and a heavy weight and then had
  negative tracking applied, closing up the letterforms.

[Unreleased]: https://github.com/ashishk1331/radius/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ashishk1331/radius/releases/tag/v0.1.0
