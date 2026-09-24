from pathlib import Path

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

kuzu = pytest.importorskip("kuzu")


def _fresh_kuzu_manager(db_path: Path) -> KuzuDBManager:
    if KuzuDBManager._instance is not None:
        KuzuDBManager._instance.close_driver()
    KuzuDBManager._instance = None
    KuzuDBManager._db = None
    KuzuDBManager._conn = None
    return KuzuDBManager(db_path=str(db_path))


class _KuzuDBAdapter:
    def __init__(self, driver):
        self._driver = driver

    def get_driver(self, graph_name=None):
        return self._driver

    def get_backend_type(self) -> str:
        return "kuzudb"


def test_finds_functions_by_argument_name_or_type_without_duplicates(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    file_path = repo / "OrderRepository.java"
    file_path.write_text(
        "Page<Order> findAll(OrderFilter filter, Pageable pageable) {}\n",
        encoding="utf-8",
    )

    manager = _fresh_kuzu_manager(tmp_path / "db")
    driver = manager.get_driver()
    try:
        writer = GraphWriter(driver)
        writer.add_repository_to_graph(repo)
        writer.add_file_to_graph(
            {
                "path": str(file_path),
                "repo_path": str(repo),
                "lang": "java",
                "functions": [
                    {
                        "name": "findAll",
                        "line_number": 1,
                        "args": ["filter", "pageable"],
                        "arg_types": ["OrderFilter", "Pageable"],
                    }
                ],
                "classes": [],
                "variables": [],
            },
            repo.name,
            {},
            repo_path_str=str(repo.resolve()),
        )
        finder = CodeFinder(_KuzuDBAdapter(driver))

        assert [
            row["function_name"] for row in finder.find_functions_by_argument("filter")
        ] == ["findAll"]
        assert [
            row["function_name"]
            for row in finder.find_functions_by_argument("OrderFilter")
        ] == ["findAll"]
    finally:
        manager.close_driver()


def test_adds_argument_types_to_an_existing_kuzu_schema(tmp_path: Path):
    db_path = tmp_path / "existing-db"
    database = kuzu.Database(str(db_path))
    connection = kuzu.Connection(database)
    connection.execute(
        "CREATE NODE TABLE Function(uid STRING, name STRING, path STRING, "
        "line_number INT64, PRIMARY KEY (uid))"
    )
    connection.close()
    database.close()

    manager = _fresh_kuzu_manager(db_path)
    try:
        with manager.get_driver().session() as session:
            columns = {
                row["name"]
                for row in session.run("CALL TABLE_INFO('Function') RETURN *").data()
            }

        assert "arg_types" in columns
    finally:
        manager.close_driver()
