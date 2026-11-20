"""Python import-bound INHERITS / METACLASS: one shape per test.

In-process (parse + pre-scan + builders), with the expected target written from
Python semantics, never read from src:

* a base names ONE definition: the writer pins it by line (a nested class, a
  function-local variable, a second definition of the name never receives the edge);
  two top-level ``class`` statements of the name are ambiguous (an ExternalClass);
* the same-file rule is scope-aware (``class Foo(Foo)``, function-local namesakes);
* the repository directory's own name never changes a result;
* namespace packages, ``__all__``, class-body imports;
* the Python layer is self-contained (standard library only) and works from the
  import records alone.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
from codegraphcontext.tools.indexing.resolution import inheritance as inheritance_mod
from codegraphcontext.tools.indexing.resolution import python_import_targets as layer
from codegraphcontext.tools.indexing.resolution.inheritance import (
    build_inheritance_and_csharp_files,
    build_metaclass_links,
)
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

EXT = {".py": "python"}


def _run(tmp_path: Path, files: Dict[str, str], repo: str = "proj") -> Dict[str, Any]:
    root = tmp_path / repo
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    parsers: Dict[str, Any] = {}

    def get_parser(ext):
        lang = EXT.get(ext)
        if lang and lang not in parsers:
            parsers[lang] = TreeSitterParser(lang)
        return parsers.get(lang)

    paths = sorted((root / r for r in files if Path(r).suffix in EXT), key=lambda p: p.as_posix())
    imports_map = pre_scan_for_imports(paths, EXT.keys(), get_parser)
    data = []
    for f in paths:
        d = get_parser(f.suffix).parse(f, False)
        d["repo_path"] = str(root)
        data.append(d)
    data.sort(key=lambda d: d["path"])
    prefix = root.resolve().as_posix() + "/"

    def rel(p):
        return p[len(prefix):] if isinstance(p, str) and p.startswith(prefix) else None

    rows, _ = build_inheritance_and_csharp_files(data, imports_map)
    out: Dict[str, Any] = {"data": data, "root": root, "imports_map": imports_map}
    out["inherits"] = {}
    for r in rows:
        out["inherits"].setdefault(r["child_name"], []).append(
            (r["parent_name"], rel(r["resolved_parent_file_path"]), r.get("parent_label"), r.get("parent_line")))
    out["meta"] = [(r["child_name"], r["parent_name"], rel(r["resolved_parent_file_path"]), r.get("parent_line"))
                   for r in build_metaclass_links(data, imports_map)]
    return out


# ── one definition, pinned by line; several are ambiguous ───────────────────

def test_an_imported_base_is_pinned_to_the_top_level_class(tmp_path):
    out = _run(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/base.py": ("class Base:\n    pass\n\nclass Outer:\n    class Base:\n        pass\n\n"
                        "def f():\n    class Base:\n        pass\n    return Base\n"),
        "a2.py": "from pkg.base import Base\n\nclass A2(Base):\n    pass\n",
    })
    assert out["inherits"]["A2"] == [("Base", "pkg/base.py", "Class", 1)]


def test_an_imported_variable_is_pinned_to_its_last_module_level_assignment(tmp_path):
    out = _run(tmp_path, {
        "orm.py": ("class BaseModel:\n    pass\n\nAbstractModel = BaseModel\n\n"
                   "def decoy():\n    AbstractModel = 1\n    return AbstractModel\n"),
        "p.py": "from orm import AbstractModel\n\nclass P(AbstractModel):\n    pass\n",
    })
    assert out["inherits"]["P"] == [("AbstractModel", "orm.py", "Variable", 4)]


def test_two_top_level_definitions_are_ambiguous(tmp_path):
    out = _run(tmp_path, {
        "dup.py": ("import sys\nif sys.version_info > (3,):\n    class D:\n        pass\n"
                   "else:\n    class D:\n        pass\n"),
        "a13.py": "from dup import D\n\nclass A13(D):\n    pass\n",
    })
    assert out["inherits"]["A13"] == [("D", None, None, None)]          # ExternalClass, no fan-out


def test_an_imported_metaclass_is_pinned(tmp_path):
    out = _run(tmp_path, {
        "meta.py": "class Meta(type):\n    pass\n\nclass Box:\n    class Meta(type):\n        pass\n",
        "m.py": "from meta import Meta\n\nclass M(metaclass=Meta):\n    pass\n",
    })
    assert out["meta"] == [("M", "Meta", "meta.py", 1)]


def test_an_imported_function_never_becomes_a_same_named_class_or_variable(tmp_path):
    """The import names a top-level FUNCTION; a nested class / a function-local variable
    of that name in the module is another definition — an ExternalClass, never an
    unpinned edge onto the namesake."""
    out = _run(tmp_path, {
        "lib_fn.py": "def Base():\n    return object\n\nclass Outer:\n    class Base:\n        pass\n",
        "lib_fv.py": "def Mixin():\n    return object\n\ndef g():\n    Mixin = 1\n    return Mixin\n",
        "c1.py": "from lib_fn import Base\nfrom lib_fv import Mixin\n\nclass C1(Base, Mixin):\n    pass\n",
    })
    assert sorted(out["inherits"]["C1"]) == [("Base", None, None, None), ("Mixin", None, None, None)]


def test_an_imported_variable_keeps_its_label_and_pin_beside_a_nested_class(tmp_path):
    out = _run(tmp_path, {
        "lib_v.py": "class _B:\n    pass\n\nBase = _B\n\nclass Outer:\n    class Base:\n        pass\n",
        "c2.py": "from lib_v import Base\n\nclass C2(Base):\n    pass\n",
    })
    assert out["inherits"]["C2"] == [("Base", "lib_v.py", "Variable", 4)]


# ── the repository directory's own name ─────────────────────────────────────

_ROOT_NAMED = {
    "utils.py": "class B:\n    pass\n",
    "pkg/__init__.py": "",
    "pkg/utils.py": "class B:\n    pass\n",
    "main.py": "from pkg.utils import B\n\nclass C(B):\n    pass\n",
}


@pytest.mark.parametrize("repo", ["proj", "pkg"])
def test_the_repository_directory_name_never_changes_a_target(tmp_path, repo):
    out = _run(tmp_path, _ROOT_NAMED, repo=repo)
    assert out["inherits"]["C"] == [("B", "pkg/utils.py", "Class", 1)]


def test_a_module_under_two_import_roots_is_ambiguous_not_missing(tmp_path):
    out = _run(tmp_path, {
        "src/pkg/__init__.py": "", "src/pkg/base.py": "class B:\n    pass\n",
        "tools/pkg/__init__.py": "", "tools/pkg/base.py": "class B:\n    pass\n",
        "main.py": "from pkg.base import B\n\nclass C(B):\n    pass\n",
    })
    assert out["inherits"]["C"] == [("B", None, None, None)]


def test_python_modules_prefer_an_import_root_over_the_repository_name():
    data = [{"path": "/w/pkg/utils.py", "repo_path": "/w/pkg"},
            {"path": "/w/pkg/pkg/__init__.py", "repo_path": "/w/pkg"},
            {"path": "/w/pkg/pkg/utils.py", "repo_path": "/w/pkg"},
            {"path": "/w/pkg/solo.py", "repo_path": "/w/pkg"}]
    m = layer.PythonModules(data)
    assert m.files("pkg.utils") == ("/w/pkg/pkg/utils.py",)
    # nothing below an import root: the repository directory itself is the package
    assert m.files("pkg.solo") == ("/w/pkg/solo.py",)


# ── namespace packages ──────────────────────────────────────────────────────

def test_a_base_through_namespace_packages(tmp_path):
    out = _run(tmp_path, {
        "ns/sub/mod.py": "class NBase:\n    pass\n",
        "a1.py": "import ns.sub.mod\n\nclass A1(ns.sub.mod.NBase):\n    pass\n",
        "a2.py": "from ns.sub import mod\n\nclass A2(mod.NBase):\n    pass\n",
        "a3.py": "import ns.sub.mod as m\n\nclass A3(m.NBase):\n    pass\n",
        "ns/use.py": "from .sub import mod\n\nclass A4(mod.NBase):\n    pass\n",
    })
    for child in ("A1", "A2", "A3", "A4"):
        assert out["inherits"][child] == [("NBase", "ns/sub/mod.py", "Class", 1)], child


# ── the same-file rule is scope-aware ───────────────────────────────────────

def test_a_function_local_namesake_never_shadows_the_import(tmp_path):
    out = _run(tmp_path, {
        "app/__init__.py": "", "app/database.py": "class Base:\n    pass\n",
        "user.py": ("from app.database import Base\n\nclass User(Base):\n    pass\n\n"
                    "def helper(rows):\n    for Base in rows:\n        pass\n    Base = None\n    return Base\n"),
    })
    assert out["inherits"]["User"] == [("Base", "app/database.py", "Class", 1)]


def test_a_class_named_like_its_imported_base_is_no_self_edge(tmp_path):
    out = _run(tmp_path, {
        "pkg/__init__.py": "", "pkg/base.py": "class Foo:\n    pass\n",
        "pkg/ext.py": "from .base import Foo\n\nclass Foo(Foo):\n    pass\n",
    })
    assert out["inherits"]["Foo"] == [("Foo", "pkg/base.py", "Class", 1)]


def test_a_later_module_level_definition_does_not_shadow_the_import(tmp_path):
    out = _run(tmp_path, {
        "pkg/__init__.py": "", "pkg/base.py": "class Base:\n    pass\n",
        "late.py": "from pkg.base import Base\n\nclass L(Base):\n    pass\n\nclass Base:\n    pass\n",
    })
    assert out["inherits"]["L"] == [("Base", "pkg/base.py", "Class", 1)]


def test_same_file_definitions_the_class_statement_sees(tmp_path):
    out = _run(tmp_path, {
        "local.py": (
            "class BaseModel:\n    pass\n\nAbstractModel = BaseModel\n\nclass Model(AbstractModel):\n    pass\n\n"
            "def decoy():\n    AbstractModel = None\n    return AbstractModel\n\n"
            "def make():\n    class B:\n        pass\n    class C(B):\n        pass\n    return C\n\n"
            "class O:\n    class A:\n        pass\n    class OB(A):\n        pass\n\n"
            "def outer():\n    class E:\n        pass\n    def inner():\n        class F(E):\n            pass\n"
            "        return F\n    return inner\n"),
    })
    assert out["inherits"]["Model"] == [("AbstractModel", "local.py", "Variable", 4)]
    assert out["inherits"]["C"] == [("B", "local.py", "Class", 14)]
    assert out["inherits"]["OB"] == [("A", "local.py", "Class", 21)]
    assert out["inherits"]["F"] == [("E", "local.py", "Class", 27)]


def test_two_same_file_alternatives_are_ambiguous(tmp_path):
    """Two module-level class statements of one name (version-conditional ``if`` /
    ``else``, ``try`` / ``except``) are alternatives — never guessed: an ExternalClass,
    not an edge to either (nor both)."""
    out = _run(tmp_path, {
        "p1.py": ("import sys\nif sys.version_info >= (3, 8):\n    class _Base:\n        pass\nelse:\n"
                  "    class _Base:\n        pass\n\nclass P1(_Base):\n    pass\n"),
        "p2.py": ("try:\n    from collections import OrderedDict as _D\n    class _Base(_D):\n        pass\n"
                  "except ImportError:\n    class _Base(dict):\n        pass\n\nclass P2(_Base):\n    pass\n"),
    })
    assert out["inherits"]["P1"] == [("_Base", None, None, None)]
    assert out["inherits"]["P2"] == [("_Base", None, None, None)]


def test_a_nested_class_does_not_see_a_module_definition_after_its_outer_class(tmp_path):
    """A class nested in a module-level class body is created while the outer class
    statement runs: a module-level definition AFTER the outer class is not visible."""
    out = _run(tmp_path, {
        "lib/__init__.py": "", "lib/base.py": "class Base:\n    pass\n",
        "p3.py": ("from lib.base import Base\n\nclass Outer:\n    class P3(Base):\n        pass\n\n"
                  "class Base:\n    pass\n"),
        "p4.py": "class Base:\n    pass\n\nclass Outer:\n    class P4(Base):\n        pass\n",
    })
    assert out["inherits"]["P3"] == [("Base", "lib/base.py", "Class", 1)]
    assert out["inherits"]["P4"] == [("Base", "p4.py", "Class", 1)]


def test_a_same_file_metaclass_is_scope_aware_and_pinned(tmp_path):
    """``metaclass=Meta`` names the definition the class statement sees: the
    module-level ``class Meta(type)``, never a Django-style inner ``class Meta:``."""
    out = _run(tmp_path, {
        "models.py": ("class Meta(type):\n    pass\n\nclass Thing:\n    class Meta:\n        ordering = 1\n\n"
                      "class M(metaclass=Meta):\n    pass\n"),
    })
    assert out["meta"] == [("M", "Meta", "models.py", 1)]


# ── star imports, class-body imports ────────────────────────────────────────

def test_a_star_import_honours_a_literal_dunder_all(tmp_path):
    out = _run(tmp_path, {
        "allmod.py": ("__all__ = ['Pub', '_Priv']\nclass Pub:\n    pass\nclass Hidden:\n    pass\n"
                      "class _Priv:\n    pass\n"),
        "a19.py": ("from allmod import *\n\nclass A19(Hidden):\n    pass\n\nclass A20(Pub):\n    pass\n\n"
                   "class A21(_Priv):\n    pass\n"),
    })
    assert out["inherits"]["A19"] == [("Hidden", None, None, None)]
    assert out["inherits"]["A20"] == [("Pub", "allmod.py", "Class", 2)]
    assert out["inherits"]["A21"] == [("_Priv", "allmod.py", "Class", 6)]


def test_the_parser_records_star_imported_modules(tmp_path):
    out = _run(tmp_path, {
        "lib/__init__.py": "", "lib/a.py": "class A:\n    pass\n",
        "s.py": "from lib.a import *\nfrom . import *\nfrom os.path import join\n",
    })
    fd = next(d for d in out["data"] if d["path"].endswith("/s.py"))
    assert fd["py_star_imports"] == [".", "lib.a"]


def test_the_python_layer_resolves_from_import_records(tmp_path):
    """Module-level, aliased and function-scoped import records bind their names; an
    import in another function or in a class body (a class attribute) binds none."""
    out = _run(tmp_path, {
        "lib/__init__.py": "", "lib/a.py": "def helper():\n    return 1\n\nclass Thing:\n    pass\n",
        "b.py": ("from lib.a import Thing as T\n\ndef one():\n    from lib.a import helper\n    return helper()\n\n"
                 "class K:\n    from lib.a import helper as kh\n\ndef two():\n    return 1\n"),
    })
    fd = next(d for d in out["data"] if d["path"].endswith("/b.py"))
    targets = layer.PythonImportTargets(out["data"])     # no alias table
    lib_a = (out["root"] / "lib/a.py").resolve().as_posix()
    assert targets.resolve(fd, "T", 1) == layer.Found(lib_a, "Thing", "Class", 4, (("Class", 4),))
    assert targets.resolve(fd, "helper", 5) == layer.Found(lib_a, "helper", "Function", 1, (("Function", 1),))
    assert targets.resolve(fd, "helper", 11) is layer.UNBOUND    # another function's import
    assert targets.resolve(fd, "kh", 11) is layer.UNBOUND        # a class attribute


def test_a_class_body_import_is_no_base_binding(tmp_path):
    out = _run(tmp_path, {
        "lib/__init__.py": "", "lib/a.py": "class Base:\n    pass\n",
        "aaa.py": "class Base:\n    pass\n",
        "b7.py": "class K:\n    from lib.a import Base\n\nclass C7(Base):\n    pass\n",
    })
    assert out["inherits"]["C7"] == [("Base", None, None, None)]


# ── the Python layer is self-contained ──────────────────────────────────────

def test_the_python_layer_imports_the_standard_library_only():
    src = Path(layer.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"relative import: {ast.dump(node)}"
            mods = [node.module or ""]
        elif isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        else:
            continue
        for mod in mods:
            top = mod.split(".")[0]
            assert top == "__future__" or top in sys.stdlib_module_names, mod


def test_the_alias_table_is_empty_unless_injected():
    data = [{"path": "/r/plugins/sale/__init__.py", "repo_path": "/r"},
            {"path": "/r/plugins/sale/models/order.py", "repo_path": "/r"}]
    assert not layer.PythonModules(data).in_repo("vendor.plugins.sale.models.order")
    assert layer.PythonModules(data, {"vendor.plugins.": ""}).in_repo("vendor.plugins.sale.models.order")


def test_the_metaclass_resolver_is_built_lazily(tmp_path, monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            raise AssertionError("built without an imported metaclass")

    out = _run(tmp_path, {"a.py": "class A:\n    pass\n", "b.py": "class Meta(type):\n    pass\n\n"
                          "class B(metaclass=Meta):\n    pass\n"})
    monkeypatch.setattr(inheritance_mod, "PythonImportTargets", Boom)
    assert [r["parent_name"] for r in build_metaclass_links(out["data"], out["imports_map"])] == ["Meta"]
