import asyncio

import pytest
from fastapi.testclient import TestClient

from codegraphcontext.api import mcp_sse, router
from codegraphcontext.api.app import create_app


class LoopRecordingServer:
    """Mimics MCPServer's loop fallback and reports which loop serves the call."""

    def __init__(self, loop=None, cwd=None):
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
        self.loop = loop
        self.tools = {"t": {"description": "d", "inputSchema": {"type": "object"}}}

    async def handle_tool_call(self, name, arguments):
        return {"same_loop": asyncio.get_running_loop() is self.loop}


@pytest.fixture
def fake_server(monkeypatch):
    monkeypatch.delenv("CGC_API_KEY", raising=False)
    monkeypatch.setattr(router, "MCPServer", LoopRecordingServer)
    monkeypatch.setattr(router, "_server_instance", None)


def test_server_is_bound_to_the_serving_event_loop(fake_server):
    with TestClient(create_app()) as client:
        body = client.get("/api/v1/repositories").json()
    assert body["data"]["same_loop"] is True


def test_sse_list_tools_still_gets_a_server(fake_server):
    tools = asyncio.run(mcp_sse.handle_list_tools())
    assert [t.name for t in tools] == ["t"]
