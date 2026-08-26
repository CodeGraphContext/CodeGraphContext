"""#1660: the 'Minor' leftovers from the #1538 parser audit."""
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


def test_kotlin_annotated_declarations_report_the_declaration_line():
    r = _parse("kotlin", "KotlinTreeSitterParser", "kotlin",
               '@Deprecated("x")\nfun oldFn() {}\n\n@Entity\nclass Model\n\nfun plain() {}\n', "kt")
    fns = {f["name"]: f["line_number"] for f in r["functions"]}
    assert fns["oldFn"] == 2   # was 1 — the annotation line
    assert fns["plain"] == 7   # un-annotated declarations unchanged
    assert {c["name"]: c["line_number"] for c in r["classes"]}["Model"] == 5


def test_php_attributed_declarations_report_the_declaration_line():
    r = _parse("php", "PhpTreeSitterParser", "php",
               "<?php\n#[Attribute1]\nfunction f() {}\n#[Attr2]\nclass K {}\nfunction plain() {}\n", "php")
    fns = {f["name"]: f["line_number"] for f in r["functions"]}
    assert fns["f"] == 3       # was 2 — the attribute line
    assert fns["plain"] == 6
    assert {c["name"]: c["line_number"] for c in r["classes"]}["K"] == 5


def test_ruby_class_and_global_variables_are_captured_with_values():
    r = _parse("ruby", "RubyTreeSitterParser", "ruby",
               "class A\n  @@count = 0\nend\n$flag = true\nx = 1\n@inst = 2\n", "rb")
    by_name = {v["name"]: v for v in r["variables"]}
    # @@class and $global were never captured at all.
    assert by_name["@@count"]["type"] == "class"
    assert by_name["$flag"]["type"] == "global"
    assert by_name["@inst"]["type"] == "instance"
    # value was ALWAYS None: id() of a tree-sitter node is a fresh wrapper
    # per access, so @name/@value captures bucketed separately.
    assert by_name["@@count"]["value"] == "0"
    assert by_name["x"]["value"] == "1"
    assert by_name["$flag"]["value"] == "true"
