"""Upgrade real legacy stores without losing relationship data (#1862)."""

import importlib.util
import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.database_embedded_kuzu import EmbeddedGraphManager


NATIVE_UPGRADE = r"""
import importlib
import sys
from types import SimpleNamespace

backend, path = sys.argv[1:]
if backend == "kuzu":
    from codegraphcontext.core.database_kuzu import KuzuDBManager as Manager
else:
    from codegraphcontext.core import ladybugdb_unavailable_reason
    if reason := ladybugdb_unavailable_reason():
        print(reason)
        raise SystemExit(77)
    from codegraphcontext.core.database_ladybug import LadybugDBManager as Manager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

native = importlib.import_module(backend)
manager = Manager(path)
manager.get_driver()
manager.close_driver()

# Retain the node schema but simulate old relationship definitions: only one
# binding and none of the recently introduced confidence/identity properties.
db = native.Database(path, buffer_pool_size=256 * 1024**2)
conn = native.Connection(db)
legacy = {
    "CALLS": "FROM Function TO Function, line_number INT64, args STRING[], full_call_name STRING",
    "HEURISTIC_CALLS": "FROM Function TO Function, line_number INT64, args STRING[], full_call_name STRING",
    "INHERITS": "FROM Class TO Class",
    "IMPLEMENTS": "FROM Class TO Interface",
    "CONTAINS": "FROM File TO Function",
    "DECORATED_BY": "FROM Function TO Function, line_number INT64",
}
for table, schema in legacy.items():
    conn.execute(f"DROP TABLE {table}")
    conn.execute(f"CREATE REL TABLE GROUP {table}({schema})")
for uid, name, line in [("caller", "caller", 1), ("callee", "callee", 2)]:
    conn.execute("CREATE (:Function {uid: $uid, name: $name, path: '/repo/a.py', line_number: $line})",
                 {"uid": uid, "name": name, "line": line})
conn.execute("CREATE (:File {path: '/repo/a.py', name: 'a.py'})")
conn.execute("CREATE (:Object {uid: 'obj', name: 'Factory', path: '/repo/a.py', line_number: 3})")
conn.execute("CREATE (:Enum {uid: 'enum', name: 'Colour'})")
conn.execute("CREATE (:EnumMember {uid: 'member', name: 'RED'})")
conn.execute("MATCH (a:Function {uid: 'caller'}), (b:Function {uid: 'callee'}) "
             "CREATE (a)-[:CALLS {line_number: 7, args: ['old'], full_call_name: 'callee'}]->(b)")
conn.execute("MATCH (f:File), (a:Function {uid: 'caller'}) CREATE (f)-[:CONTAINS]->(a)")
conn.close()
db.close()

def rows(session, query):
    return session.run(query).data()

for reopening in range(2):
    # Opening a second time must be idempotent and retain all existing data.
    driver = manager.get_driver()
    with driver.session() as session:
        for table in ("CALLS", "HEURISTIC_CALLS"):
            cols = {r["name"] for r in rows(session, f"CALL TABLE_INFO('{table}') RETURN *")}
            assert {"args_key", "confidence", "resolution_tier", "confidence_label",
                    "source", "resolution_method", "called_name"} <= cols, (table, cols)
        for table in ("INHERITS", "IMPLEMENTS"):
            assert "confidence_label" in {r["name"] for r in rows(session, f"CALL TABLE_INFO('{table}') RETURN *")}
        for table, binding in [("CALLS", ("File", "Object")),
                               ("HEURISTIC_CALLS", ("File", "Object")),
                               ("CONTAINS", ("Enum", "EnumMember")),
                               ("DECORATED_BY", ("Class", "Function")),
                               ("IMPLEMENTS", ("Object", "Interface"))]:
            pairs = {(r["source table name"], r["destination table name"])
                     for r in rows(session, f"CALL SHOW_CONNECTION('{table}') RETURN *")}
            assert binding in pairs, (table, binding, pairs)
        assert rows(session, "MATCH (:Function)-[r:CALLS]->(:Function) WHERE r.line_number = 7 RETURN r.args AS args") == [{"args": ["old"]}]
        assert rows(session, "MATCH (:File)-[:CONTAINS]->(:Function) RETURN count(*) AS n") == [{"n": 1}]

    adapter = SimpleNamespace(get_backend_type=manager.get_backend_type)
    writer = GraphWriter(driver, adapter)
    call = {"caller_name": "caller", "caller_file_path": "/repo/a.py", "caller_line_number": 1,
            "called_name": "callee", "called_file_path": "/repo/a.py", "called_line_number": 2,
            "line_number": 10, "full_call_name": "callee", "args": ["new"], "resolution_tier": 1}
    writer.write_function_call_groups(fn_to_fn=[call])
    writer.write_function_call_groups(fn_to_fn=[dict(call, line_number=11, resolution_tier=8)])
    object_call = dict(call, called_name="Factory", called_line_number=3, line_number=12, full_call_name="Factory")
    writer.write_function_call_groups(file_to_object=[object_call])
    writer.write_function_call_groups(file_to_object=[dict(object_call, resolution_tier=8, line_number=13)])
    with driver.session() as session:
        for table in ("CALLS", "HEURISTIC_CALLS"):
            assert rows(session, f"MATCH (:Function)-[r:{table}]->(:Function) WHERE r.args_key = '[\"new\"]' RETURN count(*) AS n") == [{"n": 1}], table
            assert rows(session, f"MATCH (:File)-[:{table}]->(:Object) RETURN count(*) AS n") == [{"n": 1}], table
        session.run("MATCH (e:Enum), (m:EnumMember) MERGE (e)-[:CONTAINS]->(m)")
        assert rows(session, "MATCH (:Enum)-[:CONTAINS]->(:EnumMember) RETURN count(*) AS n") == [{"n": 1}]
    manager.close_driver()

# An incompatible schema must also be rejected on a repeated open attempt,
# without retaining native connections or a database lock. After repairing
# the migration failure, the same manager must successfully reopen the data.
original_migrate = manager._migrate_relationship_schemas
def fail_migration(*args):
    raise RuntimeError("injected relationship migration failure")
manager._migrate_relationship_schemas = fail_migration
for attempt in range(2):
    try:
        manager.get_driver()
    except RuntimeError as exc:
        assert "injected relationship migration failure" in str(exc)
    else:
        raise AssertionError("returned a driver after a failed migration")
    assert manager._db is None and manager._pool is None and manager._conn is None
manager._migrate_relationship_schemas = original_migrate
with manager.get_driver().session() as session:
    assert rows(session, "MATCH (:Function)-[r:CALLS]->(:Function) WHERE r.line_number = 7 RETURN r.args AS args") == [{"args": ["old"]}]
manager.close_driver()
print("legacy relationship upgrade preserves data and writer edges across reopen")
"""


