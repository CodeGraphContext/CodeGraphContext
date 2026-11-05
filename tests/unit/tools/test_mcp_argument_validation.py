import asyncio
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from jsonschema import Draft202012Validator

from codegraphcontext.server import MCPServer, _apply_response_token_limit
from codegraphcontext.tool_definitions import TOOLS


def server():
    value = MCPServer.__new__(MCPServer)
    value.disabled_tools = set()
    value._context_note_pending = False
    value.find_code_tool = MagicMock(return_value={"success": True, "results": []})
    return value


@pytest.mark.parametrize("tool,args", [
    ("find_code", {}), ("find_code", {"query": None}),
    ("find_code", {"query": 12}), ("find_code", []),
    ("calculate_cyclomatic_complexity", {}),
    ("simulate_architectural_change", {}),
    ("simulate_architectural_change", {"changes": [{"type": "nonsense"}]}),
    ("simulate_architectural_change", {"changes": [{"type": "add_dependency"}]}),
    ("simulate_architectural_change", {"changes": [{"type": "remove_node"}]}),
    ("simulate_architectural_change", {"changes": [{"type": "decompose"}]}),
])
def test_invalid_inputs_are_rejected_before_handler(tool, args):
    value = server()
    result = asyncio.run(value.handle_tool_call(tool, args))
    assert result["error_type"] == "invalid_arguments"
    value.find_code_tool.assert_not_called()


def test_valid_input_and_compatible_extra_fields_still_dispatch():
    value = server()
    assert asyncio.run(value.handle_tool_call("find_code", {"query": "hello", "client_hint": "test"}))["success"]
    value.find_code_tool.assert_called_once()


def test_registered_schemas_are_valid():
    for definition in TOOLS.values():
        Draft202012Validator.check_schema(definition["inputSchema"])


def test_nested_relationship_error_is_not_success():
    value = server()
    value.analyze_code_relationships_tool = MagicMock(return_value={"success": True, "results": {"error": "query failed"}})
    result = asyncio.run(value.handle_tool_call("analyze_code_relationships", {"query_type": "find_callers", "target": "x"}))
    assert result["success"] is False
    assert result["error"] == "query failed"


def test_stdio_invalid_shapes_and_tool_errors(monkeypatch, capsys):
    value = server()
    requests = ['{', '[]', 'null', '"text"', '{"jsonrpc":"2.0","id":4}',
        json.dumps({"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"find_code","arguments":{"query":1}}}),
        json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}),
        json.dumps({"jsonrpc":"2.0","id":6,"method":"unknown"})]
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(requests)+"\n"))
    async def run():
        await value._run_loop(asyncio.get_running_loop())
    asyncio.run(run())
    responses = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r.get("error", {}).get("code") for r in responses[:5]] == [-32700, -32600, -32600, -32600, -32600]
    assert responses[4]["id"] == 4
    assert responses[5]["result"]["isError"] is True
    assert responses[6]["id"] == 6 and responses[6]["error"]["code"] == -32601


def test_http_uses_same_error_result(monkeypatch):
    from codegraphcontext.api import mcp_sse
    monkeypatch.setattr(mcp_sse, "get_server", AsyncMock(return_value=server()))
    result = asyncio.run(mcp_sse.handle_call_tool(None, SimpleNamespace(name="find_code", arguments={"query":1})))
    assert result.is_error is True
    assert json.loads(result.content[0].text)["error_type"] == "invalid_arguments"


@pytest.mark.parametrize("budget", [1, 2, 4, 17, 18, 50, 200, 512])
def test_serialized_limit_includes_escaping_and_wrapper(monkeypatch, budget):
    monkeypatch.setattr("codegraphcontext.cli.config_manager.get_config_value", lambda key: str(budget) if key == "MAX_PROMPT_CHARS" else "0")
    result = _apply_response_token_limit("find_code", json.dumps({"source": '\\"\n漢字' * 1000}))
    assert len(result) <= budget
    json.loads(result)
