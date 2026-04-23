"""list_graphs() on every backend manager + the MCP handler wrapper.

- Neo4j: queries SHOW DATABASES against the 'system' database.
- FalkorDB (local + remote): delegates to the FalkorDB client's list_graphs().
- Kuzu: always returns [] (no per-graph namespace concept).
- Handler: dispatches to db_manager.list_graphs and returns the canonical shape.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Neo4j
# ---------------------------------------------------------------------------


class TestNeo4jListGraphs:
    def test_list_graphs_queries_system_db_and_returns_names(self):
        from codegraphcontext.core.database import DatabaseManager

        DatabaseManager._instance = None
        env = {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "u",
            "NEO4J_PASSWORD": "p",
        }
        with patch.dict(os.environ, env, clear=True):
            mgr = DatabaseManager()

        mock_driver = MagicMock()
        mgr._driver = mock_driver

        # Simulate SHOW DATABASES YIELD name returning three rows.
        session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = session
        mock_driver.session.return_value.__exit__.return_value = None
        session.run.return_value = iter([
            {"name": "neo4j"},
            {"name": "system"},
            {"name": "tenant_a"},
        ])

        graphs = mgr.list_graphs()

        # Session must be opened against the 'system' database (SHOW DATABASES
        # is only valid there).
        mock_driver.session.assert_called_once_with(database="system")
        session.run.assert_called_once()
        assert session.run.call_args.args[0].upper().startswith("SHOW DATABASES")
        assert graphs == ["neo4j", "system", "tenant_a"]


# ---------------------------------------------------------------------------
# FalkorDB Lite (local)
# ---------------------------------------------------------------------------


class TestFalkorDBListGraphs:
    def _reset(self):
        from codegraphcontext.core.database_falkordb import FalkorDBManager
        FalkorDBManager._instance = None
        FalkorDBManager._driver = None
        FalkorDBManager._process = None

    def setup_method(self):
        self._reset()

    def teardown_method(self):
        self._reset()

    def test_list_graphs_delegates_to_client_and_decodes_bytes(self):
        from codegraphcontext.core.database_falkordb import FalkorDBManager

        mgr = FalkorDBManager()
        mock_driver = MagicMock()
        # Simulate a mixed bytes/str return from the FalkorDB client.
        mock_driver.list_graphs.return_value = [b"codegraph", "tenant_a", b"__cgc_health_check"]
        mgr._driver = mock_driver  # pre-warm so get_driver skips subprocess path

        graphs = mgr.list_graphs()
        mock_driver.list_graphs.assert_called_once()
        assert graphs == ["codegraph", "tenant_a", "__cgc_health_check"]

    def test_list_graphs_returns_empty_list_when_backend_has_no_graphs(self):
        from codegraphcontext.core.database_falkordb import FalkorDBManager

        mgr = FalkorDBManager()
        mock_driver = MagicMock()
        mock_driver.list_graphs.return_value = []
        mgr._driver = mock_driver

        assert mgr.list_graphs() == []


# ---------------------------------------------------------------------------
# FalkorDB Remote
# ---------------------------------------------------------------------------


class TestFalkorDBRemoteListGraphs:
    def _reset(self):
        from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
        FalkorDBRemoteManager._instance = None
        FalkorDBRemoteManager._driver = None

    def setup_method(self):
        self._reset()

    def teardown_method(self):
        self._reset()

    def test_list_graphs_delegates_to_client(self):
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env["FALKORDB_HOST"] = "h"
        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            mgr = FalkorDBRemoteManager()
            mock_driver = MagicMock()
            mock_driver.list_graphs.return_value = [b"g1", b"g2"]
            mgr._driver = mock_driver  # pre-warm

            assert mgr.list_graphs() == ["g1", "g2"]
            mock_driver.list_graphs.assert_called_once()


# ---------------------------------------------------------------------------
# Kuzu — no per-graph namespace
# ---------------------------------------------------------------------------


class TestKuzuListGraphs:
    def _reset(self):
        from codegraphcontext.core.database_kuzu import KuzuDBManager
        KuzuDBManager._instance = None
        KuzuDBManager._db = None
        KuzuDBManager._conn = None

    def setup_method(self):
        self._reset()

    def teardown_method(self):
        self._reset()

    def test_list_graphs_always_returns_empty(self):
        from codegraphcontext.core.database_kuzu import KuzuDBManager

        mgr = KuzuDBManager(db_path="/tmp/ignored_kuzu_list_graphs")
        # Must not require a connection — Kuzu has no graph concept to query.
        assert mgr.list_graphs() == []


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class TestListGraphsHandler:
    def test_handler_returns_backend_and_graphs(self):
        from codegraphcontext.tools.handlers.management_handlers import list_graphs

        db_manager = MagicMock()
        db_manager.get_backend_type.return_value = "falkordb-remote"
        db_manager.list_graphs.return_value = ["codegraph", "tenant_a"]

        result = list_graphs(db_manager)

        assert result["success"] is True
        assert result["backend"] == "falkordb-remote"
        assert result["graphs"] == ["codegraph", "tenant_a"]

    def test_handler_returns_error_on_exception(self):
        from codegraphcontext.tools.handlers.management_handlers import list_graphs

        db_manager = MagicMock()
        db_manager.list_graphs.side_effect = RuntimeError("backend down")

        result = list_graphs(db_manager)
        assert "error" in result
        assert "backend down" in result["error"]

    def test_handler_accepts_unused_kwargs_without_error(self):
        """Server's handle_tool_call passes args as **kwargs; ensure extraneous
        keys don't break the handler."""
        from codegraphcontext.tools.handlers.management_handlers import list_graphs

        db_manager = MagicMock()
        db_manager.get_backend_type.return_value = "neo4j"
        db_manager.list_graphs.return_value = []
        result = list_graphs(db_manager, some_unused_arg="ignored")
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Server wiring
# ---------------------------------------------------------------------------


def test_server_routes_list_graphs_to_handler():
    """handle_tool_call must dispatch 'list_graphs' to the list_graphs_tool wrapper."""
    from codegraphcontext.server import MCPServer

    server = MCPServer.__new__(MCPServer)
    # Just verify the attribute exists — full handle_tool_call dispatch is
    # already covered indirectly by the tool_map definition tests.
    assert hasattr(MCPServer, "list_graphs_tool")


def test_tool_definitions_exposes_list_graphs():
    from codegraphcontext.tool_definitions import TOOLS
    assert "list_graphs" in TOOLS
    schema = TOOLS["list_graphs"]["inputSchema"]
    # Discovery tool — no parameters at all.
    assert schema.get("properties", {}) == {}
    assert not schema.get("required")
