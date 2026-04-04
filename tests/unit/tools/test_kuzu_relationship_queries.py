from typing import Any, Dict, Optional

from codegraphcontext.tools.code_finder import CodeFinder


class _FakeResult:
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
    def __init__(self, recorder: Dict[str, Any]):
        self._recorder = recorder

    def get_driver(self):
        return _FakeDriver(self._recorder)

    # Used only for certain query formatting paths; safe to stub.
    def get_backend_type(self) -> str:
        return "kuzudb"


def _make_finder(recorder: Optional[Dict[str, Any]] = None) -> tuple[CodeFinder, Dict[str, Any]]:
    if recorder is None:
        recorder = {}
    db_manager = _FakeDBManager(recorder)
    finder = CodeFinder(db_manager)
    return finder, recorder


def test_find_all_callers_avoids_list_extract():
    finder, recorder = _make_finder()
    finder.find_all_callers("TargetFn", path="/repo/src/a.go", repo_path=None)

    q = recorder["last_query"]
    assert "list_extract" not in q
    assert "path_nodes[size(path_nodes)]" in q


def test_find_all_callees_avoids_list_extract():
    finder, recorder = _make_finder()
    finder.find_all_callees("TargetFn", path="/repo/src/a.go", repo_path=None)

    q = recorder["last_query"]
    assert "list_extract" not in q
    assert "path_nodes[size(path_nodes)]" in q


def test_call_chain_avoids_list_extract():
    finder, recorder = _make_finder()
    finder.find_function_call_chain("FuncA", "FuncB", max_depth=5, repo_path=None)

    q = recorder["last_query"]
    assert "list_extract" not in q
    assert "func_nodes[size(func_nodes)]" in q

