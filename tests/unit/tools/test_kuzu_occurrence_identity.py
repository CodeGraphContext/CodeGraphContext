"""#1393 on the embedded backends: colliding symbols must stay distinct on KuzuDB.

The writer-side fix alone was not enough here — Kùzu keys these node tables on
a computed ``uid``, and the compat layer built that uid from
``(name, path, line_number)``, so two symbols sharing a name and a line still
collapsed onto one row no matter what the MERGE pattern said. The uid must
include ``occurrence_index``.
"""
from pathlib import Path

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

kuzu = pytest.importorskip("kuzu")


def _new_kuzu_driver(tmp_path: Path):
    manager = KuzuDBManager(str(tmp_path / "db"))
    return manager, manager.get_driver()


def _write_colliding_file(writer: GraphWriter, repo: Path, file_path: Path):
    """Two distinct `tfoot` selectors on one line — the grouped-CSS-rule shape."""
    writer.add_file_to_graph(
        {
            "path": str(file_path),
            "repo_path": str(repo),
            "lang": "css",
            "imports": [],
            "functions": [
                {"name": "tfoot", "line_number": 3, "end_line": 5,
                 "args": ["th"], "class_context": "th"},
                {"name": "tfoot", "line_number": 3, "end_line": 5,
                 "args": ["td"], "class_context": "td"},
            ],
            "classes": [],
            "variables": [],
        },
        repo.name,
        {},
        repo_path_str=str(repo.resolve()),
    )


def test_kuzu_keeps_same_name_same_line_functions_distinct(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    file_path = repo / "table.css"
    file_path.write_text("tfoot th, tfoot td { }\n", encoding="utf-8")

    manager, driver = _new_kuzu_driver(tmp_path)
    try:
        writer = GraphWriter(driver)
        writer.add_repository_to_graph(repo)
        _write_colliding_file(writer, repo, file_path)

        with driver.session() as session:
            rows = session.run(
                "MATCH (f:Function {name: $name}) "
                "RETURN f.uid AS uid, f.class_context AS ctx, f.occurrence_index AS occ "
                "ORDER BY occ",
                name="tfoot",
            ).data()

        assert len(rows) == 2, f"expected 2 distinct nodes, got {rows}"
        assert rows[0]["occ"] == 0 and rows[1]["occ"] == 1
        assert rows[0]["uid"] != rows[1]["uid"]
        # Each node keeps its own properties instead of the last write winning.
        assert {r["ctx"] for r in rows} == {"th", "td"}
    finally:
        manager.close_driver()


def test_kuzu_rewrite_is_idempotent_for_colliding_symbols(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    file_path = repo / "table.css"
    file_path.write_text("tfoot th, tfoot td { }\n", encoding="utf-8")

    manager, driver = _new_kuzu_driver(tmp_path)
    try:
        writer = GraphWriter(driver)
        writer.add_repository_to_graph(repo)
        _write_colliding_file(writer, repo, file_path)
        # Writing the same parse again must MERGE onto the same uids,
        # not mint a third node.
        _write_colliding_file(writer, repo, file_path)

        with driver.session() as session:
            rows = session.run(
                "MATCH (f:Function {name: $name}) RETURN f.uid AS uid",
                name="tfoot",
            ).data()
        assert len(rows) == 2, f"expected exactly 2 nodes after re-write, got {rows}"
    finally:
        manager.close_driver()
