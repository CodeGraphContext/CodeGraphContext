"""Python class bases bound by an import, written by both embedded engines.

The in-process tests (tests/unit/tools/test_python_import_bound_*.py) prove the link
rows; this proves what the writer makes of them: the exact INHERITS edges
(``(child, label(parent), parent.name, parent.path)``) and exactly ONE edge per child —
a parent is matched by (name, path) AND its line, so a function-local
``AbstractModel = …`` or a nested ``class NB`` in the target file never receives the
edge too, whatever the child label's state (a child whose name is also a local of its
file has no pinned label) — the ExternalClass names, and the METACLASS edge.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TREE = {
    "backend/app/__init__.py": "",
    "backend/app/database.py": "class Base:\n    pass\n",
    "backend/app/other_base.py": "class Base:\n    pass\n",
    "backend/app/tasks/__init__.py": "from .base import TaskBase\n",
    "backend/app/tasks/base.py": "class TaskBase:\n    pass\n",
    "backend/app/jobs.py": (
        "from app.tasks.base import TaskBase\nfrom app.tasks import TaskBase as Reexported\n"
        "from app.database import Base as DBBase\n\n"
        "class P1(TaskBase):\n    pass\n\nclass P7(DBBase):\n    pass\n\nclass P8(Reexported):\n    pass\n"),
    # a framework package re-exports its ORM's classes; the ORM's own file has a
    # function-local decoy `AbstractModel`; a plugin defines its own `Model`
    "backend/framework/__init__.py": "",
    "backend/framework/models/__init__.py": (
        "from framework.orm.models import AbstractModel, BaseModel, Model\n"),
    "backend/framework/orm/__init__.py": "",
    "backend/framework/orm/models.py": (
        "class BaseModel:\n    pass\n\nAbstractModel = BaseModel\n\nclass Model(AbstractModel):\n    pass\n\n"
        "def decoy():\n    AbstractModel = None\n    return AbstractModel\n"),
    "backend/aaa_plugin/models/models.py": (
        "from framework import models\n\nclass Model(models.AbstractModel):\n    pass\n"),
    "backend/plugin_x/models/partner.py": (
        "from framework import models\n\nclass P12(models.Model):\n    pass\n\nclass P13(models.AbstractModel):\n    pass\n"),
    # a Class parent with a nested namesake; a child whose name is also a function
    # local of its file (its label is not pinned: the writer enumerates child labels)
    "backend/app/nested_base.py": "class NB:\n    pass\n\nclass Outer:\n    class NB:\n        pass\n",
    "backend/app/pn.py": "from app.nested_base import NB\n\nclass PN(NB):\n    pass\n",
    "backend/plugin_x/models/p14.py": (
        "from framework.models import AbstractModel\n\nclass P14(AbstractModel):\n    pass\n\n"
        "def g():\n    P14 = 1\n    return P14\n"),
    # an unbound builtin with an in-repo namesake
    "backend/app/shadow.py": "class Exception:\n    pass\n",
    "backend/app/p15.py": "class P15(Exception):\n    pass\n",
    # an imported FUNCTION with a nested class namesake -> ExternalClass
    "backend/app/lib_fn.py": "def FnBase():\n    return object\n\nclass Outer:\n    class FnBase:\n        pass\n",
    "backend/app/c1.py": "from app.lib_fn import FnBase\n\nclass C1(FnBase):\n    pass\n",
    # two same-named children in two scopes of one file, each with its own parent
    "backend/app/dd.py": ("class DBase:\n    pass\n\ndef f():\n    class DBase:\n        pass\n    class DC(DBase):\n"
                          "        pass\n    return DC\n\nclass DC(DBase):\n    pass\n"),
    # METACLASS: an imported metaclass with a nested namesake in its own file
    "backend/app/meta.py": "class Meta(type):\n    pass\n\nclass Box:\n    class Meta(type):\n        pass\n",
    "backend/app/m1.py": "from app.meta import Meta\n\nclass M1(metaclass=Meta):\n    pass\n",
}

#: child -> (parent label, parent name, parent path relative to the repo or None)
EXPECTED = {
    "P1": ("Class", "TaskBase", "backend/app/tasks/base.py"),
    "P7": ("Class", "Base", "backend/app/database.py"),
    "P8": ("Class", "TaskBase", "backend/app/tasks/base.py"),
    "P12": ("Class", "Model", "backend/framework/orm/models.py"),
    "P13": ("Variable", "AbstractModel", "backend/framework/orm/models.py"),
    "P14": ("Variable", "AbstractModel", "backend/framework/orm/models.py"),
    "PN": ("Class", "NB", "backend/app/nested_base.py"),
    "P15": ("ExternalClass", "Exception", None),
    "C1": ("ExternalClass", "FnBase", None),
}

_SCRIPT = '''
import asyncio, json, os, sys
from pathlib import Path
from codegraphcontext.core import get_database_manager
from codegraphcontext.core.jobs import JobManager
from codegraphcontext.tools.graph_builder import GraphBuilder
manager = get_database_manager(db_path=os.environ['CGC_RUNTIME_DB_PATH'])
repo = Path(sys.argv[1])
prefix = repo.as_posix() + '/'
def rel(p):
    return p[len(prefix):] if isinstance(p, str) and p.startswith(prefix) else None
try:
    async def index():
        jobs = JobManager()
        builder = GraphBuilder(manager, jobs, asyncio.get_running_loop())
        await builder.build_graph_from_path_async(repo, job_id=jobs.create_job(str(repo), is_dependency=False))
    asyncio.run(index())
    out = {'inherits': [], 'metaclass': [], 'dc': []}
    with manager.get_driver().session() as session:
        # one query per parent label: backend-neutral
        for label in ('Class', 'Variable', 'ExternalClass'):
            for r in session.run(
                    f'MATCH (c:Class)-[:INHERITS]->(p:{label}) '
                    'RETURN c.name AS c, c.path AS cp, p.name AS n, p.path AS pp').data():
                out['inherits'].append([r['c'], rel(r['cp']), label, r['n'], rel(r['pp'])])
        for r in session.run('MATCH (c:Class)-[:METACLASS]->(p:Class) '
                             'RETURN c.name AS c, p.name AS n, p.path AS pp, p.line_number AS pl').data():
            out['metaclass'].append([r['c'], r['n'], rel(r['pp']), r['pl']])
        for r in session.run("MATCH (c:Class {name: 'DC'})-[:INHERITS]->(p:Class {name: 'DBase'}) "
                             'RETURN c.line_number AS cl, p.line_number AS pl').data():
            out['dc'].append([r['cl'], r['pl']])
    print('RESULT ' + json.dumps(out))
finally:
    manager.close_driver()
'''


def _index(tmp_path: Path, backend: str) -> dict:
    repo = (tmp_path / "repo").resolve()
    for rel, text in TREE.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    env = os.environ.copy()
    env.update(CGC_RUNTIME_DB_TYPE=backend, CGC_RUNTIME_DB_PATH=str(tmp_path / "graph.db"),
               SCIP_INDEXER="false", ENABLE_INHERIT_RESOLVE="false", ENABLE_VECTOR_RESOLVE="false")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    result = subprocess.run([sys.executable, "-c", _SCRIPT, str(repo)], env=env,
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith("RESULT "))
    return json.loads(line[len("RESULT "):])


@pytest.mark.integration
@pytest.mark.parametrize("backend,module", [("kuzudb", "kuzu"), ("ladybugdb", "ladybug")])
def test_import_bound_python_bases(tmp_path, backend, module):
    if importlib.util.find_spec(module) is None:
        pytest.skip(f"{module} is not installed")
    got = _index(tmp_path, backend)
    rows = [tuple(r) for r in got["inherits"]]
    for child, want in EXPECTED.items():
        # exactly one edge: no fan-out onto a function-local or nested namesake
        assert [r[2:] for r in rows if r[0] == child] == [want], (child, rows)
    # the plugin's own `Model` (`models.AbstractModel`) reaches the module-level Variable,
    # and so does the ORM's own `class Model(AbstractModel)` (a same-file base): one edge each
    for path in ("backend/aaa_plugin/models/models.py", "backend/framework/orm/models.py"):
        assert [r[2:] for r in rows if r[:2] == ("Model", path)] == [
            ("Variable", "AbstractModel", "backend/framework/orm/models.py")], rows
    # nothing reaches the plugin's same-named `Model`
    assert not [r for r in rows if r[4] == "backend/aaa_plugin/models/models.py"], rows
    # no ExternalClass is left for a name an import resolved
    ext = {r[3] for r in rows if r[2] == "ExternalClass"}
    assert not ext & {"DBBase", "Base", "TaskBase", "Reexported", "Model", "AbstractModel", "NB"}, ext
    # the module-level metaclass, not the nested namesake
    assert got["metaclass"] == [["M1", "Meta", "backend/app/meta.py", 1]], got["metaclass"]
    # two same-named children, each with its own pinned parent: both true edges exist
    # (children are matched by (name, path), so each DC also gets the other's parent)
    dc = {tuple(r) for r in got["dc"]}
    assert {(7, 5), (11, 1)} <= dc, dc
