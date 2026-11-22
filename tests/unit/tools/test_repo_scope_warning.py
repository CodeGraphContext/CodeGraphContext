import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools.handlers import analysis_handlers as AH
from codegraphcontext.server import MCPServer


@pytest.fixture
def mock_finder():
    mock_db = SimpleNamespace(
        get_backend_type=lambda: "neo4j",
        get_driver=lambda *a: MagicMock(),
    )
    finder = CodeFinder(mock_db)
    indexed = [
        {"name": "shop", "path": "/work/shop"},
        {"name": "blog", "path": "/work/blog"},
        {"name": "shop-v2", "path": "/other/shop-v2"},
    ]
    finder.list_indexed_repositories = MagicMock(return_value=indexed)
    return finder


def test_resolve_repo_scope_valid_matches(mock_finder):
    # Exact name match
    res, warn = mock_finder._resolve_repo_scope("shop")
    assert res == "/work/shop"
    assert warn is None

    # Exact absolute path match
    res, warn = mock_finder._resolve_repo_scope("/work/shop")
    assert res == "/work/shop"
    assert warn is None

    # Subdirectory of indexed repo root
    res, warn = mock_finder._resolve_repo_scope("/work/shop/src/components")
    assert res == "/work/shop/src/components"
    assert warn is None

    # Parent directory filter across indexed repositories
    res, warn = mock_finder._resolve_repo_scope("/work")
    assert res == "/work"
    assert warn is None


def test_resolve_repo_scope_unknown_repository(mock_finder):
    res, warn = mock_finder._resolve_repo_scope("shopp")
    assert res == "shopp"
    assert warn is not None
    assert "repo_path 'shopp' did not match any indexed repository" in warn
    assert "shop" in warn

    # Unknown absolute path
    res, warn = mock_finder._resolve_repo_scope("/nowhere/shop")
    assert res == "/nowhere/shop"
    assert warn is not None
    assert "repo_path '/nowhere/shop' did not match any indexed repository" in warn


def test_resolve_repo_scope_ambiguous_matches(mock_finder):
    # Two repos ending in /repo
    mock_finder.list_indexed_repositories = MagicMock(return_value=[
        {"name": "app1", "path": "/a/repo"},
        {"name": "app2", "path": "/b/repo"},
    ])
    res, warn = mock_finder._resolve_repo_scope("repo")
    assert res == "repo"
    assert warn is not None
    assert "ambiguous" in warn
    assert "app1" in warn and "app2" in warn


def test_resolve_repo_scope_scoped_to_graph():
    mock_db = SimpleNamespace(
        get_backend_type=lambda: "neo4j",
        get_driver=lambda *a: MagicMock(),
    )
    finder = CodeFinder(mock_db)
    
    def mock_list(graph_name=None):
        if graph_name == "graph_custom":
            return [{"name": "custom_repo", "path": "/custom/path"}]
        return [{"name": "default_repo", "path": "/default/path"}]

    finder.list_indexed_repositories = MagicMock(side_effect=mock_list)

    # In default graph, custom_repo is unknown
    _, warn = finder._resolve_repo_scope("custom_repo")
    assert warn is not None
    assert "default_repo" in warn

    # In graph_custom, custom_repo is known
    res, warn = finder._resolve_repo_scope("custom_repo", graph_name="graph_custom")
    assert res == "/custom/path"
    assert warn is None


def test_analysis_handlers_include_repo_path_warning(mock_finder):
    mock_finder.find_related_code = MagicMock(return_value={
        "query": "compute_total",
        "functions_by_name": [],
        "classes_by_name": [],
        "variables_by_name": [],
        "content_matches": [],
        "ranked_results": [],
        "total_matches": 0,
    })

    # Unknown repo_path
    resp = AH.find_code(mock_finder, query="compute_total", repo_path="shopp")
    assert resp["success"] is True
    assert "repo_path_warning" in resp
    assert "repo_path 'shopp' did not match any indexed repository" in resp["repo_path_warning"]

    # Valid repo_path has no warning
    resp = AH.find_code(mock_finder, query="compute_total", repo_path="shop")
    assert resp["success"] is True
    assert "repo_path_warning" not in resp


def test_mcp_server_serialized_envelope_contains_repo_path_warning():
    async def _run():
        with patch("codegraphcontext.server.get_database_manager") as mock_db, \
             patch("codegraphcontext.server.JobManager"), \
             patch("codegraphcontext.server.GraphBuilder"), \
             patch("codegraphcontext.server.CodeWatcher"):
            
            server = MCPServer()
            indexed = [{"name": "shop", "path": "/work/shop"}]
            server.code_finder.list_indexed_repositories = MagicMock(return_value=indexed)
            server.code_finder.find_related_code = MagicMock(return_value={
                "query": "compute_total",
                "ranked_results": [],
                "total_matches": 0,
            })

            # Test handle_tool_call
            res = await server.handle_tool_call("find_code", {"query": "compute_total", "repo_path": "shopp"})
            assert res["success"] is True
            assert "repo_path_warning" in res
            assert "repo_path 'shopp' did not match any indexed repository" in res["repo_path_warning"]

            # Valid scope has no warning
            res_valid = await server.handle_tool_call("find_code", {"query": "compute_total", "repo_path": "shop"})
            assert res_valid["success"] is True
            assert "repo_path_warning" not in res_valid

    import asyncio
    asyncio.run(_run())
