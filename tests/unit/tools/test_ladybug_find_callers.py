"""Regression test for #1505 — find_callers must work on LadybugDB.

`who_calls_function` ordered by `caller.is_dependency` under a
`RETURN DISTINCT` that did not project it. Ladybug's binder rejects that
("Variable caller is not in scope"), so every `find_callers` query on the
LadybugDB backend raised — and the MCP envelope reported success with zero
callers. The property must be projected and the ORDER BY must use the alias.
"""
from pathlib import Path

import pytest

from codegraphcontext.core.database_ladybug import LadybugDBManager
from codegraphcontext.tools.code_finder import CodeFinder


kuzu = pytest.importorskip("kuzu")


class _LadybugDBAdapter:
    def __init__(self, driver):
        self._driver = driver

    def get_driver(self, graph_name=None):
        return self._driver

    def get_backend_type(self) -> str:
        return "ladybugdb"


def _seed_call_graph(driver, repo: Path):
    caller_file = (repo / "app.py").as_posix()
    target_file = (repo / "lib.py").as_posix()
    with driver.session() as session:
        session.run(
            "CREATE (:Function {uid: $uid, name: $name, path: $path, "
            "line_number: 3, is_dependency: false})",
            uid=f"main:{caller_file}:3", name="main", path=caller_file,
        )
        session.run(
            "CREATE (:Function {uid: $uid, name: $name, path: $path, "
            "line_number: 10, is_dependency: false})",
            uid=f"greet:{target_file}:10", name="greet", path=target_file,
        )
        session.run(
            "MATCH (a:Function {name: 'main'}), (b:Function {name: 'greet'}) "
            "CREATE (a)-[:CALLS {line_number: 5}]->(b)"
        )


@pytest.mark.parametrize("with_path", [False, True])
def test_who_calls_function_returns_callers_on_kuzu(tmp_path, with_path):
    """All three query branches used the illegal ORDER BY; cover both entries."""
    repo = tmp_path / "repo"
    repo.mkdir()
    manager = LadybugDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        _seed_call_graph(driver, repo)
        finder = CodeFinder(_LadybugDBAdapter(driver))

        path = (repo / "lib.py").as_posix() if with_path else None
        results = finder.who_calls_function("greet", path=path)

        assert [r["caller_function"] for r in results] == ["main"], (
            "find_callers returned no callers on LadybugDB — the ORDER BY "
            "regression from #1505 is back"
        )
        assert results[0]["call_line_number"] == 5
    finally:
        manager.close_driver()
