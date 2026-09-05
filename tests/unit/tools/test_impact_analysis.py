from typing import Any, Dict, List, Optional
from codegraphcontext.tools.code_finder import CodeFinder

class _FakeResult:
    def __init__(self, data_list: List[Dict[str, Any]]):
        self._data = data_list

    def data(self) -> List[Dict[str, Any]]:
        return self._data

    def single(self) -> Optional[Dict[str, Any]]:
        if self._data:
            return self._data[0]
        return None

    def __iter__(self):
        return iter(self._data)

class _FakeSession:
    def __init__(self, recorder: Dict[str, Any]):
        self._recorder = recorder
        self._recorder["queries"] = []

    def run(self, query: str, **kwargs: Any) -> _FakeResult:
        self._recorder["queries"].append({
            "query": query,
            "params": kwargs
        })
        
        # Mock responses based on query contents
        if "MATCH (f:File)" in query:
            if kwargs.get("target") == "auth.py":
                return _FakeResult([{"uid": "file_auth", "name": "auth.py", "path": "src/auth.py", "type": "File"}])
            return _FakeResult([])
            
        elif "MATCH (f:File)-[:CONTAINS*1..2]->(c)" in query:
            return _FakeResult([
                {"uid": "func_login", "name": "login", "path": "src/auth.py", "labels": ["Function"]},
                {"uid": "class_auth", "name": "AuthService", "path": "src/auth.py", "labels": ["Class"]}
            ])
            
        elif "MATCH (c)" in query and "c.name = $target" in query:
            if kwargs.get("target") == "AuthService":
                return _FakeResult([{"uid": "class_auth", "name": "AuthService", "path": "src/auth.py", "labels": ["Class"]}])
            return _FakeResult([])
            
        elif "MATCH p = (source)-[:CALLS" in query:
            return _FakeResult([
                {
                    "path_nodes": [
                        {"uid": "func_main", "name": "main", "path": "src/main.py", "labels": ["Function"]},
                        {"uid": "func_login", "name": "login", "path": "src/auth.py", "labels": ["Function"]}
                    ],
                    "path_rels": [
                        {"type": "CALLS", "line_number": 42}
                    ]
                }
            ])
            
        elif "MATCH (target)<-[r:CALLS" in query:
            return _FakeResult([{"count": 5}])

        return _FakeResult([])

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

    def get_driver(self, graph_name=None):
        return _FakeDriver(self._recorder)

    def get_backend_type(self) -> str:
        return "kuzudb"

def _make_finder() -> tuple[CodeFinder, Dict[str, Any]]:
    recorder = {}
    db_manager = _FakeDBManager(recorder)
    finder = CodeFinder(db_manager)
    return finder, recorder

def test_analyze_impact_symbol_target():
    finder, recorder = _make_finder()
    res = finder.analyze_impact(target="AuthService")
    
    assert res["target"]["name"] == "AuthService"
    assert res["target"]["type"] == "Class"
    assert res["risk_level"] in ("Low", "Medium", "High")
    assert res["impact_score"] > 0.0
    assert len(res["affected_nodes"]) == 1
    assert res["affected_nodes"][0]["name"] == "main"
    assert len(res["explanations"]) == 1
    assert "main" in res["explanations"][0]["text"]
    assert "calls" in res["explanations"][0]["text"]

def test_analyze_impact_file_target():
    finder, recorder = _make_finder()
    res = finder.analyze_impact(target="auth.py")
    
    # Target should resolve to file details
    assert res["target"]["name"] == "auth.py"
    assert res["target"]["type"] == "File"
    assert res["impact_score"] > 0.0
    assert len(res["affected_nodes"]) == 1
    assert res["affected_nodes"][0]["name"] == "main"

def test_analyze_impact_not_found():
    finder, recorder = _make_finder()
    res = finder.analyze_impact(target="NonExistentSymbol")
    
    assert res["impact_score"] == 0.0
    assert res["risk_level"] == "Low"
    assert "warning" in res
    assert len(res["affected_nodes"]) == 0
