"""Calls inside a call's callee expression get their own records (Python).

``load_config(path).get(k)`` is a call of ``get`` whose callee expression holds the
call ``load_config(path)``. The Python call walk visited a call's arguments but
never its callee expression, so a call whose result is the receiver of a method
call (``f(x).m()``, ``(await run(job)).get()``, ``f(a)(b)``, ``d[k()](v)``) had no
record and no CALLS edge: a function called only that way had no callers and was
reported as dead code. Every other parser records such calls.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

REPO = Path(__file__).resolve().parents[3]
_PARSERS: Dict[str, TreeSitterParser] = {}


def _parse(tmp_path: Path, lang: str, name: str, text: str) -> dict:
    if lang not in _PARSERS:
        _PARSERS[lang] = TreeSitterParser(lang)
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return _PARSERS[lang].parse(f, False)


def _calls(result: dict) -> List[Tuple[int, str, Optional[str]]]:
    """(line, name, context name) of every call record, in record order."""
    return [(c["line_number"], c["name"], (c.get("context") or (None,))[0]) for c in result["function_calls"]]


# ── Python: the shapes ───────────────────────────────────────────────────────

def test_python_call_that_is_the_receiver_of_a_method_chain(tmp_path):
    r = _parse(tmp_path, "python", "a.py",
               "def settings(path):\n"
               "    return config.load_config(path).get('level', 'info').lower()\n")
    assert _calls(r) == [(2, "lower", "settings"), (2, "get", "settings"), (2, "load_config", "settings")]
    load = next(c for c in r["function_calls"] if c["name"] == "load_config")
    assert load["full_name"] == "config.load_config" and load["args"] == ["path"]


def test_python_chained_call_inside_an_argument(tmp_path):
    r = _parse(tmp_path, "python", "a.py",
               "def workers(path):\n"
               "    return parse_int(load_config(path).get('workers'))\n")
    assert [c[1] for c in _calls(r)] == ["parse_int", "get", "load_config"]


def test_python_awaited_call_in_parentheses(tmp_path):
    r = _parse(tmp_path, "python", "a.py",
               "async def deployed(folder):\n"
               "    return (await run_job(load_config, folder)).get('workers')\n")
    assert _calls(r) == [(2, "get", "deployed"), (2, "run_job", "deployed")]


@pytest.mark.parametrize("expr, names", [
    ("open_secret(p).read_text().strip()", ["strip", "read_text", "open_secret"]),
    ("open_secret(p).unlink()", ["unlink", "open_secret"]),
    ("render(p).encode('utf-8')", ["encode", "render"]),
    ("factory(p)(p)", ["factory(p)", "factory"]),                 # a call of a call result
    ("handlers[pick(p)](p)", ["handlers[pick(p)]", "pick"]),      # a subscript callee
    ("super().write(p)", ["write", "super"]),
    ("getattr(p, name(p))(p)", ["getattr(p, name(p))", "getattr", "name"]),
])
def test_python_callee_expression_shapes(tmp_path, expr, names):
    r = _parse(tmp_path, "python", "a.py", f"def f(p):\n    return {expr}\n")
    assert [c[1] for c in _calls(r)] == names
    assert {c[2] for c in _calls(r)} == {"f"}


def test_python_callee_call_keeps_the_context_of_its_call(tmp_path):
    """A call in the arguments of a local function's call has that function as its
    context (``nested_call``); a call in the callee expression of such an argument is
    evaluated in the same place, so it gets the same context."""
    r = _parse(tmp_path, "python", "a.py",
               "def local_fn(x):\n    return x\n\n\n"
               "def f(p):\n    return local_fn(open_secret(p).strip())\n")
    ctx = {c["name"]: c["context"] for c in r["function_calls"]}
    assert ctx["strip"] == ("local_fn", "nested_call", 6)
    assert ctx["open_secret"] == ctx["strip"]


def test_python_callee_call_in_a_lambda_in_a_class_body_and_in_a_decorator(tmp_path):
    r = _parse(tmp_path, "python", "a.py",
               "def f():\n    return (lambda: helper())()\n\n\n"
               "class K:\n    X = build(1).value()\n\n\n"
               "@make(a)(b)\ndef decorated():\n    pass\n")
    by_name = {c["name"]: c for c in r["function_calls"]}
    assert by_name["helper"]["context"][0] == "f"
    assert by_name["build"]["context"] == ("K", "class_definition", 5)
    assert by_name["build"]["class_context"] == ("K", "class_definition")
    assert by_name["make"]["context"] == ("<module>", "module", 1)


def test_python_records_emitted_before_keep_their_order(tmp_path):
    """The callee expression is walked after the call and its arguments: the
    records the parser emitted before come in the same order, new ones after them."""
    r = _parse(tmp_path, "python", "a.py", "def f(p):\n    return a(b(p)).c(d(p))\n")
    assert [c[1] for c in _calls(r)] == ["c", "d", "a", "b"]


# ── Python: every call has a record (ast oracle) ─────────────────────────────

def _type_alias_misparses(tree) -> List[ast.Call]:
    """``type(x)`` of an assignment target ``type(x).attr = v``: tree-sitter-python
    reads the statement as a PEP 695 type alias (the soft keyword ``type``)."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                root = target
                while isinstance(root, (ast.Attribute, ast.Subscript)):
                    root = root.value
                if isinstance(root, ast.Call) and isinstance(root.func, ast.Name) and root.func.id == "type":
                    out.append(root)
    return out


