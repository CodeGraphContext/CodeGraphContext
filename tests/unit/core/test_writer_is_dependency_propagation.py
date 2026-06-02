"""Regression tests for is_dependency propagation through the writer.

`find_dead_code` filters on `func.is_dependency = false`. In Cypher `null = false`
evaluates to null rather than false, so a Function node that never received the
property is silently discarded and the tool returns an empty list.

Only about half the language extractors emit `is_dependency` per item, so the
writer has to supply the file-level value for the rest. Tests that hand-build
`file_data` normally include `is_dependency` on each item dict, which is exactly
why this survived the suite -- so these tests deliberately *omit* it, the way a
real extractor such as kotlin.py does.
"""

from pathlib import Path

import pytest

pytest.importorskip("kuzu")

from codegraphcontext.core.database_ladybug import LadybugDBManager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter


def _fresh_ladybug_manager(db_path: Path) -> LadybugDBManager:
    if LadybugDBManager._instance is not None:
        LadybugDBManager._instance.close_driver()
    LadybugDBManager._instance = None
    LadybugDBManager._db = None
    LadybugDBManager._conn = None
    return LadybugDBManager(db_path=str(db_path))


def _file_data(path: str, *, is_dependency: bool):
    """A file whose items carry no is_dependency of their own."""
    return {
        "path": path,
        "name": Path(path).name,
        "is_dependency": is_dependency,
        "lang": "kotlin",
        "functions": [
            {"name": "orphan", "line_number": 3, "context": None},
        ],
        "classes": [
            {"name": "Widget", "line_number": 7},
        ],
        "variables": [],
        "imports": [],
        "function_calls": [],
    }


def test_project_items_inherit_is_dependency_false(tmp_path):
    manager = _fresh_ladybug_manager(tmp_path / "isdep-project-db")
    try:
        driver = manager.get_driver()
        GraphWriter(driver).add_file_to_graph(
            _file_data("/repo/Main.kt", is_dependency=False),
            "repo",
            {},
            repo_path_str="/repo",
        )

        with driver.session() as session:
            fn = session.run(
                "MATCH (f:Function {name: $n}) RETURN f.is_dependency AS d", n="orphan"
            ).single()
            cls = session.run(
                "MATCH (c:Class {name: $n}) RETURN c.is_dependency AS d", n="Widget"
            ).single()

        # Not merely "falsy": null is falsy in Python but breaks the Cypher
        # predicate, which is the whole point of this test.
        assert fn["d"] is False
        assert cls["d"] is False
    finally:
        manager.close_driver()


def test_dependency_items_inherit_is_dependency_true(tmp_path):
    """Items inside a dependency file must be marked as dependencies."""
    manager = _fresh_ladybug_manager(tmp_path / "isdep-dependency-db")
    try:
        driver = manager.get_driver()
        GraphWriter(driver).add_file_to_graph(
            _file_data("/deps/Lib.kt", is_dependency=True),
            "repo",
            {},
            repo_path_str="/deps",
        )

        with driver.session() as session:
            fn = session.run(
                "MATCH (f:Function {name: $n}) RETURN f.is_dependency AS d", n="orphan"
            ).single()

        assert fn["d"] is True
    finally:
        manager.close_driver()


def test_extractor_supplied_is_dependency_is_not_overwritten(tmp_path):
    """A per-item value wins over the file-level default.

    The writer uses setdefault, so an extractor that already computes this
    per item (python.py and c.py among others) keeps its own answer.
    """
    manager = _fresh_ladybug_manager(tmp_path / "isdep-explicit-db")
    try:
        data = _file_data("/repo/Mixed.kt", is_dependency=False)
        data["functions"][0]["is_dependency"] = True

        driver = manager.get_driver()
        GraphWriter(driver).add_file_to_graph(data, "repo", {}, repo_path_str="/repo")

        with driver.session() as session:
            fn = session.run(
                "MATCH (f:Function {name: $n}) RETURN f.is_dependency AS d", n="orphan"
            ).single()

        assert fn["d"] is True
    finally:
        manager.close_driver()
