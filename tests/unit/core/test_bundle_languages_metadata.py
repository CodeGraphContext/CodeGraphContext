"""Regression tests for bundle metadata["languages"].

Bundle export derives the language list from a `language` property on File
nodes. Nothing ever set that property, and the export's `if record["language"]`
guard then filtered every row out -- so every bundle, including the published
registry ones, advertised no languages at all.

There were two defects: the missing property, and the fact that the whole block
sat inside `if repo_path and repo_path.exists()`, so an unscoped whole-graph
export never set the key even once the property existed.
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


def _file_data(path: str, lang: str):
    return {
        "path": path,
        "name": Path(path).name,
        "is_dependency": False,
        "lang": lang,
        "functions": [{"name": f"fn_{lang}", "line_number": 1, "context": None}],
        "classes": [],
        "variables": [],
        "imports": [],
        "function_calls": [],
    }


def test_file_node_records_its_language(tmp_path):
    manager = _fresh_ladybug_manager(tmp_path / "lang-db")
    try:
        driver = manager.get_driver()
        GraphWriter(driver).add_file_to_graph(
            _file_data("/repo/Main.kt", "kotlin"), "repo", {}, repo_path_str="/repo"
        )

        with driver.session() as session:
            row = session.run(
                "MATCH (f:File {name: $n}) RETURN f.language AS language", n="Main.kt"
            ).single()

        assert row["language"] == "kotlin"
    finally:
        manager.close_driver()


def test_languages_are_distinct_across_a_mixed_repository(tmp_path):
    """The export groups File nodes by language; each should appear once."""
    manager = _fresh_ladybug_manager(tmp_path / "lang-multi-db")
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        for name, lang in [
            ("a.py", "python"),
            ("b.kt", "kotlin"),
            ("c.js", "javascript"),
            ("d.py", "python"),
        ]:
            writer.add_file_to_graph(
                _file_data(f"/repo/{name}", lang), "repo", {}, repo_path_str="/repo"
            )

        with driver.session() as session:
            rows = session.run(
                "MATCH (f:File) RETURN f.language AS language, count(*) AS count"
            )
            languages = {r["language"]: r["count"] for r in rows if r["language"]}

        assert sorted(languages) == ["javascript", "kotlin", "python"]
        assert languages["python"] == 2
    finally:
        manager.close_driver()


def test_language_survives_the_kuzu_property_allow_list(tmp_path):
    """`language` must be in SCHEMA_MAP['File'].

    The Ladybug backend filters node properties against an allow-list and drops
    unknown ones silently, so a schema column alone is not sufficient -- this is
    the step that would fail without the allow-list entry, and it would fail
    quietly.
    """
    manager = _fresh_ladybug_manager(tmp_path / "lang-allowlist-db")
    try:
        driver = manager.get_driver()
        GraphWriter(driver).add_file_to_graph(
            _file_data("/repo/x.rs", "rust"), "repo", {}, repo_path_str="/repo"
        )
        with driver.session() as session:
            row = session.run(
                "MATCH (f:File {name: $n}) RETURN f.language AS language", n="x.rs"
            ).single()
        assert row["language"] == "rust", (
            "language was dropped between the writer and storage -- check the "
            "File entry in SCHEMA_MAP"
        )
    finally:
        manager.close_driver()
