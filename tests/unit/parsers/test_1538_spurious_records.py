"""#1538 parser audit — final batch: duplicate/spurious records and the
remaining missing declarations."""
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


def test_php_enums_are_indexed_with_their_methods():
    r = _parse("php", "PhpTreeSitterParser", "php",
               "<?php\nenum Suit {\n  case Hearts;\n  public function color(): string { return 'red'; }\n}\n", "php")
    assert [(c["name"], c.get("node_type")) for c in r["classes"]] == [("Suit", "enum")]
    assert [(f["name"], f["class_context"]) for f in r["functions"]] == [("color", "Suit")]


def test_c_function_like_macros_are_extracted():
    r = _parse("c", "CTreeSitterParser", "c",
               "#define SQUARE(x) ((x)*(x))\n#define MAX 10\n", "c")
    by_name = {m["name"]: m for m in r["macros"]}
    assert by_name["SQUARE"]["params"] == ["x"]
    assert by_name["SQUARE"]["end_line"] == 1  # end_point trailing-newline off-by-one
    assert by_name["MAX"]["params"] == []


def test_c_enum_members_attribute_to_their_own_enum():
    r = _parse("c", "CTreeSitterParser", "c",
               "enum Color { RED, GREEN, BLUE };\nenum Status { OK, ERR };\n", "c")
    got = {(m["name"], m["enum_name"]) for m in r["enum_members"]}
    assert got == {("RED", "Color"), ("GREEN", "Color"), ("BLUE", "Color"),
                   ("OK", "Status"), ("ERR", "Status")}


def test_elixir_definition_heads_are_not_calls():
    r = _parse("elixir", "ElixirTreeSitterParser", "elixir",
               "defmodule M do\n  def hello(x) do\n    world(x)\n  end\n  def f(x), do: g(x)\nend\n", "ex")
    got = [(c["name"], c["line_number"]) for c in r["function_calls"]]
    assert ("hello", 2) not in got and ("f", 5) not in got
    assert ("world", 3) in got
    assert ("g", 5) in got  # inline `, do:` bodies still walked


def test_ruby_nested_calls_keep_their_own_receiver():
    r = _parse("ruby", "RubyTreeSitterParser", "ruby",
               "logger.info(formatter.render(payload))\n", "rb")
    by_name = {c["name"]: c["full_name"] for c in r["function_calls"]}
    assert by_name["info"] == "logger.info"
    assert by_name["render"] == "formatter.render"


def test_csharp_same_line_repeat_calls_are_kept():
    r = _parse("csharp", "CSharpTreeSitterParser", "csharp",
               "class A {\n  int M(int a, int b) { return Math.Max(Clamp(a), Clamp(b)); }\n}\n", "cs")
    names = [c["name"] for c in r["function_calls"]]
    assert names.count("Clamp") == 2


def test_csharp_attributes_and_declaration_line():
    r = _parse("csharp", "CSharpTreeSitterParser", "csharp",
               "class A {\n  [Obsolete]\n  [TestMethod]\n  void M() {}\n}\n", "cs")
    m = next(f for f in r["functions"] if f["name"] == "M")
    assert m["attributes"] == ["Obsolete", "TestMethod"]
    assert m["line_number"] == 4  # the declaration, not the attribute line


def test_haskell_curried_application_is_one_call():
    r = _parse("haskell", "HaskellTreeSitterParser", "haskell",
               "main :: IO ()\nmain = print (addTwo 1 2)\n"
               "both = addTwo 1 (addTwo 2 3)\n", "hs")
    line2 = [c["name"] for c in r["function_calls"] if c["line_number"] == 2]
    assert line2.count("addTwo") == 1
    # ...but genuinely distinct same-name calls on one line survive.
    line3 = [c["name"] for c in r["function_calls"] if c["line_number"] == 3]
    assert line3.count("addTwo") == 2
