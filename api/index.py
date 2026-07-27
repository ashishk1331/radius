"""Vercel entrypoint.

Vercel loads the top-level ``app`` from a supported entrypoint path and runs it
as a single Function. Three things differ from `radius serve`:

* ``stateless_http=True`` — a serverless request may land on any instance, so
  the transport cannot assume a session established by an earlier request.
* ``json_response=True`` — each POST answers with one ordinary JSON response
  rather than a streamed SSE event, which is the simpler contract for a
  request-scoped Function.
* Configuration comes entirely from environment variables — the corpus from
  ``TURSO_DATABASE_URL`` and the JWT verification key from
  ``RADIUS_PUBLIC_KEY_PEM``, since the key files never reach the deployment.

The ASGI lifespan still has to run — FastMCP's session manager raises without
it — which Vercel's Python runtime supports.
"""

from radius.server import create_server

app = create_server().http_app(stateless_http=True, json_response=True)
