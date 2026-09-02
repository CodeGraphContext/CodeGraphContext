"""#1323: `cgc bundle export --exclude-labels` drops node types AND their edges.

Real-Kùzu roundtrip: a graph with code nodes plus datasource metadata is
exported without DbTable/Datasource; the bundle must carry neither those
nodes nor any dangling edges, must record the exclusion in metadata, and
must import cleanly.
"""
import json
import zipfile
from pathlib import Path

import pytest

from codegraphcontext.core.cgc_bundle import CGCBundle
from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

kuzu = pytest.importorskip("kuzu")


def _bundle_jsonl(bundle_path: Path, member: str):
    with zipfile.ZipFile(bundle_path) as z:
        payload_names = [n for n in z.namelist() if n.endswith(member)]
        assert payload_names, f"{member} not in bundle: {z.namelist()}"
        return [json.loads(l) for l in z.read(payload_names[0]).decode().splitlines() if l.strip()]


def test_exclude_labels_drops_nodes_edges_and_records_metadata(tmp_path: Path):
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        w = GraphWriter(driver)
        repo = tmp_path / "repo"; repo.mkdir()
        f = repo / "a.py"; f.write_text("def q():\n    pass\n", encoding="utf-8")
        w.add_repository_to_graph(repo)
        w.add_file_to_graph({
            "path": str(f), "repo_path": str(repo), "lang": "python", "imports": [],
            "functions": [{"name": "q", "line_number": 1, "end_line": 2, "args": []}],
            "classes": [], "variables": []},
            repo.name, {}, repo_path_str=str(repo.resolve()))
        w.write_datasource_graph({
            "datasource": {"name": "mydb", "kind": "mysql", "host": "h", "env": "dev"},
            "tables": [{"fqn": "mydb.users", "name": "users", "datasource_name": "mydb"}],
            "columns": [{"name": "id", "table_fqn": "mydb.users", "type": "INT",
                         "nullable": False, "datasource_name": "mydb", "is_primary_key": True}],
            "key_patterns": [],
        })

        class _DBM:
            def get_driver(self, graph_name=None): return driver
            def get_backend_type(self): return "kuzudb"

        out = tmp_path / "filtered.cgc"
        ok, msg = CGCBundle(_DBM()).export_to_bundle(
            out, exclude_labels=["DbTable", "DbColumn", "Datasource"]
        )
        assert ok, msg

        nodes = _bundle_jsonl(out, "nodes.jsonl")
        labels = {l for n in nodes for l in n.get("_labels", [])}
        assert "DbTable" not in labels and "DbColumn" not in labels and "Datasource" not in labels
        assert "Function" in labels and "File" in labels

        # No dangling edges: every endpoint id must exist in nodes.jsonl.
        node_ids = {json.dumps(n["_id"], sort_keys=True, default=str) for n in nodes if "_id" in n}
        edges = _bundle_jsonl(out, "edges.jsonl")
        for e in edges:
            for side in ("from", "to"):
                key = json.dumps(e[side], sort_keys=True, default=str)
                assert key in node_ids, f"dangling {side} endpoint: {e}"

        with zipfile.ZipFile(out) as z:
            meta_name = [n for n in z.namelist() if n.endswith("metadata.json")][0]
            meta = json.loads(z.read(meta_name))
        assert meta.get("excluded_labels") == ["Datasource", "DbColumn", "DbTable"]

        # And the filtered bundle imports cleanly into a fresh db.
        m2 = KuzuDBManager(str(tmp_path / "db2"))
        d2 = m2.get_driver()
        try:
            class _DBM2:
                def get_driver(self, graph_name=None): return d2
                def get_backend_type(self): return "kuzudb"
            ok2, msg2 = CGCBundle(_DBM2()).import_from_bundle(out)
            assert ok2, msg2
            with d2.session() as s:
                fn = s.run("MATCH (f:Function) RETURN count(f) AS c").data()[0]["c"]
                dbt = s.run("MATCH (t:DbTable) RETURN count(t) AS c").data()[0]["c"]
            assert fn == 1 and dbt == 0
        finally:
            m2.close_driver()
    finally:
        manager.close_driver()


def test_export_without_exclusions_is_unchanged(tmp_path: Path):
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        w = GraphWriter(driver)
        repo = tmp_path / "repo"; repo.mkdir()
        (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
        w.add_repository_to_graph(repo)

        class _DBM:
            def get_driver(self, graph_name=None): return driver
            def get_backend_type(self): return "kuzudb"

        out = tmp_path / "full.cgc"
        ok, msg = CGCBundle(_DBM()).export_to_bundle(out)
        assert ok, msg
        with zipfile.ZipFile(out) as z:
            meta = json.loads(z.read([n for n in z.namelist() if n.endswith("metadata.json")][0]))
        assert "excluded_labels" not in meta
    finally:
        manager.close_driver()
