from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("kuzu")

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter


def _fresh_kuzu_manager(db_path: Path) -> KuzuDBManager:
    if KuzuDBManager._instance is not None:
        KuzuDBManager._instance.close_driver()
    KuzuDBManager._instance = None
    KuzuDBManager._db = None
    KuzuDBManager._conn = None
    return KuzuDBManager(db_path=str(db_path))


def test_kuzu_schema_metadata_migration_failures_are_fatal(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "migration-failure-db")
    try:
        manager._conn = MagicMock()

        def execute(statement):
            if "class_context_line" in statement:
                raise Exception("permission denied")
            return None

        manager._conn.execute.side_effect = execute

        with pytest.raises(RuntimeError, match="Kuzu Schema Migration Failed"):
            manager._initialize_schema()
    finally:
        manager.close_driver()


def test_class_node_type_persists_in_kuzu(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "node-type-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name,
                    c.path = $path,
                    c.line_number = $line_number,
                    c.node_type = $node_type
                """,
                uid="class-1",
                name="Factory",
                path="/repo/Sample.kt",
                line_number=4,
                node_type="companion_object",
            )
            row = session.run(
                "MATCH (c:Class {uid: $uid}) RETURN c.node_type AS node_type",
                uid="class-1",
            ).single()

        assert row is not None
        assert row["node_type"] == "companion_object"
    finally:
        manager.close_driver()


def test_calls_metadata_updates_do_not_duplicate_kuzu_relationships(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "calls-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (f:Function {uid: $uid})
                SET f.name = $name, f.path = $path, f.line_number = $line_number
                """,
                uid="caller",
                name="caller",
                path="/repo/Sample.kt",
                line_number=1,
            )
            session.run(
                """
                MERGE (f:Function {uid: $uid})
                SET f.name = $name, f.path = $path, f.line_number = $line_number
                """,
                uid="target",
                name="target",
                path="/repo/Sample.kt",
                line_number=5,
            )

        writer = GraphWriter(driver)
        call = {
            "caller_name": "caller",
            "caller_file_path": "/repo/Sample.kt",
            "caller_line_number": 1,
            "called_name": "target",
            "called_file_path": "/repo/Sample.kt",
            "called_line_number": 5,
            "line_number": 2,
            "args": [],
            "full_call_name": "target",
        }
        writer.write_function_call_groups(
            [{**call, "type": "function", "confidence": 0.25, "resolution_tier": 5}],
        )
        writer.write_function_call_groups(
            [{**call, "type": "function", "confidence": 0.95, "resolution_tier": 1}],
        )

        with driver.session() as session:
            rows = session.run(
                """
                MATCH (:Function {name: $caller, path: $path, line_number: $caller_line})
                      -[r:CALLS]->
                      (:Function {name: $called, path: $path, line_number: $called_line})
                RETURN r.confidence AS confidence, r.resolution_tier AS resolution_tier
                """,
                caller="caller",
                called="target",
                path="/repo/Sample.kt",
                caller_line=1,
                called_line=5,
            ).data()

        assert rows == [{"confidence": pytest.approx(0.95), "resolution_tier": 1}]
    finally:
        manager.close_driver()


def test_class_calls_use_target_line_in_kuzu(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "class-calls-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (f:Function {uid: $uid})
                SET f.name = $name, f.path = $path, f.line_number = $line_number
                """,
                uid="make",
                name="make",
                path="/repo/Sample.kt",
                line_number=3,
            )
            for line_number in (2, 7):
                session.run(
                    """
                    MERGE (c:Class {uid: $uid})
                    SET c.name = $name, c.path = $path, c.line_number = $line_number
                    """,
                    uid=f"inner-{line_number}",
                    name="Inner",
                    path="/repo/Sample.kt",
                    line_number=line_number,
                )

        writer = GraphWriter(driver)
        writer.write_function_call_groups(
            [],
            [
                {
                    "type": "function",
                    "caller_name": "make",
                    "caller_file_path": "/repo/Sample.kt",
                    "caller_line_number": 3,
                    "called_name": "Inner",
                    "called_file_path": "/repo/Sample.kt",
                    "called_line_number": 2,
                    "line_number": 3,
                    "args": [],
                    "full_call_name": "Inner",
                }
            ],
        )

        with driver.session() as session:
            rows = session.run(
                """
                MATCH (:Function {name: $caller, path: $path, line_number: $caller_line})
                      -[:CALLS]->
                      (called:Class {name: $called, path: $path})
                RETURN called.line_number AS line_number
                ORDER BY line_number
                """,
                caller="make",
                called="Inner",
                path="/repo/Sample.kt",
                caller_line=3,
            ).data()

        assert rows == [{"line_number": 2}]
    finally:
        manager.close_driver()


def test_class_function_containment_uses_owner_line_in_kuzu(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "contains-db")
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        file_path = repo_path / "Sample.kt"
        file_path.write_text("", encoding="utf-8")

        writer.add_repository_to_graph(repo_path)
        writer.add_file_to_graph(
            {
                "path": str(file_path),
                "repo_path": str(repo_path),
                "lang": "kotlin",
                "is_dependency": False,
                "functions": [
                    {
                        "name": "run",
                        "line_number": 3,
                        "args": [],
                        "class_context": "Worker",
                        "class_context_line": 2,
                    },
                    {
                        "name": "run",
                        "line_number": 8,
                        "args": [],
                        "class_context": "Worker",
                        "class_context_line": 7,
                    },
                ],
                "classes": [
                    {"name": "Worker", "line_number": 2, "node_type": "class_declaration"},
                    {"name": "Worker", "line_number": 7, "node_type": "class_declaration"},
                ],
                "variables": [],
                "imports": [],
                "function_calls": [],
            },
            repo_path.name,
            {},
            repo_path_str=str(repo_path),
        )

        with driver.session() as session:
            first_owner = session.run(
                """
                MATCH (:Class {name: $class_name, path: $path, line_number: $class_line})
                      -[:CONTAINS]->
                      (fn:Function {name: $function_name, path: $path})
                RETURN fn.line_number AS line_number
                ORDER BY line_number
                """,
                class_name="Worker",
                function_name="run",
                path=str(file_path.resolve()),
                class_line=2,
            ).data()
            second_owner = session.run(
                """
                MATCH (:Class {name: $class_name, path: $path, line_number: $class_line})
                      -[:CONTAINS]->
                      (fn:Function {name: $function_name, path: $path})
                RETURN fn.line_number AS line_number
                ORDER BY line_number
                """,
                class_name="Worker",
                function_name="run",
                path=str(file_path.resolve()),
                class_line=7,
            ).data()

        assert first_owner == [{"line_number": 3}]
        assert second_owner == [{"line_number": 8}]
    finally:
        manager.close_driver()
