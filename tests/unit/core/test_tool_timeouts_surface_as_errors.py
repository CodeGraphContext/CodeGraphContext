"""A read timeout is an error from every MCP tool, never ``success: true``.

Every tool in tool_definitions.TOOLS is run through ``MCPServer.handle_tool_call``
against a Neo4j-shaped driver whose every statement times out. A read tool
must answer with the uniform shape (``core.read_timeout.timeout_error``):
``{"error": "Read query timed out: …", "timed_out": true, "timeout_s": …}``.
Handlers wrap exceptions in many ways (``{"success": true, "results":
{"error": …}}`` was one); the server checks the call's timeout log, so no
handler can hide one. A new tool is covered without editing this file: only
tools that never read the graph are exempt, in ``NO_GRAPH_READ`` with the reason.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("neo4j")

from codegraphcontext.core import read_timeout as RT  # noqa: E402
from codegraphcontext.tool_definitions import TOOLS  # noqa: E402
from codegraphcontext.utils.tool_limits import get_tool_query_timeout  # noqa: E402

NO_GRAPH_READ = {
    "add_code_to_graph": "starts an indexing job (writes)",
    "add_package_to_graph": "starts an indexing job (writes)",
    "watch_directory": "starts the watcher (writes)",
    "unwatch_directory": "stops the watcher",
    "list_watched_paths": "watcher state, no graph read",
    "check_job_status": "job manager state",
    "list_jobs": "job manager state",
    "delete_repository": "a write",
    "load_bundle": "bundle import (a write)",
    "search_registry_bundles": "the external bundle registry, not the graph",
    "visualize_graph_query": "builds a URL; runs nothing",
    "list_graphs": "the manager's own FalkorDB graph list",
    "discover_codegraph_contexts": "filesystem scan",
    "switch_context": "reconnects; a connection probe",
    "analyze_architectural_evolution": "reads git history first and returns before any graph read without it",
}

ARGS = {
    "find_code": [{"query": "x"}],
    "find_dead_code": [{}],
    "analyze_code_relationships": [
        {"query_type": qt, "target": t} for qt, t in [
            ("find_callers", "f"), ("find_callees", "f"), ("find_all_callers", "f"), ("find_all_callees", "f"),
            ("call_chain", "a->b"), ("find_importers", "m"), ("class_hierarchy", "K"), ("dead_code", "x"),
            ("module_deps", "m"), ("who_modifies", "v"), ("overrides", "f"), ("variable_scope", "v")]
    ],
    "execute_cypher_query": [{"cypher_query": "MATCH (n) RETURN n"}],
    "calculate_cyclomatic_complexity": [{"function_name": "f"}],
    "find_most_complex_functions": [{}],
    "list_indexed_repositories": [{}],
    "get_repository_stats": [{}, {"repo_path": "/r"}],
    "generate_report": [{}],
    "find_java_spring_endpoints": [{}],
    "find_java_spring_beans": [{}],
    "find_datasource_nodes": [{}],
    "simulate_metrics": [{"repo_path": "/r"}],
    "simulate_architectural_change": [{"repo_path": "/r", "changes": []}],
}


def _timeout_exc():
    from neo4j.exceptions import Neo4jError

    return Neo4jError._hydrate_neo4j(code="Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration",
                                     message="The transaction has not completed within the timeout")


class _Result:
    def _boom(self, *a, **k):
        raise _timeout_exc()

    data = single = consume = values = value = fetch = peek = _boom

    def __iter__(self):
        self._boom()


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, *a, **k):
        return _Result()

    def close(self):
        return None


class _Driver:
    def session(self, **_k):
        return _Session()


@pytest.fixture
def server(monkeypatch, tmp_path):
    from codegraphcontext.server import MCPServer
    from codegraphcontext.tools.code_finder import CodeFinder

    monkeypatch.setattr(RT, "is_neo4j_driver", lambda d: True)
    monkeypatch.setattr("codegraphcontext.utils.path_sandbox.is_path_allowed", lambda p: True)
    monkeypatch.setattr("codegraphcontext.cli.config_manager.get_config_value", lambda key: None)
    mgr = SimpleNamespace(get_driver=lambda *a, **k: _Driver(), get_backend_type=lambda: "neo4j",
                          is_connected=lambda: True)
    srv = MCPServer.__new__(MCPServer)
    srv.db_manager = mgr
    srv.code_finder = CodeFinder(mgr)
    srv.cwd = tmp_path
    srv.disabled_tools = set()
    srv._context_note_pending = False
    return srv


def test_every_tool_is_classified():
    names = set(TOOLS)
    assert set(NO_GRAPH_READ) <= names, set(NO_GRAPH_READ) - names
    unclassified = names - set(NO_GRAPH_READ) - set(ARGS)
    assert not unclassified, f"new tools: give them ARGS (they read the graph) or a NO_GRAPH_READ reason: {unclassified}"


@pytest.mark.parametrize("tool", sorted(ARGS))
def test_read_timeout_is_an_error(server, tool, tmp_path):
    for args in ARGS[tool]:
        if tool == "generate_report":
            args = {**args, "output_path": str(tmp_path / "r.md")}
        out = asyncio.run(server.handle_tool_call(tool, dict(args)))
        assert isinstance(out, dict), (tool, args, out)
        assert out.get("success") is not True, (tool, args, out)
        assert out.get("timed_out") is True and out.get("timeout_s") == get_tool_query_timeout(tool), (tool, args, out)
        assert out["error"].startswith("Read query timed out"), (tool, args, out)
    assert not (tmp_path / "r.md").exists()


def test_analyze_errors_are_never_success(monkeypatch):
    """Generic path: a CodeFinder-reported error is an error, not success with an error inside."""
    from codegraphcontext.tools.handlers.analysis_handlers import analyze_code_relationships

    finder = SimpleNamespace(analyze_code_relationships=lambda *a, **k: {"error": "boom", "query_type": "call_chain"})
    out = analyze_code_relationships(finder, query_type="call_chain", target="a->b")
    assert out.get("success") is not True and out["error"] == "boom"
