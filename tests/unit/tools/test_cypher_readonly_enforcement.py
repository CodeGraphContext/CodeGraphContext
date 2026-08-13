"""
Defense-in-depth tests for read-only enforcement of user Cypher queries (#1010).

The regex guard (is_read_only_cypher) is only the first layer. These tests
assert the *session-level* enforcement that the guard cannot provide:

  - Neo4j: the read path opens a session with default_access_mode="READ", so
    the server rejects writes at the protocol layer.
  - FalkorDB: FalkorDB ignores default_access_mode, so the wrapper routes READ
    sessions through graph.ro_query (GRAPH.RO_QUERY), which the FalkorDB server
    refuses to run for any write operation.
"""

from codegraphcontext.core.database_falkordb import (
    FalkorDBDriverWrapper,
    FalkorDBSessionWrapper,
)


# --------------------------------------------------------------------------
# A mock FalkorDB graph that records which command (query vs ro_query) ran.
# --------------------------------------------------------------------------

class _MockResult:
    header = [("COL", "n")]
    result_set = [[1]]


class MockFalkorGraph:
    name = "test"

    def __init__(self):
        self.query_calls = []
        self.ro_query_calls = []

    def query(self, q, params=None, timeout=None):
        self.query_calls.append(q)
        return _MockResult()

    def ro_query(self, q, params=None, timeout=None):
        self.ro_query_calls.append(q)
        return _MockResult()


class MockFalkorDBManager:
    def __init__(self, graph):
        self._graph = graph

    def get_backend_type(self):
        return "falkordb"

    def get_driver(self, graph_name=None):
        return FalkorDBDriverWrapper(self._graph)


# --------------------------------------------------------------------------
# Wrapper-level: READ sessions must use ro_query; default sessions use query.
# --------------------------------------------------------------------------

def test_falkordb_read_session_uses_ro_query():
    graph = MockFalkorGraph()
    session = FalkorDBDriverWrapper(graph).session(default_access_mode="READ")
    assert isinstance(session, FalkorDBSessionWrapper)
    assert session.read_only is True

    session.run("MATCH (n) RETURN n LIMIT 1")
    assert graph.ro_query_calls == ["MATCH (n) RETURN n LIMIT 1"]
    assert graph.query_calls == []  # the write-capable path was never touched


def test_falkordb_default_session_uses_write_query_path():
    # Internal indexing writes (no access mode) must still use graph.query().
    graph = MockFalkorGraph()
    session = FalkorDBDriverWrapper(graph).session()
    assert session.read_only is False

    session.run("MATCH (n) RETURN n")
    assert graph.query_calls == ["MATCH (n) RETURN n"]
    assert graph.ro_query_calls == []


# --------------------------------------------------------------------------
# End-to-end via execute_cypher_query on a FalkorDB backend.
# --------------------------------------------------------------------------

def test_execute_cypher_query_falkordb_reads_via_ro_query():
    from codegraphcontext.tools.handlers.query_handlers import execute_cypher_query

    graph = MockFalkorGraph()
    manager = MockFalkorDBManager(graph)
    result = execute_cypher_query(manager, cypher_query="MATCH (n) RETURN n LIMIT 1")

    assert result.get("success") is True, f"Expected success, got: {result}"
    # The query reached the server through the server-enforced read-only path.
    assert graph.ro_query_calls == ["MATCH (n) RETURN n LIMIT 1"]
    assert graph.query_calls == []


def test_execute_cypher_query_falkordb_rejects_write_before_driver():
    from codegraphcontext.tools.handlers.query_handlers import execute_cypher_query

    graph = MockFalkorGraph()
    manager = MockFalkorDBManager(graph)

    for write in (
        "CREATE (n:Foo {x: 1})",
        "MATCH (n) DETACH DELETE n",
        "MATCH (n) SET n.pwned = true",
        "CALL apoc.create.node(['L'], {}) YIELD node RETURN node",
    ):
        result = execute_cypher_query(manager, cypher_query=write)
        assert "error" in result, f"write query slipped through the guard: {write!r}"
        # The regex guard rejected it before any driver call — nothing ran.
        assert graph.query_calls == []
        assert graph.ro_query_calls == []


def test_execute_cypher_query_falkordb_var_named_created_allowed():
    # keyword-as-substring must not be falsely rejected on the FalkorDB path.
    from codegraphcontext.tools.handlers.query_handlers import execute_cypher_query

    graph = MockFalkorGraph()
    manager = MockFalkorDBManager(graph)
    result = execute_cypher_query(
        manager, cypher_query="MATCH (n) RETURN n.created AS created LIMIT 1"
    )
    assert result.get("success") is True, f"Expected success, got: {result}"
    assert graph.ro_query_calls == ["MATCH (n) RETURN n.created AS created LIMIT 1"]
