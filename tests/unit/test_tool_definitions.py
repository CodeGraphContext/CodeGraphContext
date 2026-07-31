"""MCP tool schemas must expose every handler-supported public input."""

from codegraphcontext.tool_definitions import TOOLS


def test_schemas_expose_existing_handler_inputs():
    analyze_properties = TOOLS["analyze_code_relationships"]["inputSchema"]["properties"]
    cypher_properties = TOOLS["execute_cypher_query"]["inputSchema"]["properties"]
    complexity_properties = TOOLS["calculate_cyclomatic_complexity"]["inputSchema"]["properties"]

    assert analyze_properties["depth"]["type"] == "integer"
    assert cypher_properties["params"] == {
        "type": "object",
        "description": "Optional named parameters passed to the Cypher query.",
        "default": {},
    }
    assert complexity_properties["path"]["type"] == "string"
