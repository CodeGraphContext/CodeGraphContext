"""Schema-level sanity for the graph_name MCP parameter.

Tools that execute queries or writes against a graph MUST advertise a
``graph_name`` property so clients can target a specific graph.  Tools that
only touch in-memory state, the filesystem, or external HTTP endpoints MUST
NOT (keeps the schema honest and avoids client-side confusion).
"""

from codegraphcontext.tool_definitions import TOOLS

# Tools that hit the backend graph (read or write) and therefore must expose graph_name.
_QUERY_EXECUTING = {
    "add_code_to_graph",
    "find_code",
    "analyze_code_relationships",
    "watch_directory",
    "execute_cypher_query",
    "add_package_to_graph",
    "find_dead_code",
    "calculate_cyclomatic_complexity",
    "find_most_complex_functions",
    "list_indexed_repositories",
    "delete_repository",
    "load_bundle",
    "get_repository_stats",
}

# Tools that do NOT hit the graph and therefore MUST NOT advertise graph_name.
_NON_GRAPH = {
    "check_job_status",
    "list_jobs",
    "list_watched_paths",
    "unwatch_directory",
    "discover_codegraph_contexts",
    "switch_context",
    "visualize_graph_query",     # just encodes a URL — no graph access here
    "search_registry_bundles",   # HTTP to external registry
    "list_graphs",                # enumerates graphs — doesn't target one
}


def test_every_declared_tool_is_categorized():
    """Fail fast if a new tool is added to TOOLS without deciding which bucket it belongs to."""
    declared = set(TOOLS.keys())
    categorized = _QUERY_EXECUTING | _NON_GRAPH
    missing = declared - categorized
    assert not missing, (
        f"These tools are not categorized for graph_name coverage: {missing}. "
        "Add them to _QUERY_EXECUTING or _NON_GRAPH in this test."
    )


def test_query_executing_tools_declare_graph_name():
    for name in _QUERY_EXECUTING:
        schema = TOOLS[name]["inputSchema"]
        props = schema.get("properties", {})
        assert "graph_name" in props, f"Tool '{name}' must expose a graph_name property"
        prop = props["graph_name"]
        assert prop.get("type") == "string", f"Tool '{name}': graph_name must be string"
        assert "graph_name" not in schema.get("required", []), (
            f"Tool '{name}': graph_name must be optional"
        )


def test_non_graph_tools_do_not_declare_graph_name():
    for name in _NON_GRAPH:
        schema = TOOLS[name]["inputSchema"]
        props = schema.get("properties", {})
        assert "graph_name" not in props, (
            f"Tool '{name}' should NOT carry graph_name — it doesn't hit the graph"
        )
