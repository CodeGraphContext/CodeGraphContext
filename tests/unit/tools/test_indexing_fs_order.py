"""Indexing does not depend on filesystem order.

``os.walk``/``os.fwalk``/``os.scandir``/``os.listdir``/``glob.glob``/
``glob.iglob``/``Path.glob``/``rglob``/``iterdir`` yield entries in directory
order, which depends on the filesystem (ext4 hash order, tmpfs creation order,
…): a temp copy, another machine or another filesystem can see another order,
and a first-wins/last-wins choice made while iterating becomes
nondeterministic. Every such call in indexing code is wrapped in
``sorted(...)`` (directly or around a comprehension over it), or listed in
``ALLOWED`` with the reason its order cannot matter.
"""

from __future__ import annotations

import ast
from pathlib import Path

import codegraphcontext as pkg

SRC = Path(pkg.__file__).resolve().parent
TOOLS = SRC / "tools"
SCANNED = sorted(
    list((TOOLS / "languages").glob("*.py"))
    + list((TOOLS / "indexing").rglob("*.py"))
    + [TOOLS / "graph_builder.py", TOOLS / "tree_sitter_parser.py", TOOLS / "package_resolver.py",
       TOOLS / "scip_indexer.py", SRC / "core" / "watcher.py", SRC / "utils" / "path_ignore.py"]
)
FS_ATTRS = {"glob", "iglob", "rglob", "iterdir", "listdir", "scandir", "walk", "fwalk"}
FS_MODULES = {"os", "glob", "os.path"}

#: (file name, function name, call source prefix) -> why order cannot matter
ALLOWED = {
    ("discovery.py", "safe_walk", "os.walk("):
        "top-down walk that prunes ignored dirs in place; discover_files_to_index returns the "
        "files sorted by POSIX path",
    ("scip_indexer.py", "detect_project_lang", "path.rglob("):
        "counted with sum(); order is irrelevant",
}


def _parents(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _bare_fs_names(tree):
    """Names bound by ``from os import walk`` / ``from glob import iglob as ig`` …"""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in FS_MODULES:
            for alias in node.names:
                if alias.name in FS_ATTRS:
                    names.add(alias.asname or alias.name)
    return names


def _is_fs_call(node, bare) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in FS_ATTRS:
        return True
    return isinstance(func, ast.Name) and func.id in bare


def _enclosing_function(node, parents):
    cur = parents.get(node)
    while cur is not None and not isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
        cur = parents.get(cur)
    return cur.name if cur is not None else "<module>"


def _wrapped_in_sorted(node, parents) -> bool:
    cur = parents.get(node)
    while cur is not None and not isinstance(cur, ast.stmt):
        if isinstance(cur, ast.Call) and isinstance(cur.func, ast.Name) and cur.func.id == "sorted":
            return True
        cur = parents.get(cur)
    return False


def test_filesystem_iteration_in_indexing_is_sorted():
    offenders = []
    for path in SCANNED:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = _parents(tree)
        bare = _bare_fs_names(tree)
        for node in ast.walk(tree):
            if not _is_fs_call(node, bare) or _wrapped_in_sorted(node, parents):
                continue
            src = ast.unparse(node)
            fn = _enclosing_function(node, parents)
            if any(path.name == f and fn == g and src.startswith(prefix) for f, g, prefix in ALLOWED):
                continue
            offenders.append(f"{path.relative_to(SRC)}:{node.lineno} {fn}: {src}")
    assert not offenders, (
        "filesystem order is not deterministic; wrap these in sorted(...) or justify them in ALLOWED: "
        + "; ".join(offenders))

