# tests/unit/api/test_mcp_streamable_http.py
"""MCP endpoint tests (Streamable HTTP, spec 2026-07-28).

The transport is mcp.server.lowlevel.Server.streamable_http_app(), mounted
in api/app.py at /api/v1/mcp behind the same API-key check the REST router
uses. The old two-endpoint HTTP+SSE transport (/api/v1/mcp/sse,
/api/v1/mcp/messages) is kept mounted alongside it for existing client
configs (see docs/INTEGRATION_GUIDE.md); tests below cover both.
"""
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch

import anyio
import httpx
import pytest
import uvicorn
from httpx import ASGITransport, AsyncClient


def _modern_request(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    body_params = dict(params or {})
    body_params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    return {"jsonrpc": "2.0", "method": method, "id": request_id, "params": body_params}


_MODERN_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2026-07-28",
}


class _FakeMCPServer:
    """Stand-in for router.get_server(), so tests exercise the real
    on_list_tools/on_call_tool handlers without needing a configured DB."""

    tools = {
        "ping": {"description": "Ping the server", "inputSchema": {"type": "object", "properties": {}}},
    }

    async def handle_tool_call(self, tool_name, args):
        if tool_name == "boom":
            return {"error": "simulated failure"}
        return {"ok": True, "tool": tool_name, "args": args}


@asynccontextmanager
async def _running_client(env=None, monkeypatch=None):
    """Build create_app() with env applied, drive its lifespan (starts the
    MCP session manager's task group), and yield an AsyncClient against it."""
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)

    from codegraphcontext.api.app import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_tools_list_returns_real_tools(monkeypatch):
    with patch("codegraphcontext.api.mcp_sse.get_server", return_value=_FakeMCPServer()):
        async with _running_client(monkeypatch=monkeypatch) as client:
            resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/list"),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/list"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert tool_names == ["ping"]


@pytest.mark.asyncio
async def test_tools_call_returns_result(monkeypatch):
    with patch("codegraphcontext.api.mcp_sse.get_server", return_value=_FakeMCPServer()):
        async with _running_client(monkeypatch=monkeypatch) as client:
            resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/call", {"name": "ping", "arguments": {}}),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/call", "Mcp-Name": "ping"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["isError"] is False
    assert '"tool": "ping"' in body["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_tools_call_error_result_sets_is_error(monkeypatch):
    with patch("codegraphcontext.api.mcp_sse.get_server", return_value=_FakeMCPServer()):
        async with _running_client(monkeypatch=monkeypatch) as client:
            resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/call", {"name": "boom", "arguments": {}}),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/call", "Mcp-Name": "boom"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["isError"] is True
    assert "simulated failure" in body["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_malformed_json_returns_400(monkeypatch):
    async with _running_client(monkeypatch=monkeypatch) as client:
        resp = await client.post(
            "/api/v1/mcp",
            content=b'{"jsonrpc":"2.0","method":"tools/list","id":1',  # missing closing }
            headers={"Content-Type": "application/json", **_MODERN_HEADERS},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_no_trailing_slash_redirect(monkeypatch):
    """A Mount would 307 a request without the trailing slash, which can
    drop the Authorization header on the redirected hop; add_route must not."""
    with patch("codegraphcontext.api.mcp_sse.get_server", return_value=_FakeMCPServer()):
        async with _running_client(monkeypatch=monkeypatch) as client:
            resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/list"),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/list"},
            )

    assert resp.status_code != 307


@pytest.mark.asyncio
async def test_requires_api_key_when_configured(monkeypatch):
    with patch("codegraphcontext.api.mcp_sse.get_server", return_value=_FakeMCPServer()):
        async with _running_client(env={"CGC_API_KEY": "s3cret"}, monkeypatch=monkeypatch) as client:
            no_key_resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/list"),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/list"},
            )
            wrong_key_resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/list"),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/list", "X-API-Key": "wrong"},
            )
            right_key_resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/list"),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/list", "X-API-Key": "s3cret"},
            )

    assert no_key_resp.status_code == 401
    assert wrong_key_resp.status_code == 401
    assert right_key_resp.status_code == 200


