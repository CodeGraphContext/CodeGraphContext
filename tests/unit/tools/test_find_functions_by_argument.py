from unittest.mock import MagicMock

from codegraphcontext.tools.code_finder import CodeFinder


class _RecordingDriver:
    def __init__(self):
        self.query = ""
        self.params = {}

    def session(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def run(self, query, **params):
        self.query = " ".join(query.split())
        self.params = params
        result = MagicMock()
        result.data.return_value = []
        return result


def test_argument_search_queries_parameter_names_and_function_argument_types():
    driver = _RecordingDriver()
    db_manager = MagicMock()
    db_manager.get_driver.return_value = driver
    db_manager.get_backend_type.return_value = "neo4j"
    finder = CodeFinder(db_manager)

    finder.find_functions_by_argument("OrderFilter")

    assert "OPTIONAL MATCH (f)-[:HAS_PARAMETER]->(p:Parameter {name: $argument_name})" in driver.query
    assert "$argument_name IN f.arg_types" in driver.query
    assert "RETURN DISTINCT f.name AS function_name" in driver.query
    assert driver.params["argument_name"] == "OrderFilter"


def test_argument_search_filters_functions_on_a_real_graph(tmp_path):
    """Behavioral pin on real KùzuDB: the original OPTIONAL MATCH ... WHERE
    form never filtered f, so every function came back for ANY search term —
    a query-text mock cannot catch that."""
    import pytest as _pytest
    _pytest.importorskip("kuzu")
    from codegraphcontext.core.database_kuzu import KuzuDBManager
    from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

    class _DBM:
        def __init__(self, d): self._d = d
        def get_driver(self, graph_name=None): return self._d
        def get_backend_type(self): return "kuzudb"

    manager = KuzuDBManager(str(tmp_path / "db"))
    d = manager.get_driver()
    try:
        w = GraphWriter(d)
        repo = tmp_path / "repo"; repo.mkdir()
        f = repo / "a.java"; f.write_text("x", encoding="utf-8")
        w.add_repository_to_graph(repo)
        w.add_file_to_graph({
            "path": str(f), "repo_path": str(repo), "lang": "java", "imports": [],
            "functions": [
                {"name": "byParamName", "line_number": 1, "end_line": 2, "args": ["orderFilter"]},
                {"name": "byArgType", "line_number": 4, "end_line": 5, "args": ["f"], "arg_types": ["OrderFilter"]},
                {"name": "unrelated", "line_number": 7, "end_line": 8, "args": ["x"], "arg_types": ["String"]},
            ], "classes": [], "variables": []},
            repo.name, {}, repo_path_str=str(repo.resolve()))

        finder = CodeFinder(_DBM(d))
        by_type = sorted(r["function_name"] for r in finder.find_functions_by_argument("OrderFilter"))
        by_name = sorted(r["function_name"] for r in finder.find_functions_by_argument("orderFilter"))
        assert by_type == ["byArgType"]
        assert by_name == ["byParamName"]
    finally:
        manager.close_driver()
