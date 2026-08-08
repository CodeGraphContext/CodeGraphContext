import asyncio
import importlib
import sys
import types

from codegraphcontext.api.schemas import QueryRequest

import pytest
from fastapi import HTTPException


class FakeServer:
    def __init__(self):
        self.tool_name = None
        self.arguments = None

    async def handle_tool_call(self, tool_name, arguments):
        self.tool_name = tool_name
        self.arguments = arguments
        return {"rows": [{"count": 1}]}


def test_execute_query_passes_cypher_query_argument(monkeypatch):
    server_module = types.ModuleType("codegraphcontext.server")
    server_module.MCPServer = object
    monkeypatch.setitem(sys.modules, "codegraphcontext.server", server_module)

    router_module = importlib.import_module("codegraphcontext.api.router")

    server = FakeServer()
    request = QueryRequest(
        query="MATCH (n) RETURN count(n) AS count",
        params={"limit": 10},
    )

    response = asyncio.run(router_module.execute_query(request, server=server))

    assert response.status == "ok"
    assert response.data == {"rows": [{"count": 1}]}
    assert server.tool_name == "execute_cypher_query"
    assert server.arguments == {
        "cypher_query": "MATCH (n) RETURN count(n) AS count",
        "params": {"limit": 10},
    }

class FailingServer:
    async def handle_tool_call(self, tool_name, arguments):
        raise OSError("connection refused")


def test_execute_query_returns_503_when_database_unavailable(
    monkeypatch,
):
    server_module = types.ModuleType(
        "codegraphcontext.server"
    )
    server_module.MCPServer = object

    monkeypatch.setitem(
        sys.modules,
        "codegraphcontext.server",
        server_module,
    )

    router_module = importlib.import_module(
        "codegraphcontext.api.router"
    )

    request = QueryRequest(
        query="MATCH (n) RETURN count(n) AS count",
        params={},
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            router_module.execute_query(
                request,
                server=FailingServer(),
            )
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Database service unavailable"