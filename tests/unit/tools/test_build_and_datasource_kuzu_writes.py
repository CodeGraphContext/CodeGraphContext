"""The Gradle/Maven build graph and datasource graph must write on KuzuDB.

Regression tests for the embedded-backend gaps behind #1603: none of
GradleModule / MavenModule / ExternalLibrary / DbColumn / RedisKeyPattern
was declared in the Kùzu schema (DbColumn and RedisKeyPattern used composite
PRIMARY KEYs, which Kùzu cannot parse), so every one of these writes either
binder-errored or silently dropped all rows. The UNWIND per-row fallback also
left the bare row variable in `WITH node, row` clauses, which binder-errored
and skipped each row one at a time.
"""
from pathlib import Path

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

kuzu = pytest.importorskip("kuzu")


@pytest.fixture()
def driver(tmp_path: Path):
    manager = KuzuDBManager(str(tmp_path / "db"))
    yield manager.get_driver()
    manager.close_driver()


def _count(session, query: str) -> int:
    return session.run(query).data()[0]["c"]


def test_gradle_build_graph_writes_on_kuzu(driver):
    w = GraphWriter(driver)
    w.write_gradle_build_graph(
        {
            "modules": [
                {"name": ":app", "build_file": "/r/app/build.gradle"},
                {"name": ":core", "build_file": "/r/core/build.gradle"},
            ],
            "inter_module_deps": [
                {"src_name": ":app", "tgt_name": ":core", "configuration": "implementation"}
            ],
            "external_libs": [
                {"group_id": "com.squareup.retrofit2", "artifact_id": "retrofit",
                 "version": "2.9.0", "src_name": ":app", "configuration": "implementation"}
            ],
        },
        "/r",
    )
    with driver.session() as s:
        assert _count(s, "MATCH (n:GradleModule) RETURN count(n) AS c") == 2
        assert _count(s, "MATCH (n:ExternalLibrary) RETURN count(n) AS c") == 1
        assert _count(s, "MATCH (:GradleModule)-[:MODULE_DEPENDS_ON]->(:GradleModule) RETURN count(*) AS c") == 1
        assert _count(s, "MATCH (:GradleModule)-[:USES_LIBRARY]->(:ExternalLibrary) RETURN count(*) AS c") == 1


def test_maven_build_graph_writes_on_kuzu(driver):
    w = GraphWriter(driver)
    w.write_maven_build_graph(
        {
            "modules": [
                {"group_id": "com.acme", "artifact_id": "parent", "version": "1.0",
                 "packaging": "pom", "pom_path": "/r/pom.xml"},
                {"group_id": "com.acme", "artifact_id": "child", "version": "1.0",
                 "packaging": "jar", "pom_path": "/r/child/pom.xml"},
            ],
            "child_relations": [
                {"parent_artifact_id": "parent", "child_artifact_id": "child"}
            ],
            "inter_module_deps": [
                {"src_artifact_id": "child", "tgt_artifact_id": "parent", "scope": "compile"}
            ],
            "external_libs": [
                {"group_id": "junit", "artifact_id": "junit", "version": "4.13",
                 "src_artifact_id": "child", "scope": "test"}
            ],
        },
        "/r",
    )
    with driver.session() as s:
        assert _count(s, "MATCH (n:MavenModule) RETURN count(n) AS c") == 2
        assert _count(s, "MATCH (:MavenModule)-[:CHILD_MODULE]->(:MavenModule) RETURN count(*) AS c") == 1
        assert _count(s, "MATCH (:MavenModule)-[:MODULE_DEPENDS_ON]->(:MavenModule) RETURN count(*) AS c") == 1
        assert _count(s, "MATCH (:MavenModule)-[:USES_LIBRARY]->(:ExternalLibrary) RETURN count(*) AS c") == 1


def test_datasource_graph_writes_on_kuzu(driver):
    w = GraphWriter(driver)
    w.write_datasource_graph(
        {
            "datasource": {"name": "mydb", "kind": "mysql", "host": "localhost", "env": "dev"},
            "tables": [
                {"fqn": "mydb.users", "name": "users", "datasource_name": "mydb"},
                {"fqn": "mydb.orders", "name": "orders", "datasource_name": "mydb"},
            ],
            # Same column name on two tables: must stay two distinct nodes.
            "columns": [
                {"name": "id", "table_fqn": "mydb.users", "type": "INT", "nullable": False,
                 "datasource_name": "mydb", "is_primary_key": True},
                {"name": "id", "table_fqn": "mydb.orders", "type": "INT", "nullable": False,
                 "datasource_name": "mydb", "is_primary_key": True},
            ],
            "key_patterns": [
                {"pattern": "session:*", "datasource_name": "redis1", "key_type": "hash",
                 "example_key": "session:1", "count": 10}
            ],
        }
    )
    with driver.session() as s:
        assert _count(s, "MATCH (n:Datasource) RETURN count(n) AS c") == 1
        assert _count(s, "MATCH (n:DbTable) RETURN count(n) AS c") == 2
        assert _count(s, "MATCH (n:DbColumn) RETURN count(n) AS c") == 2
        assert _count(s, "MATCH (n:RedisKeyPattern) RETURN count(n) AS c") == 1
        assert _count(s, "MATCH (:DbTable)-[:HAS_COLUMN]->(:DbColumn) RETURN count(*) AS c") == 2
        assert _count(s, "MATCH (:DbTable)-[:STORED_IN]->(:Datasource) RETURN count(*) AS c") == 2


def test_datasource_writes_are_idempotent_on_kuzu(driver):
    w = GraphWriter(driver)
    payload = {
        "datasource": {"name": "mydb", "kind": "mysql", "host": "h", "env": "dev"},
        "tables": [{"fqn": "mydb.users", "name": "users", "datasource_name": "mydb"}],
        "columns": [{"name": "id", "table_fqn": "mydb.users", "type": "INT",
                     "nullable": False, "datasource_name": "mydb", "is_primary_key": True}],
        "key_patterns": [],
    }
    w.write_datasource_graph(payload)
    w.write_datasource_graph(payload)
    with driver.session() as s:
        assert _count(s, "MATCH (n:DbTable) RETURN count(n) AS c") == 1
        assert _count(s, "MATCH (n:DbColumn) RETURN count(n) AS c") == 1
