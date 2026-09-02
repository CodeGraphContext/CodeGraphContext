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

    assert (
        "MATCH (f:Function) OPTIONAL MATCH (f)-[:HAS_PARAMETER]->(p:Parameter)"
        in driver.query
    )
    assert "p.name = $argument_name OR $argument_name IN f.arg_types" in driver.query
    assert "RETURN DISTINCT f.name AS function_name" in driver.query
    assert driver.params["argument_name"] == "OrderFilter"
