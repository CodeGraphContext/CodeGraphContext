"""
Regression test for: execute_cypher_query returns MCP error -32000 on FalkorDB/KuzuDB setups.

Root cause: execute_cypher_query (query_handlers.py) calls
    db_manager.get_driver().session(default_access_mode="READ")
but FalkorDBDriverWrapper.session() and KuzuDriverWrapper.session() did not
accept **kwargs, causing a TypeError that the MCP JSON-RPC layer converts to -32000.

Fix: Both wrappers now accept **kwargs and silently ignore Neo4j-specific args.

Repro queries from user report (v4.8.0):
  - MATCH (n) RETURN labels(n) AS labels, count(n) AS count ORDER BY count DESC LIMIT 20
  - MATCH (n) RETURN count(n) AS total_nodes
  - RETURN 1 AS test
"""

import threading
import pytest


# ---------------------------------------------------------------------------
# FalkorDBDriverWrapper — session(**kwargs) fix
# ---------------------------------------------------------------------------

class TestFalkorDBDriverWrapperSessionKwargs:
    """session() must accept and ignore Neo4j-specific kwargs."""

    def _make_wrapper(self):
        from codegraphcontext.core.database_falkordb import FalkorDBDriverWrapper, FalkorDBSessionWrapper

        class MockGraph:
            name = "test"
            def query(self, q, *a, **kw):
                class R:
                    header = [("COL", "result")]
                    result_set = [[1]]
                return R()

        wrapper = FalkorDBDriverWrapper(MockGraph())
        return wrapper, FalkorDBSessionWrapper

    def test_session_accepts_default_access_mode(self):
        """Calling .session(default_access_mode='READ') must not raise TypeError."""
        wrapper, FalkorDBSessionWrapper = self._make_wrapper()
        # This was the exact call that caused -32000 before the fix
        session = wrapper.session(default_access_mode="READ")
        assert isinstance(session, FalkorDBSessionWrapper)

    def test_session_accepts_arbitrary_kwargs(self):
        """Wrapper must silently ignore any unknown Neo4j driver kwargs."""
        wrapper, FalkorDBSessionWrapper = self._make_wrapper()
        session = wrapper.session(default_access_mode="READ", fetch_size=100, database="neo4j")
        assert isinstance(session, FalkorDBSessionWrapper)

    def test_session_no_kwargs_still_works(self):
        """Calling .session() with no args must still work (backward compat)."""
        wrapper, FalkorDBSessionWrapper = self._make_wrapper()
        session = wrapper.session()
        assert isinstance(session, FalkorDBSessionWrapper)

    def test_execute_cypher_query_return_1(self):
        """RETURN 1 AS test — the simplest possible query — must succeed."""
        from codegraphcontext.core.database_falkordb import FalkorDBDriverWrapper

        class MockGraph:
            name = "test"
            def query(self, q, *a, **kw):
                class R:
                    header = [("COL", "test")]
                    result_set = [[1]]
                return R()

        class MockDBManager:
            def get_driver(self):
                return FalkorDBDriverWrapper(MockGraph())

        from codegraphcontext.tools.handlers.query_handlers import execute_cypher_query
        result = execute_cypher_query(MockDBManager(), cypher_query="RETURN 1 AS test")
        assert result.get("success") is True, f"Expected success, got: {result}"
        assert result["record_count"] == 1

    def test_execute_cypher_query_match_nodes(self):
        """MATCH (n) RETURN labels(n) — user's actual failing query shape — must succeed."""
        from codegraphcontext.core.database_falkordb import FalkorDBDriverWrapper

        class MockGraph:
            name = "test"
            def query(self, q, *a, **kw):
                class R:
                    header = [("COL", "labels"), ("COL", "count")]
                    result_set = [["Function", 100], ["Class", 50]]
                return R()

        class MockDBManager:
            def get_driver(self):
                return FalkorDBDriverWrapper(MockGraph())

        from codegraphcontext.tools.handlers.query_handlers import execute_cypher_query
        result = execute_cypher_query(
            MockDBManager(),
            cypher_query="MATCH (n) RETURN labels(n) AS labels, count(n) AS count ORDER BY count DESC LIMIT 20"
        )
        assert result.get("success") is True, f"Expected success, got: {result}"
        assert result["record_count"] == 2


# ---------------------------------------------------------------------------
# KuzuDriverWrapper — session(**kwargs) fix
# ---------------------------------------------------------------------------

class TestKuzuDriverWrapperSessionKwargs:
    """session() must accept and ignore Neo4j-specific kwargs."""

    def _make_wrapper(self):
        from codegraphcontext.core.database_kuzu import KuzuDriverWrapper
        import inspect
        return KuzuDriverWrapper, inspect

    def test_session_signature_accepts_kwargs(self):
        """KuzuDriverWrapper.session must have **kwargs in its signature."""
        from codegraphcontext.core.database_kuzu import KuzuDriverWrapper
        import inspect
        sig = inspect.signature(KuzuDriverWrapper.session)
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        assert has_var_keyword, (
            f"KuzuDriverWrapper.session() is missing **kwargs. "
            f"Calling it with default_access_mode='READ' will raise TypeError → MCP -32000. "
            f"Actual signature: {sig}"
        )

    def test_session_call_with_default_access_mode_does_not_raise(self):
        """session(default_access_mode='READ') must not raise TypeError."""
        from codegraphcontext.core.database_kuzu import KuzuDriverWrapper
        from unittest.mock import MagicMock

        mock_conn = MagicMock()
        lock = threading.RLock()
        wrapper = KuzuDriverWrapper.__new__(KuzuDriverWrapper)
        wrapper.conn = mock_conn
        wrapper._query_lock = lock

        # Must not raise TypeError
        try:
            session = wrapper.session(default_access_mode="READ")
        except TypeError as e:
            pytest.fail(
                f"KuzuDriverWrapper.session(default_access_mode='READ') raised TypeError: {e}\n"
                "This causes MCP -32000 for all execute_cypher_query calls on KuzuDB backends."
            )