def _ast_calls(src: str) -> Counter:
    """(line, called name) of every call Python's own parser sees whose callee is a
    name or an attribute (``f(…)``, ``x.m(…)``), as a multiset."""
    tree = ast.parse(src)
    skip = {id(n) for n in _type_alias_misparses(tree)}
    out: Counter = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and id(node) not in skip:
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if name:
                out[(node.lineno, name)] += 1
    return out


def _python_corpus() -> List[Path]:
    roots = [REPO / "src" / "codegraphcontext",
             *sorted((REPO / "tests" / "fixtures" / "sample_projects").glob("sample_project*"))]
    return sorted(p for root in roots for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def test_python_parser_records_every_call_python_sees():
    """Recall against Python's own ``ast`` over CGC's source and the sample
    projects: every call whose callee is a name or an attribute has a call record
    at its line, however deep it sits in another call's callee, arguments,
    comprehensions, lambdas or decorators."""
    parser = TreeSitterParser("python")
    missing: Dict[str, List[Tuple[int, str]]] = {}
    checked = 0
    for path in _python_corpus():
        try:
            want = _ast_calls(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue                                   # a deliberately broken fixture
        got = Counter((c["line_number"], c["name"]) for c in parser.parse(path, False)["function_calls"])
        checked += sum(want.values())
        lost = want - got
        if lost:
            missing[str(path.relative_to(REPO))] = sorted(lost)
    assert checked > 10_000, f"the corpus shrank: {checked} calls"
    assert not missing, f"calls without a record: {dict(list(missing.items())[:10])}"


# ── every language: a call that is the receiver of a member call ─────────────

_RECEIVER_CASES = {
    "python": ("a.py", "def outer(p):\n    return inner(p).strip()\n"),
    "javascript": ("a.js", "function outer(p) {\n  return inner(p).trim();\n}\n"),
    "typescript": ("a.ts", "function outer(p: string) {\n  return inner(p).trim();\n}\n"),
    "tsx": ("a.tsx", "function outer(p: string) {\n  return inner(p).trim();\n}\n"),
    "java": ("A.java", "class A {\n  String outer(String p) {\n    return inner(p).trim();\n  }\n}\n"),
    "go": ("a.go", "package a\nfunc outer(p string) string {\n\treturn inner(p).Trim()\n}\n"),
    "ruby": ("a.rb", "def outer(p)\n  inner(p).strip\nend\n"),
    "rust": ("a.rs", "fn outer(p: &str) -> String {\n    inner(p).trim()\n}\n"),
    "php": ("a.php", "<?php\nfunction outer($p) {\n  return inner($p)->trim();\n}\n"),
    "c_sharp": ("a.cs", "class A {\n  string outer(string p) {\n    return inner(p).Trim();\n  }\n}\n"),
    "kotlin": ("a.kt", "fun outer(p: String): String {\n    return inner(p).trim()\n}\n"),
    "swift": ("a.swift", "func outer(p: String) -> String {\n    return inner(p).trim()\n}\n"),
    "scala": ("a.scala", "object A {\n  def outer(p: String): String = {\n    inner(p).trim()\n  }\n}\n"),
    "dart": ("a.dart", "String outer(String p) {\n  return inner(p).trim();\n}\n"),
    "cpp": ("a.cpp", "int outer(int p) {\n  return inner(p).trim();\n}\n"),
    "c": ("a.c", "int outer(int p) {\n  return inner(p)->trim(p);\n}\n"),
    "lua": ("a.lua", "function outer(p)\n  return inner(p):trim()\nend\n"),
    "elixir": ("a.ex", "defmodule A do\n  def outer(p) do\n    inner(p).trim()\n  end\nend\n"),
    "perl": ("a.pl", "sub outer {\n  my $p = shift;\n  return inner($p)->trim();\n}\n"),
}


@pytest.mark.parametrize("lang", sorted(_RECEIVER_CASES))
def test_call_that_is_the_receiver_of_a_member_call_is_recorded(tmp_path, lang):
    name, text = _RECEIVER_CASES[lang]
    r = _parse(tmp_path, lang, name, text)
    inner = [c for c in r["function_calls"] if c["name"] == "inner"]
    assert len(inner) == 1, _calls(r)
    assert inner[0]["context"][0] == "outer"
