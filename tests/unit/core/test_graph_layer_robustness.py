"""Regression tests for graph-layer failure handling."""
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.database_falkordb import (
    FalkorDBManager,
    FalkorDBSessionWrapper,
)
from codegraphcontext.tools.indexing.schema import create_graph_schema


class _FlakySession:
    """Session whose Nth statement always fails."""

    def __init__(self, fail_on):
        self.fail_on = fail_on
        self.executed = []

    def run(self, statement, *args, **kwargs):
        self.executed.append(" ".join(statement.split()))
        if len(self.executed) == self.fail_on:
            raise RuntimeError("simulated DDL failure")
        return MagicMock()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Driver:
    def __init__(self, session):
        self._session = session

    def session(self, **kwargs):
        return self._session


@pytest.mark.parametrize("backend", ["falkordb", "neo4j"])
def test_one_failing_ddl_statement_does_not_skip_the_rest(backend):
    """A single failing CREATE INDEX used to abort the remaining ~35
    statements, leaving the graph unindexed with nothing surfaced."""
    session = _FlakySession(fail_on=5)
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = backend

    create_graph_schema(_Driver(session), db_manager)

    assert len(session.executed) > 20, (
        f"only {len(session.executed)} statements ran; a failure still aborts the rest"
    )


def test_all_ddl_statements_run_when_none_fail():
    session = _FlakySession(fail_on=0)
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = "falkordb"

    create_graph_schema(_Driver(session), db_manager)

    assert len(session.executed) > 20


class _Graph:
    def __init__(self, exc):
        self.exc = exc

    def query(self, query, parameters):
        raise self.exc


def test_already_exists_is_swallowed_only_for_schema_ddl():
    """The substring test used to apply to every query, so a genuine data
    write that failed came back as an empty success wrapper."""
    wrapper = FalkorDBSessionWrapper(_Graph(RuntimeError("Index already exists")))

    # DDL: benign, swallowed.
    result = wrapper.run("CREATE INDEX FOR (f:Function) ON (f.name)")
    assert result.data() == []

    # Data write with the same error text: must propagate.
    with pytest.raises(RuntimeError):
        wrapper.run("UNWIND $batch AS row MERGE (n:Function {name: row.name})")


def test_schema_ddl_detection():
    is_ddl = FalkorDBSessionWrapper._is_schema_ddl
    assert is_ddl("CREATE INDEX FOR (f:Function) ON (f.name)")
    assert is_ddl("  create constraint foo IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE")
    assert is_ddl("CREATE FULLTEXT INDEX code_search_index FOR (n:Function) ON EACH [n.name]")
    assert is_ddl("CALL db.idx.fulltext.createNodeIndex('Function', 'name')")
    assert is_ddl("DROP INDEX foo")
    # A data query merely *mentioning* the words is not DDL.
    assert not is_ddl("MATCH (f:Function) WHERE f.source CONTAINS 'CREATE INDEX' RETURN f")
    assert not is_ddl("MERGE (n:Function {name: 'CREATE CONSTRAINT'})")
    assert not is_ddl("MATCH (n) RETURN n")


def test_close_driver_disconnects_the_connection_pool():
    """Dropping the reference alone leaked one redis client per cycle."""
    manager = FalkorDBManager.__new__(FalkorDBManager)
    pool = MagicMock()
    driver = MagicMock()
    driver.connection.connection_pool = pool
    manager._driver = driver
    manager._graph = MagicMock()
    manager._graphs = {"g": MagicMock()}
    manager._process = None

    manager.close_driver()

    pool.disconnect.assert_called_once()
    assert manager._driver is None


def test_close_driver_survives_a_pool_that_raises():
    manager = FalkorDBManager.__new__(FalkorDBManager)
    driver = MagicMock()
    driver.connection.connection_pool.disconnect.side_effect = RuntimeError("boom")
    manager._driver = driver
    manager._graph = None
    manager._graphs = {}
    manager._process = None

    manager.close_driver()   # must not raise

    assert manager._driver is None
