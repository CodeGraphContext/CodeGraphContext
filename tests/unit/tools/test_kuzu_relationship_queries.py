from typing import Any, Dict, Optional

import pytest

from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools.query_tool_languages.cpp_toolkit import CppToolkit

class _FakeResult:
    def __iter__(self):
        return iter(self.data())

    def data(self):
        return []

class _FakeSession:
    def __init__(self, recorder: Dict[str, Any]):
        self._recorder = recorder

    def run(self, query: str, **kwargs: Any):
        self._recorder["last_query"] = query
        self._recorder["last_params"] = kwargs
        return _FakeResult()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

class _FakeDriver:
    def __init__(self, recorder: Dict[str, Any]):
        self._recorder = recorder

    def session(self):
        return _FakeSession(self._recorder)

class _FakeDBManager:
    def __init__(self, recorder: Dict[str, Any], backend: str = "kuzudb"):
        self._recorder = recorder
        self._backend = backend

    def get_driver(self, graph_name: str = None):
        return _FakeDriver(self._recorder)

    # Used only for certain query formatting paths; safe to stub.
    def get_backend_type(self) -> str:
        return self._backend


def _make_finder(
    recorder: Optional[Dict[str, Any]] = None,
    backend: str = "kuzudb",
) -> tuple[CodeFinder, Dict[str, Any]]:
    if recorder is None:
        recorder = {}
    db_manager = _FakeDBManager(recorder, backend)
    finder = CodeFinder(db_manager)
    return finder, recorder

def test_find_all_callers_parameterizes_symbol_and_path():
    finder, recorder = _make_finder()
    name = "TargetFn') MATCH (n) DELETE n //"
    path = "/repo/src/a'quoted.go"
    assert finder.find_all_callers(name, path=path, repo_path=None) == []
    assert name not in recorder["last_query"]
    assert path not in recorder["last_query"]
    assert recorder["last_params"]["function_name"] == name
    assert recorder["last_params"]["path"] == path


def test_find_all_callees_parameterizes_symbol_and_path():
    finder, recorder = _make_finder()
    name = "TargetFn') MATCH (n) DELETE n //"
    path = "/repo/src/a'quoted.go"
    assert finder.find_all_callees(name, path=path, repo_path=None) == []
    assert name not in recorder["last_query"]
    assert path not in recorder["last_query"]
    assert recorder["last_params"]["function_name"] == name
    assert recorder["last_params"]["path"] == path


def test_call_chain_avoids_list_extract():
    finder, recorder = _make_finder()
    finder.find_function_call_chain("FuncA", "FuncB", max_depth=5, repo_path=None)

    q = recorder["last_query"]
    assert "list_extract" not in q
    assert "MATCH path = (start)-[:CALLS|HEURISTIC_CALLS*1..5]->()" in q
    assert "size(call_rels) as chain_length" in q


@pytest.mark.parametrize(
    ("backend", "path_end_expression"),
    [
        ("kuzudb", "func_nodes[size(func_nodes)]"),
        ("ladybugdb", "func_nodes[size(func_nodes)]"),
        ("neo4j", "func_nodes[size(func_nodes)-1]"),
    ],
)
def test_call_chain_uses_backend_correct_list_index(backend, path_end_expression):
    finder, recorder = _make_finder(backend=backend)
    finder.find_function_call_chain("FuncA", "FuncB", max_depth=5, repo_path=None)

    assert f"{path_end_expression} as path_end" in recorder["last_query"]


@pytest.mark.parametrize("end_function", ["FuncB", "FuncC"])
def test_call_chain_returns_actual_endpoint_on_kuzu(tmp_path, end_function):
    pytest.importorskip("kuzu")
    from codegraphcontext.core.database_kuzu import KuzuDBManager

    manager = KuzuDBManager(str(tmp_path / "db"))
    try:
        with manager.get_driver().session() as session:
            for name in ("FuncA", "FuncB", "FuncC"):
                session.run(
                    "CREATE (:Function {uid: $name, name: $name, path: $path})",
                    name=name, path=(tmp_path / "app.py").as_posix(),
                )
            for caller, callee in [("FuncA", "FuncB"), ("FuncB", "FuncC")]:
                session.run(
                    "MATCH (a:Function {name: $caller}), (b:Function {name: $callee}) "
                    "CREATE (a)-[:CALLS]->(b)",
                    caller=caller, callee=callee,
                )

        chains = CodeFinder(manager).find_function_call_chain("FuncA", end_function)

        expected = ["FuncA", "FuncB"] + (["FuncC"] if end_function == "FuncC" else [])
        assert len(chains) == 1
        assert [node["name"] for node in chains[0]["function_chain"]] == expected
        assert chains[0]["chain_length"] == len(expected) - 1
    finally:
        manager.close_driver()


def test_import_alias_queries_use_imports_relationship():
    finder, recorder = _make_finder()
    finder.who_imports_module("numpy")

    query = recorder["last_query"]
    assert "import_alias: imp.alias" in query
    assert "module.alias" not in query

    cpp_query = CppToolkit().get_cypher_query("Module")
    assert "i.alias AS alias" in cpp_query
    assert "m.alias AS alias" not in cpp_query
