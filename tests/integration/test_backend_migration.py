"""Native engines stay in subprocesses, including test setup and verification."""

import importlib.util
import json
import os
import subprocess
import sys
import zipfile

import pytest

from codegraphcontext.core.backend_migration import DatabaseLocation, MigrationError, migrate_graph


pytestmark = pytest.mark.integration


def _database_script(backend, path, code):
    env = os.environ.copy()
    env["CGC_RUNTIME_DB_TYPE"] = backend
    env["CGC_EMBEDDED_BUFFER_POOL_MB"] = "64"
    script = "\n".join([
        "from codegraphcontext.core import get_database_manager",
        "import json",
        f"manager = get_database_manager(db_path={str(path)!r})",
        "try:",
        "    with manager.get_driver().session() as session:",
        *["        " + line for line in code.splitlines()],
        "finally:",
        "    manager.close_driver()",
    ])
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout


def _seed(backend, path):
    _database_script(backend, path, "\n".join([
        "session.run(\"MERGE (r:Repository {path: '/migration/project'}) SET r.name = 'project'\")",
        "session.run(\"MERGE (f:File {path: '/migration/project/main.py'}) SET f.name = 'main.py'\")",
        "session.run(\"MATCH (r:Repository), (f:File) MERGE (r)-[:CONTAINS]->(f)\")",
        "session.run(\"MERGE (f:Function {uid: 'caller'}) "
        "SET f.name = 'caller', f.path = '/migration/project/main.py', f.line_number = 1\")",
        "session.run(\"MERGE (f:Function {uid: 'callee'}) "
        "SET f.name = 'callee', f.path = '/migration/project/main.py', f.line_number = 5\")",
        "session.run(\"MATCH (a:Function {name: 'caller'}), (b:Function {name: 'callee'}) "
        "MERGE (a)-[r:CALLS]->(b) SET r.line_number = 3\")",
    ]))


def _snapshot(backend, path):
    output = _database_script(backend, path, "\n".join([
        "nodes = session.run('MATCH (n) RETURN count(n) AS count').single()['count']",
        "edges = session.run('MATCH ()-[r]->() RETURN count(r) AS count').single()['count']",
        "calls = session.run('MATCH (a:Function)-[r:CALLS]->(b:Function) "
        "RETURN a.name AS caller, b.name AS callee, r.line_number AS line').data()",
        "repos = session.run('MATCH (r:Repository) RETURN r.path AS path, r.name AS name').data()",
        "print('SNAPSHOT:' + json.dumps({'nodes': nodes, 'edges': edges, 'calls': calls, 'repos': repos}))",
    ]))
    snapshot = next(line for line in output.splitlines() if line.startswith("SNAPSHOT:"))
    return json.loads(snapshot.removeprefix("SNAPSHOT:"))


@pytest.mark.parametrize("source_backend,target_backend", [
    ("kuzudb", "ladybugdb"),
    ("ladybugdb", "kuzudb"),
    ("falkordb", "ladybugdb"),
    ("ladybugdb", "falkordb"),
])
def test_migrates_graph_both_directions_without_loading_natives_in_parent(
    tmp_path, monkeypatch, source_backend, target_backend
):
    drivers = {"kuzudb": "kuzu", "ladybugdb": "ladybug", "falkordb": "redislite"}
    for driver in {drivers[source_backend], drivers[target_backend]}:
        if importlib.util.find_spec(driver) is None:
            pytest.skip(f"{driver} is not installed")
    monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "64")
    source, target = tmp_path / "source", tmp_path / "target"
    _seed(source_backend, source)
    before = _snapshot(source_backend, source)
    assert before["nodes"] == 4
    assert before["edges"] == 2
    checkpoint = tmp_path / "graph.cgc"
    natives_before = {driver for driver in ("kuzu", "ladybug") if driver in sys.modules}

    migrate_graph(DatabaseLocation(source_backend, source), DatabaseLocation(target_backend, target), checkpoint)

    assert _snapshot(target_backend, target) == before
    assert _snapshot(source_backend, source) == before
    with zipfile.ZipFile(checkpoint) as bundle:
        assert len(bundle.read("nodes.jsonl").splitlines()) == 4
        assert len(bundle.read("edges.jsonl").splitlines()) == 2
    assert {driver for driver in ("kuzu", "ladybug") if driver in sys.modules} == natives_before


def test_populated_target_is_unchanged_and_export_remains_available(tmp_path, monkeypatch):
    if importlib.util.find_spec("ladybug") is None:
        pytest.skip("ladybug is not installed")
    monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "64")
    source, target = tmp_path / "source", tmp_path / "target"
    _seed("ladybugdb", source)
    _seed("ladybugdb", target)
    before = _snapshot("ladybugdb", target)
    checkpoint = tmp_path / "graph.cgc"
    with pytest.raises(MigrationError, match="not confirmed empty"):
        migrate_graph(DatabaseLocation("ladybugdb", source), DatabaseLocation("ladybugdb", target), checkpoint)
    assert checkpoint.exists()
    assert _snapshot("ladybugdb", target) == before
