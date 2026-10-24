"""Read paths open sessions only through ``read_driver``.

A per-tool time ceiling (core/read_timeout.py) only bounds the queries that go
through it. Read paths used to bypass ``CodeFinder.driver``
(report_generator, get_repository_stats, the simulator), so this is static
and covers **all of src/** by default:

* any reference to ``get_driver`` — a call, a bound method stored for later
  (``drv = m.get_driver``), or ``getattr(m, "get_driver")`` — must sit in a
  reviewed entry of ``DIRECT_GET_DRIVER``: write and index paths (which must
  never be time-limited mid-write), connection probes that open no read
  session, the database managers themselves, and ``read_driver``;
* a new module, or a new function in a listed module, is covered without
  editing this file;
* CodeFinder and the read modules never write: no write clause in any Cypher
  string (the timeout proxy is only safe because reads are all it
  wraps).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import codegraphcontext

SRC = Path(codegraphcontext.__file__).resolve().parent

#: Whole modules allowed to call get_driver directly, and why (paths under src/codegraphcontext).
DIRECT_MODULES = {
    "core/read_timeout.py": "read_driver itself",
    "core/cgc_bundle.py": "bundle export/import: a full-graph dump and a write path, not a tool read",
    "core/database_falkordb.py": "the manager's own list_graphs",
    "core/database_falkordb_remote.py": "the manager's own list_graphs",
    "core/__init__.py": "manager factory: connection probes, no session",
    "tools/graph_builder.py": "the indexing pipeline's writer driver",
}

#: (module, function) -> why a direct get_driver there is not a tool read.
DIRECT_GET_DRIVER = {
    ("server.py", "__init__"): "connection probe at startup; opens no session",
    ("server.py", "switch_context_tool"): "connection probe of the new context; opens no session",
    ("cli/cli_helpers.py", "_initialize_services"): "connection probes; open no session",
    ("cli/cli_helpers.py", "index_helper"): "the index command (decides whether to re-index, then writes)",
    ("cli/cli_helpers.py", "clean_helper"): "deletes orphaned nodes (a write)",
    ("cli/main.py", "doctor"): "connection probe of each configured backend",
    ("cli/main.py", "_write_datasource_graph"): "writes datasource nodes (a write)",
}


def _is_dynamic_getattr_on_db(node) -> bool:
    """``getattr(<a db manager or driver>, <computed name>)``: could fetch get_driver/_driver unseen."""
    if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "getattr" and len(node.args) >= 2):
        return False
    if isinstance(node.args[1], ast.Constant):
        return False
    target = ast.unparse(node.args[0]).lower()
    return "manager" in target or "driver" in target


def _get_driver_refs(tree):
    """(node, enclosing function) for every way to reach a raw driver without read_driver.

    * ``get_driver`` as an attribute (a call or a stored bound method) or a
      getattr string;
    * ``._driver`` on anything but ``self`` (a manager's private driver,
      e.g. ``db_manager._driver.session()``);
    * ``getattr`` with a computed name on a db manager or driver.
    """
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    for node in ast.walk(tree):
        hit = isinstance(node, ast.Attribute) and node.attr == "get_driver"
        hit = hit or (isinstance(node, ast.Constant) and node.value in ("get_driver", "_driver")
                      and isinstance(parents.get(node), ast.Call))
        hit = hit or (isinstance(node, ast.Attribute) and node.attr == "_driver"
                      and not (isinstance(node.value, ast.Name) and node.value.id == "self"))
        hit = hit or _is_dynamic_getattr_on_db(node)
        if not hit:
            continue
        cur = parents.get(node)
        while cur is not None and not isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cur = parents.get(cur)
        yield node, (cur.name if cur is not None else "<module>")


def _modules():
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def test_reads_get_sessions_only_through_read_driver():
    offenders, seen = [], set()
    for path in _modules():
        rel = path.relative_to(SRC).as_posix()
        if rel in DIRECT_MODULES or (rel.startswith("core/database") and rel.endswith(".py")):
            continue  # database managers define and use their own drivers
        for node, fn in _get_driver_refs(ast.parse(path.read_text(encoding="utf-8"))):
            seen.add((rel, fn))
            if (rel, fn) not in DIRECT_GET_DRIVER:
                offenders.append(f"{rel}:{node.lineno} in {fn}()")
    assert not offenders, (
        "read paths must use core.read_timeout.read_driver(db_manager, graph_name) (or CodeFinder.driver) "
        "so the tool's time ceiling applies; a write/probe path needs a DIRECT_GET_DRIVER entry: "
        + ", ".join(offenders))
    assert set(DIRECT_GET_DRIVER) <= seen, f"stale DIRECT_GET_DRIVER entries: {set(DIRECT_GET_DRIVER) - seen}"
    assert all((SRC / m).exists() for m in DIRECT_MODULES), "stale DIRECT_MODULES entry"


def test_codefinder_driver_property_is_read_driver():
    src = (SRC / "tools" / "code_finder.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    prop = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "driver")
    body = ast.unparse(prop)
    assert "read_driver(self.db_manager, self._active_graph)" in body, body


def test_the_scanner_sees_every_spelling():
    src = (
        "def a(m):\n    with m.get_driver().session() as s:\n        s.run('RETURN 1')\n"
        "def b(m):\n    drv = m.get_driver\n    drv().session()\n"
        "def c(m):\n    getattr(m, 'get_driver')().session()\n"
        "def d(m):\n    return read_driver(m)\n"
        "def e(db_manager):\n    return db_manager._driver.session()\n"
        "def f(db_manager, name):\n    return getattr(db_manager, name)().session()\n"
        "def g(self):\n    return self._driver.session()\n"
        "def h(obj, name):\n    return getattr(obj, name)\n"
    )
    assert sorted(fn for _, fn in _get_driver_refs(ast.parse(src))) == ["a", "b", "c", "e", "f"]


# ── no writes from the read side ─────────────────────────────────────────────

_CYPHER = re.compile(r"\b(MATCH|RETURN)\b")
_WRITE = re.compile(r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|FOREACH|LOAD\s+CSV)\b", re.IGNORECASE)


def _string_text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    return None


def _cypher_strings(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def in_log_call(node):
        cur = parents.get(node)
        while cur is not None and not isinstance(cur, ast.stmt):
            if isinstance(cur, ast.Call):
                f = cur.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in _LOG_CALLS:
                    return True
            cur = parents.get(cur)
        return False

    for node in ast.walk(tree):
        text = _string_text(node)
        if text and id(node) not in docstrings and _CYPHER.search(text) and not in_log_call(node):
            yield node.lineno, text


#: Messages (which may quote a maintenance query for the user) are not queries.
_LOG_CALLS = {"debug", "info", "warning", "warn", "error", "exception", "critical",
              "debug_log", "info_logger", "warning_logger", "error_logger"}


def test_read_modules_send_no_write_clauses():
    modules = [SRC / "tools" / "code_finder.py", SRC / "tools" / "report_generator.py"] + sorted(
        (SRC / "tools" / "handlers").glob("*.py"))
    found = []
    for path in modules:
        if path.name == "indexing_handlers.py":
            continue  # starts indexing jobs; its graph writes happen in the pipeline
        for line, text in _cypher_strings(path):
            m = _WRITE.search(text)
            if m:
                found.append(f"{path.name}:{line}: {m.group(0)!r} in {' '.join(text.split())[:120]}")
    assert not found, "read-side Cypher must never write (the timeout proxy wraps reads only): " + "; ".join(found)
