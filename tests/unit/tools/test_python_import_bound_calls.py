"""A bare Python call to a from-imported name resolves through the imported module.

``from app.util_a import helper; helper()`` used to take ``imports_map["helper"][0]``:
the first file, in pre-scan order, defining anything named ``helper`` (a nested
``def``, a method of an unrelated class, a namesake in another module), even when
``app.util_a`` defines no such name (#1921). The binding's module is now followed to
its file (``resolution/python_import_targets.py``); a name the file rebinds keeps
resolving locally.

The parsed records are written out in the shape ``PythonTreeSitterParser`` emits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups


def _fn(name, line, end, context=None, class_context=None, args=()):
    return {
        "name": name, "line_number": line, "end_line": end, "args": list(args),
        "context": context, "class_context": class_context, "lang": "python",
    }


def _cls(name, line, end):
    return {"name": name, "line_number": line, "end_line": end, "bases": [], "context": None, "lang": "python"}


def _var(name, line, context=None):
    return {"name": name, "line_number": line, "value": "1", "context": context, "class_context": None,
            "lang": "python"}


def _from_import(module, name, line=1):
    return {
        "name": name, "source": module, "imported_name": name, "full_import_name": f"{module}.{name}",
        "line_number": line, "alias": None, "context": (None, None), "lang": "python",
    }


def _call(name, line, caller, caller_line):
    return {
        "name": name, "full_name": name, "line_number": line, "args": [], "inferred_obj_type": None,
        "context": (caller, "function_definition", caller_line), "class_context": (None, None),
        "lang": "python",
    }


# rel path -> (functions, classes, variables, imports, calls)
FILES: Dict[str, Tuple[list, list, list, list, list]] = {
    "app/__init__.py": ([], [], [], [], []),
    "app/util_a.py": ([_fn("helper", 1, 2)], [], [], [], []),
    "app/aaa_first.py": ([_fn("helper", 1, 2), _fn("nothing_here", 5, 6)], [], [], [], []),
    "app/calls_helper.py": (
        [_fn("go", 4, 5)], [], [], [_from_import("app.util_a", "helper")], [_call("helper", 5, "go", 4)]),
    "app/actions.py": ([_fn("choose", 1, 2)], [], [], [], []),
    "app/aaa_views.py": ([_fn("outer", 1, 4), _fn("choose", 2, 3, context="outer")], [], [], [], []),
    "app/use_choose.py": (
        [_fn("run", 4, 5)], [], [], [_from_import("app.actions", "choose")], [_call("choose", 5, "run", 4)]),
    "app/rules.py": ([_fn("allow", 1, 2)], [], [], [], []),
    "app/aaa_log.py": ([_fn("allow", 2, 3, context="Log", class_context="Log")], [_cls("Log", 1, 3)], [], [], []),
    "app/use_allow.py": (
        [_fn("check", 4, 5)], [], [], [_from_import("app.rules", "allow")], [_call("allow", 5, "check", 4)]),
    "app/use_missing.py": (
        [_fn("missing", 4, 5)], [], [], [_from_import("app.util_a", "nothing_here")],
        [_call("nothing_here", 5, "missing", 4)]),
    # a relative import, and a class re-exported by a package __init__
    "app/models/__init__.py": ([], [], [], [_from_import(".user", "User")], []),
    "app/models/user.py": ([], [_cls("User", 1, 2)], [], [], []),
    "app/aaa_user.py": ([], [_cls("User", 1, 2)], [], [], []),
    "app/models/rel.py": (
        [_fn("rel", 4, 5)], [], [], [_from_import(".user", "User")], [_call("User", 5, "rel", 4)]),
    "app/use_pkg.py": (
        [_fn("make", 4, 5)], [], [], [_from_import("app.models", "User")], [_call("User", 5, "make", 4)]),
    # the file rebinds the imported name (one app.util_a does not define, so the import
    # rule would drop the call): a parameter of an enclosing function, a nested def, a
    # function-scoped assignment
    "app/shadow.py": (
        [
            _fn("outer", 4, 7, args=["nothing_here"]), _fn("inner", 5, 6, context="outer"),
            _fn("nested", 9, 12), _fn("nothing_here", 10, 11, context="nested"),
            _fn("assigned", 14, 16),
        ],
        [], [_var("nothing_here", 15, context="assigned")], [_from_import("app.util_a", "nothing_here")],
        [
            _call("nothing_here", 6, "inner", 5), _call("nothing_here", 12, "nested", 9),
            _call("nothing_here", 16, "assigned", 14),
        ],
    ),
    # a module outside the repository keeps the general resolution
    "app/use_ext.py": (
        [_fn("ext", 4, 5)], [], [], [_from_import("thirdparty.tools", "nothing_here")],
        [_call("nothing_here", 5, "ext", 4)]),
}


def _file_data(root: Path, order: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    data = []
    imports_map: Dict[str, List[str]] = {}
    for rel in order:
        functions, classes, variables, imports, calls = FILES[rel]
        path = (root / rel).resolve().as_posix()
        data.append({
            "path": path, "repo_path": str(root), "lang": "python",
            "functions": functions, "classes": classes, "variables": variables,
            "imports": imports, "function_calls": calls, "py_star_imports": [],
        })
        # as pre_scan_python: every class / def of the file, nested ones and methods too
        for item in classes + functions:
            imports_map.setdefault(item["name"], []).append(path)
    return data, imports_map


def _edges(root: Path, order: List[str]):
    data, imports_map = _file_data(root, order)
    diagnostics: List[Dict[str, Any]] = []
    groups = build_function_call_groups(data, imports_map, None, diagnostics=diagnostics)
    out: Dict[Tuple[str, int], List[Tuple[str, str, Optional[int], int]]] = {}
    for group in groups:
        for r in group:
            if r.get("type") == "parameter":
                target = "<param>"
            else:
                target = Path(r["called_file_path"]).resolve().relative_to(root.resolve()).as_posix()
            out.setdefault((r["caller_name"], r["line_number"]), []).append(
                (r["called_name"], target, r.get("called_line_number"), r["resolution_tier"]))
    return out, diagnostics


@pytest.fixture(params=["sorted", "reversed"])
def resolved(request, tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    order = sorted(FILES)
    if request.param == "reversed":
        order.reverse()
    return _edges(root, order)


def test_imported_function_resolves_to_the_imported_module(resolved):
    edges, _ = resolved
    assert edges[("go", 5)] == [("helper", "app/util_a.py", 1, 6)]


def test_nested_namesake_is_not_the_target(resolved):
    edges, _ = resolved
    assert edges[("run", 5)] == [("choose", "app/actions.py", 1, 6)]


def test_method_namesake_is_not_the_target(resolved):
    edges, _ = resolved
    assert edges[("check", 5)] == [("allow", "app/rules.py", 1, 6)]


def test_in_repo_module_without_the_name_makes_no_edge(resolved):
    edges, diagnostics = resolved
    assert ("missing", 5) not in edges
    assert any(
        d["reason"] == "python_import_target_unresolved" and d["caller_name"] == "missing"
        for d in diagnostics
    )


def test_relative_import_and_package_reexport_reach_the_class(resolved):
    edges, _ = resolved
    assert edges[("rel", 5)] == [("User", "app/models/user.py", 1, 6)]
    assert edges[("make", 5)] == [("User", "app/models/user.py", 1, 6)]


def test_local_rebinding_is_not_resolved_through_the_import(resolved):
    edges, diagnostics = resolved
    skipped = {d["caller_name"] for d in diagnostics if d["reason"] == "python_import_target_unresolved"}
    for caller, line in (("inner", 6), ("nested", 12), ("assigned", 16)):
        assert caller not in skipped
        assert edges.get((caller, line))


def test_external_module_keeps_general_resolution(resolved):
    edges, diagnostics = resolved
    assert "ext" not in {d["caller_name"] for d in diagnostics if d["reason"] == "python_import_target_unresolved"}
    assert edges.get(("ext", 5))
