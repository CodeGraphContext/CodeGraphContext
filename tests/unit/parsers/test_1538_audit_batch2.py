"""#1538 parser audit — 'wrong values' and 'missing declarations' batch.

One regression test per audit finding, each against the pinned grammar.
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


def test_rust_braced_use_list_yields_every_name():
    """`use a::{X, Y as Z, W};` kept only the last name, and
    full_import_name was raw source including `use` and `;`."""
    r = _parse("rust", "RustTreeSitterParser", "rust",
               "use std::collections::{HashMap, HashSet as HS, BTreeMap};\n"
               "use std::fmt;\nuse serde::*;\n", "rs")
    rows = {(i["name"], i["full_import_name"], i["alias"]) for i in r["imports"]}
    assert ("HashMap", "std::collections::HashMap", None) in rows
    assert ("HS", "std::collections::HashSet", "HS") in rows
    assert ("BTreeMap", "std::collections::BTreeMap", None) in rows
    assert ("fmt", "std::fmt", None) in rows
    assert ("*", "serde::*", None) in rows
    for _, full, _ in rows:
        assert not full.startswith("use ") and not full.endswith(";")


def test_csharp_generic_bases_are_not_shredded():
    """`: Dictionary<string, int>` split on every comma, creating INHERITS
    edges to 'Dictionary<string' and 'int>'."""
    r = _parse("csharp", "CSharpTreeSitterParser", "csharp",
               "class Map : Dictionary<string, int>, IDisposable { }\n", "cs")
    bases = {b for c in r["classes"] for b in c.get("bases", [])}
    assert "Dictionary<string, int>" in bases
    assert "IDisposable" in bases
    assert "Dictionary<string" not in bases and "int>" not in bases


def test_python_relative_import_keeps_package_level():
    """`from . import sibling` produced '..sibling' — one level too high."""
    r = _parse("python", "PythonTreeSitterParser", "python",
               "from . import sibling\nfrom .. import x\nfrom .pkg import y\nfrom a.b import z\n", "py")
    fulls = {i["name"]: i["full_import_name"] for i in r["imports"]}
    assert fulls["sibling"] == ".sibling"
    assert fulls["x"] == "..x"
    assert fulls["y"] == ".pkg.y"
    assert fulls["z"] == "a.b.z"


def test_dart_import_alias_is_extracted():
    """`import 'dart:math' as math;` lost the alias — a `math.max(...)` call
    could never be mapped back to its import."""
    r = _parse("dart", "DartTreeSitterParser", "dart",
               "import 'dart:math' as math;\nimport 'dart:io';\n", "dart")
    aliases = {i["name"]: i["alias"] for i in r["imports"]}
    assert aliases["dart:math"] == "math"
    assert aliases["dart:io"] is None


def test_scala_parameterless_defs_are_captured():
    """The functions query made `parameters` mandatory, dropping every
    parameterless def (getters, abstract members)."""
    r = _parse("scala", "ScalaTreeSitterParser", "scala",
               "object Utils {\n  def simple = 42\n  def withParens(): Int = 43\n}\n", "scala")
    names = {f["name"] for f in r["functions"]}
    assert {"simple", "withParens"} <= names


def test_ruby_singleton_methods_are_captured():
    """`def self.x` is a singleton_method node — never captured by the
    method-only query, in the parser or the cross-file pre-scan."""
    r = _parse("ruby", "RubyTreeSitterParser", "ruby",
               "class A\n  def self.build(x)\n  end\n  def plain(y)\n  end\nend\n", "rb")
    by_name = {f["name"]: f for f in r["functions"]}
    assert "build" in by_name and "plain" in by_name
    assert by_name["build"]["args"] == ["x"]


def test_ruby_pre_scan_sees_singleton_methods(tmp_path):
    from codegraphcontext.tools.languages.ruby import pre_scan_ruby
    from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager
    mgr = get_tree_sitter_manager()
    w = MagicMock()
    w.language_name = "ruby"
    w.language = mgr.get_language_safe("ruby")
    w.parser = mgr.create_parser("ruby")
    f = tmp_path / "svc.rb"
    f.write_text("class Svc\n  def self.build\n  end\nend\n", encoding="utf-8")
    imports_map = pre_scan_ruby([f], w)
    assert "build" in imports_map
