"""#1512: the simulator's load queries must execute on the embedded backends.

Previously the relationship query used a bare pattern predicate in WHERE and
labels(n1)[0]/labels(n2)[0], neither of which the Ladybug engine (or the
translator's literal labels(n)[0] rewrite) could handle — simulate_metrics
failed on every LadybugDB/LadybugDB database.
"""
from pathlib import Path

import pytest

from codegraphcontext.core.database_ladybug import LadybugDBManager
from codegraphcontext.core.simulator import CodeGraphTwin
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

kuzu = pytest.importorskip("kuzu")


class _DBM:
    def __init__(self, driver):
        self._driver = driver

    def get_driver(self, graph_name=None):
        return self._driver

    def get_backend_type(self):
        return "ladybugdb"


def test_twin_loads_nodes_and_edges_from_kuzu(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "a.py"
    f.write_text("def x():\n    y()\n\ndef y():\n    pass\n", encoding="utf-8")

    manager = LadybugDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        w = GraphWriter(driver)
        w.add_repository_to_graph(repo)
        w.add_file_to_graph(
            {
                "path": str(f), "repo_path": str(repo), "lang": "python",
                "imports": [],
                "functions": [
                    {"name": "x", "line_number": 1, "end_line": 2, "args": [],
                     "cyclomatic_complexity": 1},
                    {"name": "y", "line_number": 4, "end_line": 5, "args": [],
                     "cyclomatic_complexity": 1},
                ],
                "classes": [], "variables": [],
            },
            repo.name, {}, repo_path_str=str(repo.resolve()),
        )

        twin = CodeGraphTwin(str(repo.resolve()))
        twin.load_from_db(_DBM(driver))

        # Repository + File + 2 Functions, and the CONTAINS chain between them.
        assert len(twin.nodes) >= 3
        assert len(twin.edges) >= 2
    finally:
        manager.close_driver()
