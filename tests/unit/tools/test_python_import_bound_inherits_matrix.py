"""Enforcement matrix: Python import form × INHERITS target.

Each cell file binds a name with one import form and uses it as a class base
(``class X(<base>)``). For every cell:

1. INHERITS reaches the expected target — written from this table, never from src;
   ``None``: nothing in the repository (an ExternalClass parent);
2. the answers do not depend on where the repository lives (copies under hostile
   directory names: ``…_t…``, ``…models…``, ``…base…``) nor on the repository
   directory's own name (``lib``: the name of a top-level package of the tree, with a
   root-level ``base.py`` decoy that ``lib.base`` would name through it).

Same-named decoys sort first (``aaa_decoy/``) so a first-of-many pick shows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
from codegraphcontext.tools.indexing.resolution.inheritance import build_inheritance_and_csharp_files
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

EXT = {".py": "python"}

LIB = {
    "lib/__init__.py": "from .base import Base\nfrom .mid import Deep\n",
    "lib/base.py": "class Base:\n    pass\n",
    "lib/mid.py": "from .deep import Deep\n",
    "lib/deep.py": "class Deep:\n    pass\n",
    "lib/sub/__init__.py": "",
    # names `lib.base` only through a repository directory called `lib` (never: the
    # package `lib/` is the import root's)
    "base.py": "class Base:\n    pass\n\nclass Deep:\n    pass\n",
    "aaa_decoy/__init__.py": "",
    "aaa_decoy/base.py": (
        "class Base:\n    pass\n\nclass Deep:\n    pass\n\nclass Missing:\n    pass\n\n"
        "class Thing:\n    pass\n"),
}


@dataclass(frozen=True)
class Cell:
    id: str
    file: str                       # the cell file
    imports: str                    # its import lines
    base: str                       # the base expression
    want: Optional[Tuple[str, str]]  # (file, name) the binding names; None: not in the repository
    scoped: bool = False            # the import and the class sit in a function


def _py(cell: Cell) -> str:
    if cell.scoped:
        return f"def use():\n    {cell.imports}\n    class X({cell.base}):\n        pass\n    return X\n"
    return f"{cell.imports}\n\nclass X({cell.base}):\n    pass\n"


BASE = ("lib/base.py", "Base")
CELLS = [
    Cell("py_from", "app/c_from.py", "from lib.base import Base", "Base", BASE),
    Cell("py_from_as", "app/c_from_as.py", "from lib.base import Base as B", "B", BASE),
    Cell("py_relative_1", "lib/c_rel1.py", "from .base import Base", "Base", BASE),
    Cell("py_relative_2", "lib/sub/c_rel2.py", "from ..base import Base", "Base", BASE),
    Cell("py_from_package_module", "app/c_from_mod.py", "from lib import base", "base.Base", BASE),
    Cell("py_import_dotted", "app/c_import.py", "import lib.base", "lib.base.Base", BASE),
    Cell("py_import_as", "app/c_import_as.py", "import lib.base as m", "m.Base", BASE),
    Cell("py_package_reexport", "app/c_pkg.py", "from lib import Base", "Base", BASE),
    Cell("py_two_hop_reexport", "app/c_two_hop.py", "from lib import Deep", "Deep", ("lib/deep.py", "Deep")),
    Cell("py_star", "app/c_star.py", "from lib.base import *", "Base", BASE),
    Cell("py_external", "app/c_external.py", "from extpkg.things import Thing", "Thing", None),
    Cell("py_missing", "app/c_missing.py", "from lib.base import Missing", "Missing", None),
    Cell("py_builtin", "app/c_builtin.py", "import os", "Exception", None),
    Cell("py_function_scoped", "app/c_scoped.py", "from lib.base import Base", "Base", BASE, scoped=True),
]

#: ``<parent directory>/<repository directory>`` of each copy of the repository.
ROOTS = ("neutral_zq1w2e3r/proj", "cgc_copy_tq1w2e3r/proj", "x_models_y/proj", "x_base_y/proj",
         "neutral_zq1w2e3r/lib")


def _files() -> Dict[str, str]:
    files = dict(LIB)
    for cell in CELLS:
        files[cell.file] = _py(cell)
    return files


def _resolve(root: Path, files: Dict[str, str]) -> Dict[str, Optional[Tuple[str, str]]]:
    parsers: Dict[str, Any] = {}

    def get_parser(ext):
        lang = EXT.get(ext)
        if lang and lang not in parsers:
            parsers[lang] = TreeSitterParser(lang)
        return parsers.get(lang)

    paths = sorted((root / rel for rel in files if Path(rel).suffix in EXT), key=lambda p: p.as_posix())
    imports_map = pre_scan_for_imports(paths, EXT.keys(), get_parser)
    data = []
    for f in paths:
        d = get_parser(f.suffix).parse(f, False)
        d["repo_path"] = str(root)
        data.append(d)
    data.sort(key=lambda d: d["path"])

    def rel(p):
        return Path(p).resolve().relative_to(root.resolve()).as_posix()

    inherits: Dict[str, Optional[Tuple[str, str]]] = {}
    for r in build_inheritance_and_csharp_files(data, imports_map)[0]:
        if r["child_name"] != "X":
            continue
        parent = None if r["resolved_parent_file_path"] == "__external__" else (
            rel(r["resolved_parent_file_path"]), r["parent_name"])
        assert rel(r["path"]) not in inherits, r
        inherits[rel(r["path"])] = parent
    return inherits


@pytest.fixture(scope="module")
def matrix(tmp_path_factory):
    files = _files()
    out = {}
    base = tmp_path_factory.mktemp("matrix")
    for name in ROOTS:
        root = base / name
        for rel, text in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        out[name] = _resolve(root, files)
    return out


@pytest.mark.parametrize("cell", CELLS, ids=[c.id for c in CELLS])
def test_inherits_target(matrix, cell):
    assert matrix[ROOTS[0]][cell.file] == cell.want


@pytest.mark.parametrize("root", ROOTS[1:])
def test_location_independent(matrix, root):
    assert matrix[root] == matrix[ROOTS[0]]
