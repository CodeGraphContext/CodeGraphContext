"""execute_query returns captures in tree-sitter's native, deterministic order.

py-tree-sitter 0.24+ ``QueryCursor.captures()`` returns ``{name: [nodes]}``
built through a per-name *set* of nodes, so the order inside a name followed
node ids (memory addresses) and changed on every parse of the same file — 8
orders in 8 parses — and flattening it grouped the captures by name. Every
consumer keeping the first or last capture attributed nondeterministically.

The contract pinned here:

* the order is a pure function of the tree: identical across re-parses;
* it is the C cursor's order — by start byte, then pattern index, outer node
  before inner — which is also the order in which ``captures()`` meets each
  capture name for the first time (its dict key order: the one part of its
  result that *is* native);
* the (node, name) pairs are exactly ``captures()``'s, each once;
* nothing else calls ``captures``/``matches`` directly.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.utils import tree_sitter_manager
from codegraphcontext.utils.tree_sitter_manager import execute_query

SRC = Path(tree_sitter_manager.__file__).resolve().parents[1]

PY_SOURCE = b"""
import os
from x import y as z

class A(Base):
    def f(self, a, b=1):
        options = {"k": self.g, "j": self.h}
        return helper(a)(b)

    def g(self):
        options = {"k": self.f}
        return [self.f(i) for i in range(3)]

def helper(n):
    def inner(m):
        return n + m
    return inner

class B(A):
    def h(self):
        return super().h() + self.g()
"""

# Several patterns, overlapping captures (call / name at the same start byte),
# several captures per name — the shapes where order matters.
PY_QUERY = """
(class_definition name: (identifier) @name) @class
(function_definition name: (identifier) @name) @function
(call function: (_) @callee) @call
(assignment left: (identifier) @var right: (dictionary) @dict)
(dictionary (pair value: (attribute) @value))
(identifier) @ident
"""


def _sig(captures):
    return [(n.start_byte, n.end_byte, n.type, name) for n, name in captures]


@pytest.fixture(scope="module")
def py():
    return TreeSitterParser("python")


def test_order_is_identical_across_reparses(py):
    """The bug: captures() set order changed with every parse of the same bytes."""
    orders = {tuple(_sig(execute_query(py.language, PY_QUERY, py.parser.parse(PY_SOURCE).root_node))) for _ in range(8)}
    assert len(orders) == 1, f"{len(orders)} different capture orders in 8 parses"


def test_order_is_native_document_order(py):
    caps = execute_query(py.language, PY_QUERY, py.parser.parse(PY_SOURCE).root_node)
    starts = [n.start_byte for n, _ in caps]
    assert starts == sorted(starts), "captures are not in start-byte order"
    # at one start byte the outer node of a pattern comes first: `class` before its
    # keyword-less children, `call` before its callee
    for (a, na), (b, nb) in zip(caps, caps[1:]):
        if a.start_byte == b.start_byte and na == "call" and nb == "callee":
            assert a.end_byte >= b.end_byte


def test_same_pairs_as_captures_and_first_seen_name_order(py):
    """Set-equal to QueryCursor.captures(); its dict key order (the order the C
    cursor first yields each name) equals ours."""
    from tree_sitter import Query, QueryCursor

    root = py.parser.parse(PY_SOURCE).root_node
    caps = execute_query(py.language, PY_QUERY, root)
    ref = QueryCursor(Query(py.language, PY_QUERY)).captures(root)
    assert {(n.id, name) for n, name in caps} == {(n.id, name) for name, ns in ref.items() for n in ns}
    assert len(caps) == len({(n.id, name) for n, name in caps}), "a (node, name) pair is repeated"
    first_seen = []
    for _, name in caps:
        if name not in first_seen:
            first_seen.append(name)
    assert first_seen == list(ref.keys())


def test_every_api_shape_flattens_to_the_same_order(py):
    """matches() shapes across py-tree-sitter versions: {name: [nodes]} (0.24/0.25),
    {name: node} (older), [(node, index)] — one order."""
    from tree_sitter import Query, QueryCursor

    from codegraphcontext.utils.tree_sitter_manager import _ordered_captures

    root = py.parser.parse(PY_SOURCE).root_node
    query = Query(py.language, PY_QUERY)
    names = [query.capture_name(i) for i in range(query.capture_count)]
    matches = QueryCursor(query).matches(root)
    as_lists = _ordered_captures(matches, names)
    as_pairs = _ordered_captures(
        [(pi, [(n, names.index(name)) for name, ns in d.items() for n in ns]) for pi, d in matches], names
    )
    single = [(pi, d) for pi, d in matches if all(len(ns) == 1 for ns in d.values())]
    as_single = _ordered_captures([(pi, {k: v[0] for k, v in d.items()}) for pi, d in single], names)
    assert _sig(as_lists) == _sig(as_pairs)
    assert _sig(as_single) == _sig(_ordered_captures(single, names))


def test_equal_span_ancestor_first_like_the_c_cursor():
    """Parent and child spanning the same bytes, captured by different patterns: the
    ancestor first whatever the pattern order — the C cursor's pre-order (checked
    against captures()' first-seen name order)."""
    from tree_sitter import Query, QueryCursor

    js = TreeSitterParser("javascript")
    root = js.parser.parse(b"foo(1)\n").root_node  # statement and call both span bytes 0-6
    for query in (
        "(call_expression) @c_call\n(expression_statement) @s_stmt",
        "(expression_statement) @s_stmt\n(call_expression) @c_call",
    ):
        ours = [name for _, name in execute_query(js.language, query, root)]
        assert ours == ["s_stmt", "c_call"]
        assert ours == list(QueryCursor(Query(js.language, query)).captures(root).keys())


