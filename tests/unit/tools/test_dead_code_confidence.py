"""#1332: dead-code results carry confidence scoring on a real embedded graph."""
from pathlib import Path

import pytest

from codegraphcontext.core.database_ladybug import LadybugDBManager
from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

ladybug = pytest.importorskip("ladybug")


class _DBM:
    def __init__(self, driver):
        self._driver = driver

    def get_driver(self, graph_name=None):
        return self._driver

    def get_backend_type(self):
        return "ladybugdb"


@pytest.fixture()
def finder(tmp_path: Path):
    manager = LadybugDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "app.py"
    f.write_text("# fixture\n", encoding="utf-8")

    w = GraphWriter(driver)
    w.add_repository_to_graph(repo)
    w.add_file_to_graph(
        {
            "path": str(f), "repo_path": str(repo), "lang": "python",
            "imports": [],
            "functions": [
                {"name": "genuinely_dead", "line_number": 1, "end_line": 2, "args": []},
                {"name": "decorated_dead", "line_number": 4, "end_line": 5, "args": [],
                 "decorators": ["@app.route"]},
                {"name": "__str__", "line_number": 7, "end_line": 8, "args": []},
                {"name": "test_something", "line_number": 10, "end_line": 11, "args": []},
                {"name": "main", "line_number": 13, "end_line": 14, "args": []},
            ],
            "classes": [], "variables": [],
        },
        repo.name, {}, repo_path_str=str(repo.resolve()),
    )
    yield CodeFinder(_DBM(driver))
    manager.close_driver()


def test_default_results_are_scored_and_low_categories_hidden(finder):
    res = finder.find_dead_code()
    by_name = {r["function_name"]: r for r in res["potentially_unused_functions"]}
    assert by_name["genuinely_dead"]["confidence"] == "high"
    assert by_name["decorated_dead"]["confidence"] == "medium"
    assert "decorat" in by_name["decorated_dead"]["confidence_reason"]
    # Hard-excluded categories stay hidden by default.
    assert "__str__" not in by_name
    assert "test_something" not in by_name
    assert "main" not in by_name
    assert res["confidence_counts"]["high"] == 1
    assert res["confidence_counts"]["medium"] == 1
    assert res["confidence_counts"]["low"] == 0


def test_show_all_reintroduces_low_confidence_rows(finder):
    res = finder.find_dead_code(include_low_confidence=True)
    by_name = {r["function_name"]: r for r in res["potentially_unused_functions"]}
    assert by_name["__str__"]["confidence"] == "low"
    assert "dunder" in by_name["__str__"]["confidence_reason"]
    assert by_name["test_something"]["confidence"] == "low"
    assert by_name["main"]["confidence"] == "low"
    assert "entry-point" in by_name["main"]["confidence_reason"]
    # The default rows keep their scores alongside.
    assert by_name["genuinely_dead"]["confidence"] == "high"
    assert res["confidence_counts"]["low"] == 3
    assert res["total_count"] == 5
