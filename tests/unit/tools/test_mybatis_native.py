"""Native XML → Java interface → table-edge regression for #890."""

import subprocess
import sys

import pytest


NATIVE_SCRIPT = r'''
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

backend = sys.argv[1]
module = "kuzu" if backend == "kuzudb" else "ladybug"
if importlib.util.find_spec(module) is None:
    raise SystemExit(77)
if backend == "ladybugdb":
    from codegraphcontext.core import ladybugdb_unavailable_reason
    reason = ladybugdb_unavailable_reason()
    if reason:
        print(reason)
        raise SystemExit(77)
    from codegraphcontext.core.database_ladybug import LadybugDBManager as Manager
else:
    from codegraphcontext.core.database_kuzu import KuzuDBManager as Manager
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.tools.languages.mybatis import find_and_parse_mybatis_mappers

os.environ["CGC_EMBEDDED_BUFFER_POOL_MB"] = "256"
with tempfile.TemporaryDirectory() as root:
    root = Path(root)
    repo = root / "repo"
    repo.mkdir()
    foreign = root / "foreign"
    foreign.mkdir()
    sources = []
    parser = TreeSitterParser("java")
    for directory, package in ((repo / "a", "a"), (repo / "b", "b"), (foreign / "a", "a")):
        directory.mkdir()
        source = directory / "UserMapper.java"
        source.write_text("package " + package + ";\npublic interface UserMapper {\n"
                          "String find(int id);\nvoid remove(int id);\n}\n")
        data = parser.parse(source)
        assert {f["name"] for f in data["functions"]} == {"find", "remove"}
        # SCIP definitions can omit this field; links must not depend on it.
        for function in data["functions"]:
            function["class_context"] = None
        sources.append(data)
    mapper = repo / "Queries.xml"
    mapper.write_text('<mapper namespace="a.UserMapper">'
                      '<select id="find">SELECT * FROM users</select>'
                      '<delete id="remove">DELETE FROM users</delete></mapper>')
    expected_path = (repo / "a" / "UserMapper.java").as_posix()
    records = find_and_parse_mybatis_mappers(repo, sources)
    assert len(records) == 2 and all(r["method_path"] == expected_path for r in records), records
    manager = Manager(str(root / "db"))
    driver = manager.get_driver()
    try:
        writer = GraphWriter(driver, manager)
        writer.add_repository_to_graph(repo)
        for data in sources:
            writer.add_file_to_graph(data, "repo", {}, repo_path_str=repo.as_posix())
        entity_path = (repo / "Entity.java").as_posix()
        with driver.session() as session:
            session.run("CREATE (:Class {uid: 'entity', name: 'User', path: $path, line_number: 1})",
                        path=entity_path)
            # Backfill a pre-existing table with no datasource; the later
            # annotation-query writer must preserve the resulting postgres value.
            session.run("CREATE (:DbTable {fqn: 'entity_users', name: 'entity_users'})")
        writer.write_orm_mappings([{"kind": "class_table", "class_name": "User",
                                    "class_path": entity_path, "orm_table": "entity_users",
                                    "datastore": "postgres", "line_number": 1}])
        writer.write_query_links([{"kind": "method_query", "method_name": "find",
                                   "method_path": expected_path, "db_tables": ["entity_users"],
                                   "operation": "READS", "line_number": 7}])
        writer.write_mybatis_links(records)
        writer.write_mybatis_links([{"method_name": "find", "class_name": "UserMapper",
                                     "db_tables": ["unresolved"], "operation": "READS"}])
        with driver.session() as session:
            rows = session.run("MATCH (f:Function)-[r:READS|WRITES]->(t:DbTable) "
                               "RETURN f.path AS path, f.name AS name, type(r) AS operation, t.name AS table_name").data()
        actual = {(r["path"], r["name"], r["operation"], r["table_name"]) for r in rows}
        assert actual == {(expected_path, "find", "READS", "users"),
                          (expected_path, "find", "READS", "entity_users"),
                          (expected_path, "remove", "WRITES", "users")}, rows
        with driver.session() as session:
            tables = session.run("MATCH (c:Class)-[:MAPS_TO]->(t:DbTable) "
                                 "RETURN t.fqn AS fqn, t.datasource_name AS datasource").data()
        assert tables == [{"fqn": "entity_users", "datasource": "postgres"}], tables
        print("exact namespace-scoped READS and WRITES edges preserved")
    finally:
        manager.close_driver()
'''


@pytest.mark.parametrize("backend", ["kuzudb", "ladybugdb"])
def test_mybatis_links_on_native_backend(backend):
    result = subprocess.run([sys.executable, "-c", NATIVE_SCRIPT, backend],
                            capture_output=True, text=True, timeout=90)
    if result.returncode == 77:
        pytest.skip(result.stdout.strip() or f"{backend} is unavailable")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "namespace-scoped" in result.stdout
