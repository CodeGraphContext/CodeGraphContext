# tests/test_mcp_sse.py
import json
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_handle_messages_valid_json():
    """Complete JSON-RPC payload should be accepted without error."""
    from codegraphcontext.api.mcp_sse import handle_messages
    from fastapi import FastAPI

    app = FastAPI()
    app.add_route("/api/v1/mcp/messages", handle_messages, methods=["POST"])

    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    }).encode()

    with patch("codegraphcontext.api.mcp_sse.sse.handle_post_message", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/mcp/messages",
                content=payload,
                headers={"Content-Type": "application/json"}
            )
        assert response.status_code != 400


@pytest.mark.asyncio
async def test_handle_messages_incomplete_json_returns_400():
    """Truncated/incomplete JSON should return 400 with a parse error."""
    from codegraphcontext.api.mcp_sse import handle_messages
    from fastapi import FastAPI

    app = FastAPI()
    app.add_route("/api/v1/mcp/messages", handle_messages, methods=["POST"])

    # Simulates a large JSON split mid-stream
    incomplete_payload = b'{"jsonrpc":"2.0","method":"tools/list","id":1'  # missing closing }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/mcp/messages",
            content=incomplete_payload,
            headers={"Content-Type": "application/json"}
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == -32700
    assert "Parse error" in body["error"]["message"]

