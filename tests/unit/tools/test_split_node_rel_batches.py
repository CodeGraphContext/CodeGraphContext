"""Parameter / HAS_PARAMETER, Module / IMPORTS and ExternalClass / INHERITS are written as a node-only UNWIND followed
by a relationship-only UNWIND on Kuzu, so its forced per-row fallback (Kuzu #1605) never fires.
Ladybug retains the established combined/per-row path until its split batches preserve exact parity. The graph must be what the combined per-row query wrote: nodes only where
the old MATCH succeeded, first non-null Module metadata, the last row's values for a repeated IMPORTS key, and the
label-less external fan-out over every populated child label.
"""
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import codegraphcontext.core.database_embedded_kuzu as embedded
from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.core.database_ladybug import LadybugDBManager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

REPO = Path("C:/fx3").resolve().as_posix()
A = f"{REPO}/src/a.rs"
GUARD = re.compile(r"UNWIND\s+\$\w+\s+AS\s+\w+")


@pytest.fixture()
def env(tmp_path: Path, monkeypatch):
    # The two native engines must run in separate interpreters: importing
    # both extension libraries can collide on their C++ symbols.
    backend = os.environ.get("CGC_SPLIT_TEST_BACKEND", "kuzudb")
    pytest.importorskip("ladybug" if backend == "ladybugdb" else "kuzu")
    if backend == "ladybugdb":
        from codegraphcontext.core import ladybugdb_unavailable_reason
        reason = ladybugdb_unavailable_reason()
        if reason:
            pytest.skip(reason)
    forced = []
    original = embedded.EmbeddedSessionWrapper.run

    def run(self, q, **p):
        if GUARD.search(q) and ("-[" in q or "]->" in q) and re.search(r"MERGE\s*\(\s*\w+\s*:", q):
            forced.append(q)
        return original(self, q, **p)

    monkeypatch.setattr(embedded.EmbeddedSessionWrapper, "run", run)
    manager_class = LadybugDBManager if backend == "ladybugdb" else KuzuDBManager
    manager = manager_class(str(tmp_path / "db"))
    driver = manager.get_driver()
    writer = GraphWriter(driver, SimpleNamespace(get_backend_type=lambda: backend))
    writer.add_repository_to_graph(Path(REPO))
    yield writer, driver, forced, backend
    manager.close_driver()


def _q(driver, cypher):
    with driver.session() as s:
        return s.run(cypher).data()


def _imp(name, full, line, imported, alias=None, lang="rust"):
    return {"name": name, "full_import_name": full, "line_number": line, "imported_name": imported, "alias": alias, "lang": lang}


def _fn(name, line, args):
    return {"name": name, "line_number": line, "end_line": line + 5, "args": args, "lang": "rust"}


def test_parameters_follow_occurrence_identity(env):
    writer, driver, forced, backend = env
    writer.add_file_to_graph({"path": A, "repo_path": REPO, "lang": "rust",
                              "functions": [_fn("f", 10, ["a", "b"]), _fn("f", 10, ["a", "c"]), _fn("g", 20, ["a", "a"])]}, "fx", {})
    edges = sorted((r["o"], r["p"], r["l"]) for r in _q(driver, "MATCH (f:Function)-[:HAS_PARAMETER]->(p:Parameter) "
                                                         "RETURN f.occurrence_index AS o, p.name AS p, p.function_line_number AS l"))
    assert edges == [(0, "a", 10), (0, "a", 20), (0, "b", 10), (1, "a", 10), (1, "c", 10)]
    assert len(_q(driver, "MATCH (p:Parameter) RETURN p.uid")) == 4        # (a,10) shared by both occurrences
    assert bool(forced) == (backend == "ladybugdb")


def test_imports_metadata_and_repeated_keys(env):
    writer, driver, forced, backend = env
    writer.add_file_to_graph({"path": A, "repo_path": REPO, "lang": "rust", "imports": [
        _imp("M1", "use M1::Baz;", 4, "Baz"), _imp("M1", "use super::*;", 1, "*"), _imp("M1", "pub use M1::Bar;", 2, "Bar", "B"),
        _imp("M1", "pub use M1::*;", 5, "*"), _imp("M1", "use M1::Bar;", 2, "Bar", "B2"),
        _imp("M4", "import M4", 1, "M4", lang=None), _imp("M4", "import M4", 2, "M4b")]}, "fx", {})
    mods = {r["n"]: (r["l"], r["f"]) for r in _q(driver, "MATCH (m:Module) RETURN m.name AS n, m.lang AS l, m.full_import_name AS f")}
    assert mods == {"M1": ("rust", "use super::*;"), "M4": ("rust", "import M4")}
    bar = _q(driver, "MATCH (:File)-[r:IMPORTS {line_number: 2, imported_name: 'Bar'}]->(:Module) RETURN r.alias AS a, r.full_import_name AS f")
    assert bar == [{"a": "B2", "f": "use M1::Bar;"}]                      # last sorted row, as row-by-row SETs leave it
    assert len(_q(driver, "MATCH (:File)-[r:IMPORTS]->(:Module) RETURN r.line_number")) == 6
    assert bool(forced) == (backend == "ladybugdb")


def test_external_parents_only_for_existing_children(env):
    writer, driver, forced, backend = env
    writer.add_file_to_graph({"path": A, "repo_path": REPO, "lang": "rust",
                              "classes": [{"name": "K", "line_number": 1, "end_line": 2, "lang": "rust"},
                                          {"name": "Status", "line_number": 3, "end_line": 4, "lang": "rust"}],
                              "variables": [{"name": "Status", "line_number": 5, "lang": "rust"}]}, "fx", {})
    x = "__external__"
    writer.write_inheritance_links([
        {"child_name": "K", "path": A, "parent_name": "Base", "resolved_parent_file_path": x, "child_label": "Class"},
        {"child_name": "Status", "path": A, "parent_name": "Legacy", "resolved_parent_file_path": x},
        {"child_name": "Ghost", "path": A, "parent_name": "Nowhere", "resolved_parent_file_path": x, "child_label": "Class"},
    ], [], {})
    assert sorted(r["n"] for r in _q(driver, "MATCH (e:ExternalClass) RETURN e.name AS n")) == ["Base", "Legacy"]
    rels = sorted((r["lab"], r["c"], r["p"], r["k"]) for r in _q(driver, "MATCH (c)-[r:INHERITS]->(p:ExternalClass) "
                                                                  "RETURN label(c) AS lab, c.name AS c, p.name AS p, r.confidence_label AS k"))
    assert rels == [("Class", "K", "Base", "INFERRED"), ("Class", "Status", "Legacy", "INFERRED"),
                    ("Variable", "Status", "Legacy", "INFERRED")]
    assert bool(forced) == (backend == "ladybugdb")
