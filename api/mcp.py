"""Vercel entrypoint.

Vercel loads the top-level ``app`` from this file and runs it as a single
Function. Four things differ from `radius serve`:

* **Path.** The app is mounted at ``/api/mcp`` rather than ``/mcp``. Vercel has
  two Python routing behaviours — a file under ``api/`` becomes a Function at
  its own path, and a detected framework entrypoint receives every path — and
  mounting here is correct under both. It also matches the URL shape Vercel's
  own MCP documentation uses.
* ``stateless_http=True`` — a request may land on any instance, so the
  transport cannot assume a session an earlier request established.
* ``json_response=True`` — each POST answers with one ordinary JSON response
  rather than a streamed SSE event, the simpler contract for a Function.
* Configuration comes entirely from environment variables — the corpus from
  ``TURSO_DATABASE_URL`` and the JWT verification key from
  ``RADIUS_PUBLIC_KEY_PEM``, since the key files never reach the deployment.

The ASGI lifespan still has to run — FastMCP's session manager raises without
it — which Vercel's Python runtime supports.
"""

from radius.server import create_server

MCP_PATH = "/api/mcp"

app = create_server().http_app(
    path=MCP_PATH,
    stateless_http=True,
    json_response=True,
)
