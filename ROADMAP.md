# Roadmap

Candidate work, not commitments. Numbering is stable so items can be referred
to by number; nothing here is scheduled.

Shipped today: `fetch_bookmarks` (exact and fuzzy) and `whoami`, behind RS256
tokens carrying a single scope, `bookmarks:read`.

## Where to start

**36 → 32 → 1 → 19 → 26.** The exporter (36) and incremental ingest (32) are
what stand between this and someone else actually adopting it. `recent_bookmarks`
(1) is the cheapest real tool win. OAuth (19) is what unlocks Claude web and
desktop, which cannot use a hand-pasted token. The token dashboard (26) matters
once more than one client exists.

## MCP tools

1. [x] `recent_bookmarks(k)` — last k saved, no query needed
2. [x] `get_bookmark(id | url)` — fetch one exactly, for follow-up after a search [Fetch using resource instead]
3. [x] `bookmarks_by_author(handle, k)`
4. [ ] `bookmarks_in_range(since, until)`
5. [x] `list_authors()` — who you save most, with counts
6. [ ] `stats()` — total count, date span, top authors, last ingest time
7. [ ] `similar_to(bookmark_id, k)` — neighbours of a known bookmark
8. [ ] `semantic_search(query, k)` — embeddings, catches paraphrase where FTS5 cannot
9. [ ] `hybrid_search` — bm25 and vector fused; would become the new default
10. [ ] `random_bookmark(n)` — resurfacing what you forgot you saved
11. [ ] `get_thread(bookmark_id)` — the full thread, not just the saved tweet
12. [ ] `add_bookmark(url)` — needs a `write:bookmarks` scope
13. [ ] `delete_bookmark(id)` / `archive_bookmark(id)`
14. [ ] Filters on search — `has_media`, `has_link`, `author`, `after`, `before`
15. [ ] `fetch_link_content(bookmark_id)` — the article behind the link

## Protocol surface

16. Resources — `bookmark://<id>`, so clients can cite and re-read
17. Prompts — canned "digest my last week", "find prior art for X"
18. Cursor pagination on every list tool
19. OAuth 2.1 and `/.well-known/oauth-protected-resource` — required for the
    Claude web and desktop connectors; today only manual-token clients work

## Auth and tokens

20. Never-expiring tokens
21. Token revocation — a `jti` denylist checked in the verifier
22. `token list` — there is currently no way to see what has been issued
23. Key rotation with a grace window, JWKS serving two keys
24. Per-client rate limiting
25. Audit log — client, tool, query, latency, per call

## Dashboard

26. Token management — issue, name, scope, revoke, last-used
27. Search playground — try queries without an MCP client
28. Library browser — paginated, with filters
29. Stats page
30. Ingest upload — drop the JSON export in the browser
31. Audit log viewer

## Ingestion

32. Incremental ingest — dedupe on id and only write new rows. The slow
    backfill is almost entirely re-writes
33. Batched writes — every statement is a round trip to Turso
34. Scheduled sync — a Vercel cron pulling from the X API
35. Browser extension or bookmarklet — save straight to radius
36. **An exporter.** The docs currently tell you to bring your own JSON. The
    setup prompt in `static/index.html` softens this by having an agent ask
    for the file, but nothing here produces it
37. Auto-tagging or topic clustering at ingest

## CLI

38. `radius search` — query without starting the server
39. `radius doctor` — verify env, keys, database reachability, schema version
40. `radius stats`
41. `radius export --format md|json|csv`
42. `radius backup` / `restore`

## Infrastructure

43. Versioned migrations rather than one idempotent schema file
44. Structured request logging
45. CI — pytest on pull requests
46. A `/health` that actually checks the database
47. Response caching for repeated queries
