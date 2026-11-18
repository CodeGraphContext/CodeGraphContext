"""The IMPORTS write contract: keys, properties, and one row per imported name.

* Every IMPORTS ``MERGE`` in src/ is keyed on exactly
  ``schema_contract.IMPORTS_MERGE_KEYS`` (``line_number``, ``imported_name``).
  The JS/TS write was keyed on the line alone, so ``import { a, b } from './x'``
  kept only ``b`` (about 42% of JS/TS imported names lost on a real web app).
* The properties the writer sets are all in ``IMPORTS_PROPERTIES`` — the
  importer's own data. Nothing derived from another file (a resolved path, a
  canonical module name) may be stored: it goes stale when that file changes
  and the importer is not re-indexed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from codegraphcontext.tools.indexing import schema_contract as sc
from codegraphcontext.tools.indexing.persistence import writer as W

SRC = Path(W.__file__).resolve().parents[3]          # src/codegraphcontext

_IMPORTS_MERGE = re.compile(r"MERGE\s*\([^()]*\)\s*-\s*\[\s*\w*\s*:\s*`?IMPORTS`?\s*(\{[^}]*\})?\s*\]")
_ANY_IMPORTS_WRITE = re.compile(r"(MERGE|CREATE)[^;\"']*?:\s*`?IMPORTS\b")


def _strings(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value
        elif isinstance(node, ast.JoinedStr):
            yield node.lineno, "".join(v.value if isinstance(v, ast.Constant) else "{expr}" for v in node.values)


def _imports_merges():
    for path in sorted(SRC.rglob("*.py")):
        for line, text in _strings(path):
            for m in _IMPORTS_MERGE.finditer(text):
                yield path.relative_to(SRC).as_posix(), line, m.group(1)


def test_every_imports_merge_uses_the_contract_keys():
    found = list(_imports_merges())
    assert found, "no IMPORTS MERGE found: the scan is broken"
    bad = []
    for rel, line, keys in found:
        names = tuple(k.split(":")[0].strip() for k in (keys or "{}").strip("{}").split(",") if k.strip())
        if sorted(names) != sorted(sc.IMPORTS_MERGE_KEYS):
            bad.append(f"{rel}:{line} keyed on {names or '(nothing)'}")
    assert not bad, f"IMPORTS MERGE must be keyed on {sc.IMPORTS_MERGE_KEYS}: {bad}"


def _clause(query: str, start: str) -> str:
    """The MERGE … SET block of *query* that begins with *start* (up to the next MERGE)."""
    body = query[query.index(start):]
    nxt = body.find("MERGE", len(start))
    return " ".join((body if nxt < 0 else body[:nxt]).split())


def test_the_writer_has_one_imports_write():
    """One IMPORTS write, in #1748's two shapes: the relationship-only batch
    (``IMPORTS_EDGE_QUERY``, after ``IMPORTS_MODULE_QUERY``) and the combined per-row
    fallback (``IMPORTS_MERGE_QUERY``). Both must write the same edge and the same
    Module values, so the clauses are compared verbatim."""
    writes = [(p, line) for p, line, _ in _imports_merges() if p.endswith("persistence/writer.py")]
    assert len(writes) == 2, writes
    edge = "MERGE (f)-[r:IMPORTS {line_number: row.line_number, imported_name: row.imported_name}]->(m)"
    module = "MERGE (m:Module {name: row.name})"
    assert edge in W.IMPORTS_MERGE_QUERY and edge in W.IMPORTS_EDGE_QUERY
    assert _clause(W.IMPORTS_EDGE_QUERY, edge) == _clause(W.IMPORTS_MERGE_QUERY, edge)
    assert _clause(W.IMPORTS_MODULE_QUERY, module) == _clause(W.IMPORTS_MERGE_QUERY, module)
    assert "MERGE" not in W.IMPORTS_EDGE_QUERY.split(edge)[0], "the edge phase must not create Modules"
    assert "IMPORTS" not in W.IMPORTS_MODULE_QUERY


def test_the_writer_sets_only_registered_properties():
    set_props = set(re.findall(r"\br\.(\w+)\s*=", W.IMPORTS_MERGE_QUERY))
    key_props = set(re.findall(r"(\w+):\s*row\.", W.IMPORTS_MERGE_QUERY.split("IMPORTS", 1)[1].split("]")[0]))
    assert set(sc.IMPORTS_MERGE_KEYS) == key_props
    assert set_props | key_props <= sc.IMPORTS_PROPERTIES, sorted((set_props | key_props) - sc.IMPORTS_PROPERTIES)
    # nothing that names another file: no resolved path, no target, no canonical module
    for forbidden in ("resolved", "target", "canonical", "path"):
        assert not any(forbidden in p for p in sc.IMPORTS_PROPERTIES), forbidden


# ── build_import_rows ─────────────────────────────────────────────────────────

ROW_KEYS = {"name", "imported_name", "alias", "line_number", "lang", "module_lang", "full_import_name"}


def test_js_names_on_one_line_are_one_row_each():
    rows = W.build_import_rows([
        {"name": "a", "imported_name": "a", "source": "./x", "alias": None, "line_number": 1,
         "lang": "typescript"},
        {"name": "b", "imported_name": "b", "source": "./x", "alias": "c", "line_number": 1,
         "lang": "typescript"},
    ], "typescript")
    assert [(r["name"], r["imported_name"], r["alias"]) for r in rows] == [("./x", "a", ""), ("./x", "b", "c")]
    assert all(set(r) == ROW_KEYS for r in rows)
    assert all(r["module_lang"] is None and r["full_import_name"] is None for r in rows)


@pytest.mark.parametrize("file_lang", ["vue", "svelte"])
def test_sfc_imports_route_on_the_record_language(file_lang):
    """A Vue/Svelte file's lang is "vue"/"svelte"; its script imports were written by the
    non-JS branch, so the Module was the imported NAME ("default", "ref"), not the specifier."""
    rows = W.build_import_rows([
        {"name": "default", "source": "../utils", "alias": "fmt", "line_number": 7,
         "lang": "typescript"},
        {"name": "ref", "source": "vue", "alias": None, "line_number": 6, "lang": "javascript"},
    ], file_lang)
    assert sorted((r["name"], r["imported_name"]) for r in rows) == [("../utils", "default"), ("vue", "ref")]


def test_other_languages_keep_their_mapping():
    rows = W.build_import_rows([
        {"name": "proxy_service", "source": "app.services", "imported_name": "proxy_service",
         "full_import_name": "app.services.proxy_service", "alias": None, "line_number": 2, "lang": "python"},
        {"name": "os", "full_import_name": "os", "alias": "o", "line_number": 1, "lang": "python"},
        {"name": "fmt", "source": "fmt", "line_number": 3, "lang": "go"},
    ], "python")
    by = {r["name"]: r for r in rows}
    assert (by["app.services"]["imported_name"], by["app.services"]["full_import_name"],
            by["app.services"]["module_lang"]) == ("proxy_service", "app.services.proxy_service", "python")
    assert (by["os"]["imported_name"], by["os"]["alias"]) == ("os", "o")
    assert by["fmt"]["imported_name"] == "fmt" and by["fmt"]["lang"] == "go"
    assert all(set(r) == ROW_KEYS for r in rows)
