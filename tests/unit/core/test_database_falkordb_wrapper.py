from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.database_falkordb import (
    FalkorDBManager,
    FalkorDBSessionWrapper,
    FalkorDBUnavailableError,
)


def test_run_translates_single_unique_constraint_to_graph_constraint():
    graph = MagicMock()
    graph.name = "g"
    session = FalkorDBSessionWrapper(graph)

    session.run("CREATE CONSTRAINT repository_path IF NOT EXISTS FOR (r:Repository) REQUIRE r.path IS UNIQUE")

    graph.execute_command.assert_called_once_with(
        "GRAPH.CONSTRAINT",
        "CREATE",
        "g",
        "UNIQUE",
        "NODE",
        "Repository",
        "PROPERTIES",
        1,
        "path",
    )


def test_run_translates_composite_unique_constraint_to_graph_constraint():
    graph = MagicMock()
    graph.name = "g"
    session = FalkorDBSessionWrapper(graph)

    session.run(
        "CREATE CONSTRAINT function_unique IF NOT EXISTS FOR (f:Function) "
        "REQUIRE (f.name, f.path, f.line_number) IS UNIQUE"
    )

    graph.execute_command.assert_called_once_with(
        "GRAPH.CONSTRAINT",
        "CREATE",
        "g",
        "UNIQUE",
        "NODE",
        "Function",
        "PROPERTIES",
        3,
        "name",
        "path",
        "line_number",
    )


def test_run_keeps_regular_queries_on_graph_query():
    graph = MagicMock()
    graph.name = "g"
    graph.query.return_value = MagicMock(result_set=[])
    session = FalkorDBSessionWrapper(graph)

    session.run("MATCH (n) RETURN count(n) AS c")

    graph.query.assert_called_once()
    graph.execute_command.assert_not_called()


def test_startup_failure_for_one_path_does_not_disable_another_path(tmp_path, monkeypatch):
    monkeypatch.setattr(FalkorDBManager, "_instance", None)
    monkeypatch.setattr(FalkorDBManager, "_process", None)
    monkeypatch.setattr(FalkorDBManager, "_driver", None)
    monkeypatch.setattr(FalkorDBManager, "_graphs", {})
    monkeypatch.setattr(FalkorDBManager, "_failed_configurations", set())

    unavailable = FalkorDBManager(db_path=str(tmp_path / "unavailable" / "falkordb.db"))
    monkeypatch.setattr(
        unavailable,
        "_ensure_server_running",
        MagicMock(side_effect=FalkorDBUnavailableError("test startup failure")),
    )

    with pytest.raises(FalkorDBUnavailableError, match="test startup failure"):
        unavailable.get_driver()

    available = FalkorDBManager(db_path=str(tmp_path / "available" / "falkordb.db"))
    graph = MagicMock()
    available._driver = MagicMock()
    available._graphs = {available.graph_name: graph}

    assert available.get_driver().graph is graph


def test_factory_keeps_explicit_falkordb_strict_for_each_path(
    monkeypatch,
    tmp_path,
):
    from codegraphcontext import core
    from codegraphcontext.core import database_falkordb

    failed_path = str(tmp_path / "failed" / "falkordb")
    working_path = str(tmp_path / "working" / "falkordb")

    class PathScopedFalkorManager:
        def __init__(self, db_path):
            self.db_path = db_path

        def get_driver(self):
            if self.db_path == failed_path:
                raise FalkorDBUnavailableError("test startup failure")

    monkeypatch.setenv("DEFAULT_DATABASE", "falkordb")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CGC_RUNTIME_DB_TYPE", raising=False)
    monkeypatch.setattr(core, "_FALKORDB_DISABLED", False)
    monkeypatch.setattr(core, "_is_falkordb_available", lambda: True)
    monkeypatch.setattr(database_falkordb, "FalkorDBManager", PathScopedFalkorManager)

    with pytest.raises(ValueError, match="strict and will not fall back"):
        core.get_database_manager(failed_path)

    assert isinstance(core.get_database_manager(working_path), PathScopedFalkorManager)
