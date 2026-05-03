from unittest.mock import MagicMock

from codegraphcontext.core.database_falkordb import FalkorDBSessionWrapper


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