@pytest.mark.parametrize("backend", ["kuzu", "ladybug"])
def test_legacy_relationship_upgrade_on_native_backend(backend, tmp_path):
    # These native extensions export colliding symbols. Never load both in the
    # pytest interpreter, and use the selected checkout in the child process.
    if importlib.util.find_spec(backend) is None:
        pytest.skip(f"{backend} is not installed")
    env = os.environ.copy()
    env["CGC_EMBEDDED_BUFFER_POOL_MB"] = "256"
    result = subprocess.run(
        [sys.executable, "-c", NATIVE_UPGRADE, backend, str(tmp_path / "db")],
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
    )
    if result.returncode == 77:
        pytest.skip(result.stdout.strip())
    assert result.returncode == 0, result.stdout + result.stderr
    assert "preserves data and writer edges" in result.stdout


@pytest.mark.parametrize("failed_query", ["TABLE_INFO", "ADD confidence", "SHOW_CONNECTION", "ADD FROM"])
def test_relationship_migration_failure_is_fatal(failed_query):
    manager = object.__new__(EmbeddedGraphManager)
    manager._conn = MagicMock()

    def execute(query):
        if failed_query in query:
            raise RuntimeError("migration permission denied")
        result = MagicMock()
        result.has_next.return_value = False
        return result

    manager._conn.execute.side_effect = execute
    with pytest.raises(RuntimeError, match=r"Relationship Schema Migration Failed \(CALLS\)"):
        manager._migrate_relationship_schemas([("CALLS", "FROM Function TO Function, confidence DOUBLE", True)])
