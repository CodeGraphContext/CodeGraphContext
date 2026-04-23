"""Per-call graph_name plumbing through database managers.

These tests verify that:
- Neo4j: graph_name passed to get_driver becomes database= on the session.
- FalkorDB (local + remote): graph_name passed to get_driver drives
  select_graph so the returned wrapper targets that graph.
- Kuzu: graph_name is accepted and silently ignored.
- Two concurrent get_driver calls with different names produce independent
  wrappers (no shared mutable state).

See feedback_switch_context memory: graph_name is NOT related to cgc
switch_context — this is strictly within-backend namespace selection.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Neo4j
# ---------------------------------------------------------------------------


class TestNeo4jGraphName:
    def _fresh_manager(self, env):
        from codegraphcontext.core.database import DatabaseManager
        DatabaseManager._instance = None
        with patch.dict(os.environ, env, clear=True):
            mgr = DatabaseManager()
        return mgr

    def test_get_driver_with_graph_name_overrides_env(self):
        mgr = self._fresh_manager({
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "u",
            "NEO4J_PASSWORD": "p",
            "NEO4J_DATABASE": "envdb",
        })
        mgr._driver = MagicMock()

        wrapper = mgr.get_driver(graph_name="per_call_graph")
        assert wrapper._database == "per_call_graph"

    def test_get_driver_without_graph_name_uses_env_default(self):
        mgr = self._fresh_manager({
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "u",
            "NEO4J_PASSWORD": "p",
            "NEO4J_DATABASE": "envdb",
        })
        mgr._driver = MagicMock()

        wrapper = mgr.get_driver()
        assert wrapper._database == "envdb"

    def test_get_driver_without_env_or_arg_leaves_none(self):
        env = {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "u",
            "NEO4J_PASSWORD": "p",
        }
        mgr = self._fresh_manager(env)
        mgr._driver = MagicMock()

        wrapper = mgr.get_driver()
        assert wrapper._database is None

    def test_session_call_uses_overridden_graph_name(self):
        """End-to-end: per-call graph_name flows through to session(database=...)."""
        mgr = self._fresh_manager({
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "u",
            "NEO4J_PASSWORD": "p",
            "NEO4J_DATABASE": "envdb",
        })
        mock_driver = MagicMock()
        mgr._driver = mock_driver

        wrapper = mgr.get_driver(graph_name="my_graph")
        wrapper.session()
        mock_driver.session.assert_called_with(database="my_graph")

    def test_two_concurrent_calls_return_independent_wrappers(self):
        """Different graph_names → independent wrapper objects with independent binding."""
        mgr = self._fresh_manager({
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "u",
            "NEO4J_PASSWORD": "p",
        })
        mgr._driver = MagicMock()

        w1 = mgr.get_driver(graph_name="alpha")
        w2 = mgr.get_driver(graph_name="beta")
        assert w1 is not w2
        assert w1._database == "alpha"
        assert w2._database == "beta"


# ---------------------------------------------------------------------------
# FalkorDB Remote (easier to exercise than local — no subprocess)
# ---------------------------------------------------------------------------


class TestFalkorDBRemoteGraphName:
    def _reset(self):
        from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
        FalkorDBRemoteManager._instance = None
        FalkorDBRemoteManager._driver = None

    def setup_method(self):
        self._reset()

    def teardown_method(self):
        self._reset()

    def _warmed_manager(self, env):
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update(env)
        from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
        with patch.dict(os.environ, clean_env, clear=True):
            self._reset()
            mgr = FalkorDBRemoteManager()
            mock_driver = MagicMock()
            # Pre-warm the driver so get_driver() skips the connect path.
            mgr._driver = mock_driver
            return mgr, mock_driver

    def test_get_driver_with_graph_name_calls_select_graph_with_override(self):
        mgr, mock_driver = self._warmed_manager({
            'FALKORDB_HOST': 'h',
            'FALKORDB_GRAPH_NAME': 'default_g',
        })
        mock_driver.select_graph.return_value = MagicMock()

        mgr.get_driver(graph_name="per_call_g")
        mock_driver.select_graph.assert_called_with("per_call_g")

    def test_get_driver_without_graph_name_uses_env_default(self):
        mgr, mock_driver = self._warmed_manager({
            'FALKORDB_HOST': 'h',
            'FALKORDB_GRAPH_NAME': 'env_default_g',
        })
        mock_driver.select_graph.return_value = MagicMock()

        mgr.get_driver()
        mock_driver.select_graph.assert_called_with("env_default_g")

    def test_two_concurrent_calls_select_independent_graphs(self):
        mgr, mock_driver = self._warmed_manager({'FALKORDB_HOST': 'h'})
        g_alpha = MagicMock(name="alpha")
        g_beta = MagicMock(name="beta")
        mock_driver.select_graph.side_effect = lambda name: g_alpha if name == "alpha" else g_beta

        w1 = mgr.get_driver(graph_name="alpha")
        w2 = mgr.get_driver(graph_name="beta")
        # The wrappers hold independent graph objects; neither leaks into the
        # other even though they share the same underlying driver singleton.
        assert w1.graph is g_alpha
        assert w2.graph is g_beta


# ---------------------------------------------------------------------------
# FalkorDB local — same semantics, just reuse the remote-shaped assertions
# ---------------------------------------------------------------------------


class TestFalkorDBLocalGraphName:
    def _reset(self):
        from codegraphcontext.core.database_falkordb import FalkorDBManager
        FalkorDBManager._instance = None
        FalkorDBManager._driver = None
        FalkorDBManager._process = None

    def setup_method(self):
        self._reset()

    def teardown_method(self):
        self._reset()

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="FalkorDB Lite requires Python 3.12+")
    def test_get_driver_with_graph_name_calls_select_graph_with_override(self):
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_GRAPH_NAME': 'default_g'})
        from codegraphcontext.core.database_falkordb import FalkorDBManager
        with patch.dict(os.environ, clean_env, clear=True):
            self._reset()
            mgr = FalkorDBManager()
            mock_driver = MagicMock()
            mock_driver.select_graph.return_value = MagicMock()
            # Pre-warm so get_driver skips the subprocess path.
            mgr._driver = mock_driver

            mgr.get_driver(graph_name="per_call_g")
            # select_graph may be called more than once (warm-up ping), but the
            # last call (made by get_driver for the caller's session) must use
            # the per-call override.
            assert mock_driver.select_graph.call_args.args == ("per_call_g",)


# ---------------------------------------------------------------------------
# Kuzu — accepts and silently ignores
# ---------------------------------------------------------------------------


class TestKuzuGraphNameIgnored:
    def _reset(self):
        from codegraphcontext.core.database_kuzu import KuzuDBManager
        KuzuDBManager._instance = None
        KuzuDBManager._db = None
        KuzuDBManager._conn = None

    def setup_method(self):
        self._reset()

    def teardown_method(self):
        self._reset()

    def test_get_driver_accepts_and_ignores_graph_name(self):
        from codegraphcontext.core.database_kuzu import KuzuDBManager

        mgr = KuzuDBManager(db_path="/tmp/ignored_kuzu_test_path")
        mgr._conn = MagicMock()  # Pre-warm so get_driver skips the kuzu import path.

        # Both calls must succeed and produce equivalent behavior — Kuzu has no
        # per-graph namespace, so graph_name is a no-op.
        w_none = mgr.get_driver()
        w_named = mgr.get_driver(graph_name="irrelevant")
        assert w_none.conn is w_named.conn
