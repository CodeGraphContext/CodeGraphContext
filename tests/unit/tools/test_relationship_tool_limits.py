"""Unit tests for relationship query tool limits and truncation flags (Issue #1542)."""
import json
from pathlib import Path
import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools.handlers import analysis_handlers

kuzu = pytest.importorskip("kuzu")


class _KuzuDBAdapter:
    def __init__(self, driver):
        self._driver = driver

    def get_driver(self, graph_name=None):
        return self._driver

    def get_backend_type(self) -> str:
        return "kuzudb"


def test_find_callers_truncation(tmp_path, monkeypatch):
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        with driver.session() as session:
            session.run(
                "CREATE (:Function {uid: 'target:lib.py:1', name: 'target_fn', path: 'lib.py', "
                "line_number: 1, is_dependency: false})"
            )
            for i in range(25):
                caller_name = f"caller_{i}"
                session.run(
                    "CREATE (:Function {uid: $uid, name: $name, path: 'app.py', "
                    "line_number: $line, is_dependency: false})",
                    uid=f"{caller_name}:app.py:{i+10}",
                    name=caller_name,
                    line=i + 10,
                )
                session.run(
                    "MATCH (a:Function {name: $caller}), (b:Function {name: 'target_fn'}) "
                    "CREATE (a)-[:CALLS {line_number: $line}]->(b)",
                    caller=caller_name,
                    line=i + 10,
                )

        finder = CodeFinder(_KuzuDBAdapter(driver))

        # Default limit 20
        res = finder.analyze_code_relationships("find_callers", "target_fn")
        assert len(res["results"]) == 20
        assert res["truncated"] is True
        assert res["result_limit"] == 20
        assert "(truncated — more exist)" in res["summary"]

        # Handler forwarding
        handler_res = analysis_handlers.analyze_code_relationships(finder, query_type="find_callers", target="target_fn")
        assert handler_res["truncated"] is True
        assert handler_res["result_limit"] == 20

        # Custom config limit 50 via TOOL_RESULT_LIMITS
        monkeypatch.setenv("TOOL_RESULT_LIMITS", json.dumps({"find_callers": 50}))
        res_custom = finder.analyze_code_relationships("find_callers", "target_fn")
        assert len(res_custom["results"]) == 25
        assert res_custom["truncated"] is False
        assert res_custom["result_limit"] == 50
        assert "(truncated" not in res_custom["summary"]
    finally:
        manager.close_driver()


def test_find_callees_truncation(tmp_path):
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        with driver.session() as session:
            session.run(
                "CREATE (:Function {uid: 'caller:app.py:1', name: 'caller_fn', path: 'app.py', "
                "line_number: 1, is_dependency: false})"
            )
            for i in range(30):
                callee_name = f"callee_{i}"
                session.run(
                    "CREATE (:Function {uid: $uid, name: $name, path: 'lib.py', "
                    "line_number: $line, is_dependency: false})",
                    uid=f"{callee_name}:lib.py:{i+10}",
                    name=callee_name,
                    line=i + 10,
                )
                session.run(
                    "MATCH (a:Function {name: 'caller_fn'}), (b:Function {name: $callee}) "
                    "CREATE (a)-[:CALLS {line_number: $line}]->(b)",
                    callee=callee_name,
                    line=i + 10,
                )

        finder = CodeFinder(_KuzuDBAdapter(driver))
        res = finder.analyze_code_relationships("find_callees", "caller_fn")
        assert len(res["results"]) == 20
        assert res["truncated"] is True
        assert res["result_limit"] == 20
        assert "(truncated — more exist)" in res["summary"]
    finally:
        manager.close_driver()


def test_find_importers_truncation(tmp_path):
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        with driver.session() as session:
            session.run("CREATE (:Module {name: 'mod_a', full_import_name: 'mod_a'})")
            for i in range(25):
                file_path = f"src/file_{i}.py"
                session.run(
                    "CREATE (:File {name: $name, path: $path, relative_path: $path, is_dependency: false})",
                    name=f"file_{i}.py",
                    path=file_path,
                )
                session.run(
                    "MATCH (f:File {path: $path}), (m:Module {name: 'mod_a'}) "
                    "CREATE (f)-[:IMPORTS {alias: NULL}]->(m)",
                    path=file_path,
                )

        finder = CodeFinder(_KuzuDBAdapter(driver))
        res = finder.analyze_code_relationships("find_importers", "mod_a")
        assert len(res["results"]) == 20
        assert res["truncated"] is True
        assert res["result_limit"] == 20
        assert "(truncated — more exist)" in res["summary"]
    finally:
        manager.close_driver()


def test_regression_untruncated_results(tmp_path):
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        with driver.session() as session:
            session.run(
                "CREATE (:Function {uid: 'target:lib.py:1', name: 'target_fn', path: 'lib.py', "
                "line_number: 1, is_dependency: false})"
            )
            for i in range(5):
                caller_name = f"caller_{i}"
                session.run(
                    "CREATE (:Function {uid: $uid, name: $name, path: 'app.py', "
                    "line_number: $line, is_dependency: false})",
                    uid=f"{caller_name}:app.py:{i+10}",
                    name=caller_name,
                    line=i + 10,
                )
                session.run(
                    "MATCH (a:Function {name: $caller}), (b:Function {name: 'target_fn'}) "
                    "CREATE (a)-[:CALLS {line_number: $line}]->(b)",
                    caller=caller_name,
                    line=i + 10,
                )

        finder = CodeFinder(_KuzuDBAdapter(driver))
        res = finder.analyze_code_relationships("find_callers", "target_fn")
        assert len(res["results"]) == 5
        assert res["truncated"] is False
        assert res["result_limit"] == 20
        assert "(truncated" not in res["summary"]
    finally:
        manager.close_driver()
