"""Tests that Go generic function instantiation calls are captured by the call query."""
from tree_sitter import Parser

from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager, execute_query
from codegraphcontext.tools.languages.go import GO_QUERIES


class _DummyGenericParserWrapper:
    def __init__(self):
        self.language_name = "go"
        self.ts_manager = get_tree_sitter_manager()
        self.language = self.ts_manager.get_language_safe("go")
        self.parser = Parser(self.language)


def _get_call_names(source: str) -> list[str]:
    wrapper = _DummyGenericParserWrapper()
    tree = wrapper.parser.parse(source.encode())
    return [
        node.text.decode()
        for node, capture_name in execute_query(wrapper.language, GO_QUERIES["calls"], tree.root_node)
        if capture_name == "name"
    ]


def test_plain_function_call_captured():
    src = b"package p\nfunc f() { foo() }"
    names = _get_call_names(src.decode())
    assert "foo" in names


def test_selector_call_captured():
    src = b'package p\nfunc f() { pkg.Bar() }'
    names = _get_call_names(src.decode())
    assert "Bar" in names


def test_generic_selector_call_captured():
    """web.Run[Clients, Config](...) — the motivating case."""
    src = b'package p\nfunc f() { web.Run[Clients, Config](ctx, cfg) }'
    names = _get_call_names(src.decode())
    assert "Run" in names


def test_generic_plain_call_not_a_call_expression():
    """NewClient[MyType](ctx) without a package qualifier is parsed by tree-sitter
    as a type_conversion_expression (ambiguous with type conversions), not a
    call_expression, so it produces no call edge. This is a tree-sitter limitation,
    not a bug in our query."""
    src = b'package p\nfunc f() { NewClient[MyType](ctx) }'
    names = _get_call_names(src.decode())
    assert "NewClient" not in names