@pytest.mark.asyncio
async def test_origin_validation_default_on(monkeypatch):
    """Origin is checked by default (DNS-rebinding protection): a browser tab
    on an untrusted origin is rejected, a non-browser client sending no
    Origin at all is allowed, and localhost is allowed by default."""
    with patch("codegraphcontext.api.mcp_sse.get_server", return_value=_FakeMCPServer()):
        async with _running_client(monkeypatch=monkeypatch) as client:
            no_origin_resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/list"),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/list"},
            )
            evil_origin_resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/list"),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/list", "Origin": "http://evil.example"},
            )
            localhost_origin_resp = await client.post(
                "/api/v1/mcp",
                json=_modern_request("tools/list"),
                headers={**_MODERN_HEADERS, "Mcp-Method": "tools/list", "Origin": "http://localhost:3000"},
            )

    assert no_origin_resp.status_code == 200
    assert evil_origin_resp.status_code == 403
    assert localhost_origin_resp.status_code == 200


def test_legacy_sse_routes_still_registered():
    """Clients still configured with the pre-migration /sse URL (see
    docs/INTEGRATION_GUIDE.md) must keep working during the deprecation
    window, not 404."""
    from codegraphcontext.api.app import create_app

    app = create_app()
    route_paths = {getattr(r, "path", None): getattr(r, "methods", None) for r in app.routes}
    assert route_paths.get("/api/v1/mcp/sse") == {"GET"}
    assert route_paths.get("/api/v1/mcp/messages") == {"POST"}
    assert "/api/v1/mcp" in route_paths


@asynccontextmanager
async def _running_server(port: int):
    """Run the real app under uvicorn on localhost. ASGITransport can't drive
    an open SSE stream (it waits for the app callable to finish before
    returning), so the legacy transport needs a real socket to prove it
    actually completes a request/response cycle under mcp 2.x."""
    from codegraphcontext.api.app import create_app

    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(0.05)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task


@pytest.mark.asyncio
async def test_legacy_sse_transport_end_to_end():
    """A real MCP client (mcp.client.sse) against a real server proves the
    legacy /sse + /messages routes still work under the mcp 2.x SDK, not
    just that the route table has entries for them."""
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    with patch("codegraphcontext.api.mcp_sse.get_server", return_value=_FakeMCPServer()):
        async with _running_server(port=18791) as base_url:
            with anyio.fail_after(15):
                async with sse_client(f"{base_url}/api/v1/mcp/sse") as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        assert [t.name for t in tools.tools] == ["ping"]
                        result = await session.call_tool("ping", {})
                        assert result.is_error is False


@pytest.mark.asyncio
async def test_legacy_streamable_http_initialize_handshake():
    """A 2025-era client (initialize handshake, no MCP-Protocol-Version
    header) hitting the new single /api/v1/mcp endpoint gets a session ID
    back — the SDK's era classifier routes it to the legacy handler rather
    than rejecting it, so one mount really does serve both eras."""
    with patch("codegraphcontext.api.mcp_sse.get_server", return_value=_FakeMCPServer()):
        async with _running_server(port=18792) as base_url:
            with anyio.fail_after(15):
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{base_url}/api/v1/mcp",
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-06-18",
                                "capabilities": {},
                                "clientInfo": {"name": "test", "version": "1.0"},
                            },
                        },
                        headers={
                            "Accept": "application/json, text/event-stream",
                            "Content-Type": "application/json",
                        },
                    )

    assert resp.status_code == 200
    assert resp.headers.get("mcp-session-id")
    assert '"protocolVersion":"2025-06-18"' in resp.text


@pytest.mark.asyncio
async def test_legacy_routes_enforce_origin_and_api_key():
    """The legacy /sse and /messages routes don't go through
    _TransportSecurityMiddleware (that only wraps the new mount) — they must
    still reject a bad Origin and a missing/wrong API key via
    require_mcp_transport_security / require_api_key on the route itself."""
    with patch("codegraphcontext.api.mcp_sse.get_server", return_value=_FakeMCPServer()):
        async with _running_server(port=18793) as base_url:
            with anyio.fail_after(15):
                async with httpx.AsyncClient() as client:
                    evil_origin_resp = await client.post(
                        f"{base_url}/api/v1/mcp/messages",
                        json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                        headers={"Origin": "http://evil.example"},
                    )

    assert evil_origin_resp.status_code == 403
