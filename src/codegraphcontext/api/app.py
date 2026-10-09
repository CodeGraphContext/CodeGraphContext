# src/codegraphcontext/api/app.py
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from .router import router
import logging

from .auth import (
    get_configured_api_key,
    get_mcp_transport_security_config,
    log_auth_status,
    require_api_key,
    require_mcp_transport_security,
    _extract_provided_key,
    _host_matches,
    _keys_match,
    _origin_matches,
)
from .mcp_sse import handle_messages, handle_sse, mcp_server
from mcp.server.transport_security import TransportSecuritySettings

logger = logging.getLogger(__name__)


class _TransportSecurityMiddleware:
    """DNS-rebinding protection: Origin validated by default, Host opt-in.

    A browser tab on an attacker's page can still send same-origin-looking
    requests to a server bound to localhost/0.0.0.0 (DNS rebinding); checking
    Origin blocks that without breaking CLI/desktop MCP clients, which don't
    send an Origin header at all. Host is left opt-in (CGC_MCP_ALLOWED_HOSTS)
    because this gateway commonly sits behind a proxy or a non-loopback
    hostname with no single safe default.
    """

    def __init__(self, app, allowed_hosts: list[str], allowed_origins: list[str]):
        self.app = app
        self.allowed_hosts = allowed_hosts
        self.allowed_origins = allowed_origins

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])

        if self.allowed_hosts:
            host = headers.get(b"host", b"").decode("latin-1") or None
            if not _host_matches(host, self.allowed_hosts):
                logger.warning("Rejected MCP request with Host %r; add it to CGC_MCP_ALLOWED_HOSTS if legitimate.", host)
                response = Response(content="Invalid Host header", status_code=421)
                await response(scope, receive, send)
                return

        origin = headers.get(b"origin", b"").decode("latin-1") or None
        if not _origin_matches(origin, self.allowed_origins):
            logger.warning("Rejected MCP request with Origin %r; add it to CGC_MCP_ALLOWED_ORIGINS if legitimate.", origin)
            response = Response(content="Invalid Origin header", status_code=403)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class _ApiKeyMiddleware:
    """ASGI middleware enforcing the same API-key check as require_api_key().

    The mounted Streamable HTTP app is a plain Starlette app, not a FastAPI
    route, so it can't take a FastAPI ``Depends`` — this reuses the same
    header-extraction/comparison logic at the ASGI layer instead.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        configured = get_configured_api_key()
        if configured:
            headers = dict(scope["headers"])
            authorization = headers.get(b"authorization", b"").decode("latin-1") or None
            x_api_key = headers.get(b"x-api-key", b"").decode("latin-1") or None
            provided = _extract_provided_key(authorization, x_api_key)
            if not provided or not _keys_match(provided, configured):
                response = Response(
                    content='{"error": "Invalid or missing API key"}',
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


def _combine_lifespans(outer_lifespan, mcp_app):
    """Chain the FastAPI app's own lifespan with the mounted MCP sub-app's."""

    @asynccontextmanager
    async def combined(app):
        async with outer_lifespan(app):
            async with mcp_app.router.lifespan_context(mcp_app):
                yield

    return combined


def create_app() -> FastAPI:
    # Log whether API-key auth is active. Emits a prominent security warning
    # when the gateway is running unauthenticated (CGC_API_KEY unset).
    log_auth_status()

    app = FastAPI(
        title="CodeGraphContext Gateway",
        description="HTTP API gateway for CodeGraphContext MCP server. Enables integration with ChatGPT Actions, Claude, and web frontends.",
        version="0.1.0"
    )

    # Enable CORS for the website/frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # In production, restrict this
        # Credentials must stay disabled while origins is a wildcard; the
        # combination is rejected by browsers and would leak cookie-authed
        # responses to any site.
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        """Liveness probe for load balancers and k8s."""
        return {"status": "ok"}

    # MCP endpoint (Streamable HTTP, spec 2026-07-28). Replaces the deprecated
    # two-endpoint HTTP+SSE transport as the primary transport. The SDK's
    # session manager auto-detects legacy Streamable HTTP clients (2025-03-26
    # through 2025-11-25, via the MCP-Protocol-Version header) and the modern
    # per-request era, and routes each to the right internal handler — one
    # mount serves both.
    #
    # This dispatches to the same tools as the REST router
    # (execute_cypher_query, add_code_to_graph, delete_repository), so it
    # needs the same API-key check the router applies — without it, setting
    # CGC_API_KEY would leave the MCP transport as an unauthenticated path to
    # every tool. streamable_http_app() returns a plain Starlette app (no
    # FastAPI dependency injection), so the check is applied as ASGI
    # middleware instead of a FastAPI dependency. DNS-rebinding protection is
    # handled by our own _TransportSecurityMiddleware (Origin default-on,
    # Host opt-in — see get_mcp_transport_security_config), not the SDK's
    # built-in check, which couples both under one flag.
    allowed_hosts, allowed_origins = get_mcp_transport_security_config()
    mcp_app = mcp_server.streamable_http_app(
        streamable_http_path="/api/v1/mcp",
        # Disable the SDK's own Host/Origin check (coupled under one flag) —
        # _TransportSecurityMiddleware below replaces it with independently
        # configurable checks.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    # add_route (not mount): a Mount redirects a request without the trailing
    # slash to "/api/v1/mcp/" with a 307, and a redirect across origins can
    # drop the Authorization header. add_route with a plain ASGI callable
    # registers the exact path with no redirect and no method restriction.
    app.add_route(
        "/api/v1/mcp",
        _TransportSecurityMiddleware(
            _ApiKeyMiddleware(mcp_app),
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        ),
    )

    # streamable_http_app()'s session manager needs its own lifespan entered
    # (it starts the task group backing every request) — a plain app.mount()
    # doesn't propagate that automatically, so it's driven from the parent's.
    app.router.lifespan_context = _combine_lifespans(app.router.lifespan_context, mcp_app)

    # Deprecated HTTP+SSE transport (2024-11-05). Kept alongside the mount
    # above so clients still configured with the old /api/v1/mcp/sse URL
    # (docs/INTEGRATION_GUIDE.md) keep working during the migration to
    # Streamable HTTP. Same API-key and DNS-rebinding checks as the new
    # endpoint — SseServerTransport takes no security_settings of its own, so
    # without these dependencies a browser page could open this stream
    # directly, key or no key.
    app.add_api_route(
        "/api/v1/mcp/sse",
        handle_sse,
        methods=["GET"],
        dependencies=[Depends(require_mcp_transport_security), Depends(require_api_key)],
    )
    app.add_api_route(
        "/api/v1/mcp/messages",
        handle_messages,
        methods=["POST"],
        dependencies=[Depends(require_mcp_transport_security), Depends(require_api_key)],
    )

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return """
        <!DOCTYPE html>
        <html>
            <head>
                <title>CGC Gateway</title>
                <style>
                    body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #0f172a; color: white; margin: 0; }
                    .card { background: #1e293b; padding: 2rem; border-radius: 1rem; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); text-align: center; max-width: 400px; border: 1px solid #334155; }
                    h1 { color: #38bdf8; margin-top: 0; }
                    p { color: #94a3b8; line-height: 1.6; }
                    .btn { display: inline-block; background: #38bdf8; color: #0f172a; padding: 0.75rem 1.5rem; border-radius: 0.5rem; text-decoration: none; font-weight: bold; margin-top: 1rem; transition: background 0.2s; }
                    .btn:hover { background: #7dd3fc; }
                    .links { margin-top: 1.5rem; font-size: 0.9rem; }
                    .links a { color: #38bdf8; text-decoration: none; margin: 0 0.5rem; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>CGC Gateway</h1>
                    <p>CodeGraphContext HTTP API is running. This gateway allows ChatGPT and Claude to interact with your code graph.</p>
                    <a href="/docs" class="btn">View API Docs</a>
                    <div class="links">
                        <a href="/openapi.json">OpenAPI Spec</a>
                        <a href="https://github.com/CodeGraphContext/CodeGraphContext" target="_blank">GitHub</a>
                    </div>
                </div>
            </body>
        </html>
        """

    return app

app = create_app()
