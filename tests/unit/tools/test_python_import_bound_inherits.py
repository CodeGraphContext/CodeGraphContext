"""A Python class base bound by an import resolves through that import.

INHERITS used to test whether the *imported name* occurred in a candidate's path
(``from app.scheduler.base import SchedulerJob`` asked whether ``SchedulerJob`` is a
substring of ``…/app/scheduler/base.py``: never), so an imported base resolved WORSE
than an unimported one and became an ExternalClass; a dotted ``models.Model`` took the
first ``Model`` whose path contains ``models``; an alias (``Base as DBBase``) was
written under the alias, which no node carries; an unbound ``Exception`` took any
same-named class of the repository. The resolver
(``resolution/python_import_targets.py``) follows the import to the module's file,
through package re-exports, module-level re-imports and ``*`` imports.

In-process (parse + pre-scan + builders), as test_resolution_location_independence.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
from codegraphcontext.tools.indexing.resolution.inheritance import (
    _build_node_label_index,
    build_inheritance_and_csharp_files,
    build_metaclass_links,
)
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

EXT = {".py": "python", ".java": "java"}

FILES = {
    "backend/app/__init__.py": "",
    "backend/app/database.py": "class Base:\n    pass\n\ndef get_db():\n    return 1\n",
    "backend/app/other_base.py": "class Base:\n    pass\n",                 # a second same-named class
    "backend/app/scheduler/__init__.py": "from .base import SchedulerJob\n",  # package re-export
    "backend/app/scheduler/base.py": (
        "class SchedulerJob:\n    def run(self):\n        return 1\n\n"
        "class PerInstanceJob(SchedulerJob):\n    pass\n"),
    "backend/app/scheduler/jobs/__init__.py": "",
    "backend/app/scheduler/jobs/p1_from.py": (
        "from app.scheduler.base import SchedulerJob\n\nclass P1(SchedulerJob):\n    pass\n"),
    "backend/app/models/__init__.py": "",
    "backend/app/models/p2_base.py": "from app.database import Base\n\nclass P2(Base):\n    pass\n",
    "backend/app/scheduler/jobs/p3_modfrom.py": (
        "from app.scheduler import base\n\nclass P3(base.SchedulerJob):\n    pass\n"),
    "backend/app/scheduler/jobs/p4_import.py": (
        "import app.scheduler.base\n\nclass P4(app.scheduler.base.SchedulerJob):\n    pass\n"),
    "backend/app/scheduler/jobs/p5_alias.py": "import app.scheduler.base as b\n\nclass P5(b.SchedulerJob):\n    pass\n",
    "backend/app/scheduler/p6_rel.py": (
        "from .base import SchedulerJob\nfrom . import base\n\n"
        "class P6a(SchedulerJob):\n    pass\n\nclass P6b(base.SchedulerJob):\n    pass\n"),
    "backend/app/models/p7_alias.py": "from app.database import Base as DBBase\n\nclass P7(DBBase):\n    pass\n",
    "backend/app/scheduler/jobs/p8_reexport.py": (
        "from app.scheduler import SchedulerJob\n\nclass P8(SchedulerJob):\n    pass\n"),
    "backend/app/models/p9_ext.py": (
        "from sqlalchemy.orm import DeclarativeBase\nimport enum\n\n"
        "class P9(DeclarativeBase):\n    pass\n\nclass P10(enum.Enum):\n    A = 1\n"),
    "backend/app/models/p11_missing.py": "from app.database import Missing\n\nclass P11(Missing):\n    pass\n",
    # a framework package re-exports its ORM's classes (one of them a Variable alias);
    # a plugin defines its own `Model` in an alphabetically-first `…/models/models.py`
    "backend/framework/__init__.py": "",
    "backend/framework/models/__init__.py": (
        "from framework.orm.models import AbstractModel, BaseModel, Model\n"),
    "backend/framework/orm/__init__.py": "",
    "backend/framework/orm/models.py": (
        "class BaseModel:\n    pass\n\nAbstractModel = BaseModel\n\nclass Model(AbstractModel):\n    pass\n"),
    "backend/aaa_plugin/__init__.py": "",
    "backend/aaa_plugin/models/__init__.py": "",
    "backend/aaa_plugin/models/models.py": (
        "from framework import models\n\nclass Model(models.AbstractModel):\n    pass\n"),
    "backend/plugin_x/__init__.py": "",
    "backend/plugin_x/models/__init__.py": "",
    "backend/plugin_x/models/partner.py": (
        "from framework import models\n\nclass P12(models.Model):\n    pass\n\nclass P13(models.AbstractModel):\n    pass\n"),
    # a star import; an unbound builtin with an unrelated in-repo namesake
    "backend/app/models/p14_star.py": (
        "from app.scheduler.base import *\n\nclass P14(SchedulerJob):\n    pass\n\nclass P15(Exception):\n    pass\n"),
    "backend/app/models/shadow_exc.py": "class Exception:\n    pass\n",
    # METACLASS: an imported metaclass with a same-named decoy
    "backend/app/meta.py": "class Meta(type):\n    pass\n",
    "backend/app/aaa_meta.py": "class Meta(type):\n    pass\n",
    "backend/app/m1.py": "from app.meta import Meta\n\nclass M1(metaclass=Meta):\n    pass\n",
    "backend/app/errors.py": "class Error(Exception):\n    pass\n",
    # ── Java control (FQN path; unchanged) ──
    "java/com/x/Foo.java": "package com.x;\npublic class Foo {}\n",
    "java/com/y/Bar.java": "package com.y;\nimport com.x.Foo;\npublic class Bar extends Foo {}\n",
}

EXT_ROW = "__external__"


def _materialise(root: Path, files: Dict[str, str]) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _parse(root: Path, files: Dict[str, str]):
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
        d["repo_path"] = str(root)          # as GraphBuilder.parse_file sets it
        data.append(d)
    data.sort(key=lambda d: d["path"])
    return data, imports_map


def _rel(root: Path, p: Optional[str]) -> Optional[str]:
    if not p or p == EXT_ROW:
        return p
    return Path(p).resolve().relative_to(root.resolve()).as_posix()


@pytest.fixture(scope="module")
def resolved(tmp_path_factory):
    root = _materialise(tmp_path_factory.mktemp("pyib") / "proj", FILES)
    data, imports_map = _parse(root, FILES)
    rows, _cs = build_inheritance_and_csharp_files(data, imports_map)
    return root, data, imports_map, rows


def _inherits(root: Path, rows) -> Dict[str, List[Tuple[str, str, Optional[str]]]]:
    out: Dict[str, List[Tuple[str, str, Optional[str]]]] = {}
    for r in rows:
        out.setdefault(r["child_name"], []).append(
            (r["parent_name"], _rel(root, r["resolved_parent_file_path"]), r.get("parent_label")))
    return {k: sorted(v, key=repr) for k, v in out.items()}


# child -> [(parent name, parent file or __external__, parent label)]
EXPECTED = {
    "PerInstanceJob": [("SchedulerJob", "backend/app/scheduler/base.py", "Class")],
    "P1": [("SchedulerJob", "backend/app/scheduler/base.py", "Class")],
    "P2": [("Base", "backend/app/database.py", "Class")],
    "P3": [("SchedulerJob", "backend/app/scheduler/base.py", "Class")],
    "P4": [("SchedulerJob", "backend/app/scheduler/base.py", "Class")],
    "P5": [("SchedulerJob", "backend/app/scheduler/base.py", "Class")],
    "P6a": [("SchedulerJob", "backend/app/scheduler/base.py", "Class")],
    "P6b": [("SchedulerJob", "backend/app/scheduler/base.py", "Class")],
    "P7": [("Base", "backend/app/database.py", "Class")],
    "P8": [("SchedulerJob", "backend/app/scheduler/base.py", "Class")],
    "P9": [("DeclarativeBase", EXT_ROW, None)],
    "P10": [("Enum", EXT_ROW, None)],
    "P11": [("Missing", EXT_ROW, None)],
    "P12": [("Model", "backend/framework/orm/models.py", "Class")],
    "P13": [("AbstractModel", "backend/framework/orm/models.py", "Variable")],
    # the plugin's own Model: its base is the ORM's AbstractModel too; the ORM's Model
    # reaches the same-file Variable (unchanged)
    "Model": sorted([("AbstractModel", "backend/framework/orm/models.py", "Variable")] * 2, key=repr),
    "P14": [("SchedulerJob", "backend/app/scheduler/base.py", "Class")],
    "P15": [("Exception", EXT_ROW, None)],
    "Error": [("Exception", EXT_ROW, None)],
    "Bar": [("Foo", "java/com/x/Foo.java", "Class")],
    # `class Meta(type)`: a builtin base (the metaclasses of the METACLASS case)
    "Meta": [("type", EXT_ROW, None)] * 2,
}


def test_every_inherits_row(resolved):
    root, _data, _imap, rows = resolved
    assert _inherits(root, rows) == EXPECTED


@pytest.mark.parametrize("child", sorted(EXPECTED))
def test_inherits_row(resolved, child):
    """The same table, one case per child (a failure names the case)."""
    root, _data, _imap, rows = resolved
    assert _inherits(root, rows).get(child) == EXPECTED[child]


def test_an_alias_names_the_declared_class(resolved):
    # `from app.database import Base as DBBase; class P7(DBBase)`: the writer matches the
    # parent by (name, path), so the alias would match nothing (it was ExternalClass DBBase)
    _root, _data, _imap, rows = resolved
    assert [(r["parent_name"], r["confidence_label"]) for r in rows if r["child_name"] == "P7"] == [
        ("Base", "EXTRACTED")]


def test_every_internal_row_names_a_node_the_writer_can_match(resolved):
    # a Found row whose (name, path) is no node would be dropped silently by the writer
    _root, data, _imap, rows = resolved
    index = _build_node_label_index(data)
    for r in rows:
        if r["resolved_parent_file_path"] != EXT_ROW:
            labels = index.get(r["resolved_parent_file_path"], {}).get(r["parent_name"])
            assert labels, r
            assert r.get("parent_label") in labels, r


def test_a_dotted_base_never_reaches_a_same_named_class_elsewhere(resolved):
    # `models.Model` used to take the first `Model` whose path contains `models`
    root, _data, _imap, rows = resolved
    decoy = "backend/aaa_plugin/models/models.py"
    assert not [r for r in rows if _rel(root, r["resolved_parent_file_path"]) == decoy]


def test_imported_metaclass(resolved):
    root, data, imports_map, _rows = resolved
    rows = build_metaclass_links(data, imports_map)
    got = [(r["child_name"], r["parent_name"], _rel(root, r["resolved_parent_file_path"])) for r in rows]
    assert ("M1", "Meta", "backend/app/meta.py") in got, got


def test_a_parse_without_star_imports_keeps_every_other_target(tmp_path):
    """A parse without ``py_star_imports`` (an older parse) resolves from the import
    records alone: the same targets, except a base bound by a ``*`` import only (no
    record carries one), which stays an ExternalClass."""
    root = _materialise(tmp_path / "proj", FILES)
    data, imports_map = _parse(root, FILES)
    full = _inherits(root, build_inheritance_and_csharp_files(data, imports_map)[0])
    for d in data:
        d.pop("py_star_imports", None)
    legacy = _inherits(root, build_inheritance_and_csharp_files(data, imports_map)[0])
    assert legacy == dict(full, P14=[("SchedulerJob", EXT_ROW, None)])
