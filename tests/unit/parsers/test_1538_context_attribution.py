"""#1538 parser audit — context-attribution batch.

Call-site class_context was structurally dead in Java/C#/Swift (and shape-
inconsistent in PHP), Rust impl methods were orphaned from their type, JS
nested functions lost their enclosing context, and the writer's nested-
function CONTAINS gate only accepted Python's node type.
"""
import importlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


def _parse(mod_name, cls_name, ts_lang, code, ext):
    mgr = get_tree_sitter_manager()
    mod = importlib.import_module(f"codegraphcontext.tools.languages.{mod_name}")
    w = MagicMock()
    w.language_name = ts_lang
    w.language = mgr.get_language_safe(ts_lang)
    w.parser = mgr.create_parser(ts_lang)
    f = Path(tempfile.mkdtemp()) / f"t.{ext}"
    f.write_text(code, encoding="utf-8")
    return getattr(mod, cls_name)(w).parse(str(f))


def test_java_call_class_context_is_the_enclosing_class():
    r = _parse("java", "JavaTreeSitterParser", "java",
               "class Svc {\n  void run() {\n    helper();\n  }\n}\n", "java")
    call = next(c for c in r["function_calls"] if c["name"] == "helper")
    assert call["class_context"] == ("Svc", 1)


def test_csharp_call_class_context_is_the_enclosing_class():
    r = _parse("csharp", "CSharpTreeSitterParser", "csharp",
               "class Svc {\n  void Run() {\n    Helper();\n  }\n}\n", "cs")
    call = next(c for c in r["function_calls"] if c["name"] == "Helper")
    assert call["class_context"] == ("Svc", 1)


def test_swift_call_class_context_and_args():
    r = _parse("swift", "SwiftTreeSitterParser", "swift",
               "class Svc {\n  func run() {\n    helper(x: 1, y)\n  }\n}\n", "swift")
    call = next(c for c in r["function_calls"] if c["name"] == "helper")
    assert call["class_context"] == ("Svc", 1)
    assert call["args"] == ["x: 1", "y"]


def test_php_call_class_context_shape_is_uniform():
    """Plain calls emitted a bare string while `new X()` emitted a dead
    (None, None) tuple — one list, two shapes."""
    r = _parse("php", "PhpTreeSitterParser", "php",
               "<?php\nclass A {\n  function m() {\n    helper();\n    $x = new Widget();\n  }\n}\n", "php")
    by_name = {c["name"]: c for c in r["function_calls"]}
    assert by_name["helper"]["class_context"] == ("A", 2)
    assert by_name["Widget"]["class_context"] == ("A", 2)


def test_php_top_level_call_class_context_is_none():
    r = _parse("php", "PhpTreeSitterParser", "php",
               "<?php\nhelper();\nfunction helper() {}\n", "php")
    call = next(c for c in r["function_calls"] if c["name"] == "helper")
    assert call["class_context"] is None


def test_rust_impl_methods_carry_their_type_as_class_context():
    r = _parse("rust", "RustTreeSitterParser", "rust",
               "struct Point;\nimpl Point {\n    fn new() {}\n}\n"
               "impl Draw for Point {\n    fn draw(&self) {}\n}\nfn free() {}\n", "rs")
    by_name = {f["name"]: f for f in r["functions"]}
    assert by_name["new"]["class_context"] == "Point"
    assert by_name["draw"]["class_context"] == "Point"
    assert by_name["free"]["class_context"] is None


def test_js_nested_function_stores_enclosing_context():
    r = _parse("javascript", "JavascriptTreeSitterParser", "javascript",
               "function outer() {\n  function inner() {}\n}\n", "js")
    by_name = {f["name"]: f for f in r["functions"]}
    assert by_name["inner"]["context"] == "outer"
    assert by_name["inner"]["context_type"] == "function_declaration"
    assert isinstance(by_name["inner"]["context_line"], int)


def test_writer_gate_accepts_non_python_function_context_types():
    from codegraphcontext.tools.indexing.persistence.writer import _FUNCTION_CONTEXT_TYPES
    # The gate that only matched Python's node type
    assert "function_definition" in _FUNCTION_CONTEXT_TYPES
    # ...must also match the other grammars' function-ish types
    for t in ("function_declaration", "method_declaration", "function_item",
              "method", "arrow_function"):
        assert t in _FUNCTION_CONTEXT_TYPES