def test_position_then_pattern_index(py):
    """An outer node before an inner one at the same start byte (tree pre-order, as
    the C cursor walks), whatever the pattern index; one node captured by two
    patterns: the lower pattern index first."""
    root = py.parser.parse(b"foo(1)\n").root_node
    for query in ("(identifier) @z_ident\n(call) @a_call", "(call) @a_call\n(identifier) @z_ident"):
        assert [name for _, name in execute_query(py.language, query, root)] == ["a_call", "z_ident"]
    same_node = execute_query(py.language, "(identifier) @b_second\n(identifier) @a_first", root)
    assert [name for _, name in same_node] == ["b_second", "a_first"]


# ── enforcement: nothing bypasses execute_query ──────────────────────────────

_DIRECT = re.compile(r"QueryCursor|captures|matches|tree_sitter")
_FORBIDDEN_ATTRS = {"captures", "matches"}


def _offenders(tree, rel):
    found = []
    aliases = {"QueryCursor"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("tree_sitter"):
            for alias in node.names:
                if alias.name == "QueryCursor":
                    aliases.add(alias.asname or alias.name)
                    found.append(f"{rel}:{node.lineno} imports QueryCursor")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in aliases:
            found.append(f"{rel}:{node.lineno} {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr == "QueryCursor":
            found.append(f"{rel}:{node.lineno} .QueryCursor")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_ATTRS:
                found.append(f"{rel}:{node.lineno} .{func.attr}()")
            elif (
                isinstance(func, ast.Name)
                and func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in _FORBIDDEN_ATTRS | {"QueryCursor"}
            ):
                found.append(f"{rel}:{node.lineno} getattr(…, {node.args[1].value!r})")
    return found


def test_no_module_calls_querycursor_captures_or_matches_directly():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "tree_sitter_manager.py" and path.parent.name == "utils":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not _DIRECT.search(text):
            continue
        offenders += _offenders(ast.parse(text), path.relative_to(SRC))
    assert not offenders, (
        "tree-sitter queries must go through utils.tree_sitter_manager.execute_query, which "
        "returns captures in a deterministic order; direct calls: " + ", ".join(offenders)
    )


def test_the_scanner_catches_aliases_and_getattr():
    src = (
        "from tree_sitter import QueryCursor as QC\n"
        "def f(q, n):\n"
        "    c = QC(q)\n"
        "    return getattr(c, 'captures')(n), c.matches(n)\n"
    )
    found = _offenders(ast.parse(src), "x.py")
    assert any("imports QueryCursor" in f for f in found)
    assert any("QC" in f for f in found)
    assert any("getattr" in f for f in found)
    assert any(".matches()" in f for f in found)
