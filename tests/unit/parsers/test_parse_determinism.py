"""Parsing is deterministic: same bytes in, same parse output out.

Every file of every sample project is parsed twice
in this process and once in each of two fresh interpreters with different
PYTHONHASHSEEDs; the canonical JSON of each parse result — list order included,
since downstream maps are built by iterating these lists and keep the first or
last entry — must be identical everywhere.

``execute_query`` used to return captures in an order that changed with every
parse (py-tree-sitter's ``captures()`` set order), so lists came out in a
different order run to run and first-wins consumers attributed differently.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

import pytest

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "tests" / "fixtures"
ROOTS = sorted(p for p in (FIXTURES / "sample_projects").iterdir() if p.is_dir())


def _digests(roots) -> Dict[str, str]:
    """{relative file path: sha256 of the canonical parse result} for every parseable file."""
    from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

    extensions = _extension_map()
    parsers: Dict[str, object] = {}
    out: Dict[str, str] = {}
    for root in roots:
        for path in sorted(Path(root).rglob("*")):
            lang = extensions.get(path.suffix)
            if not lang or not path.is_file():
                continue
            if lang not in parsers:
                parsers[lang] = TreeSitterParser(lang)
            result = parsers[lang].parse(path, False)
            blob = json.dumps(result, sort_keys=True, default=str, ensure_ascii=False)
            out[path.relative_to(REPO).as_posix()] = hashlib.sha256(blob.encode()).hexdigest()
    return out


def _extension_map() -> Dict[str, str]:
    """GraphBuilder's extension -> language map, without constructing a GraphBuilder (needs a DB)."""
    import ast
    import inspect

    from codegraphcontext.tools import graph_builder

    tree = ast.parse(inspect.getsource(graph_builder.GraphBuilder.__init__).lstrip())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Attribute)
            and node.targets[0].attr == "parsers"
            and isinstance(node.value, ast.Dict)
        ):
            return {k.value: v.value for k, v in zip(node.value.keys, node.value.values)}
    raise AssertionError("GraphBuilder.parsers literal not found")


_CHILD = r"""
import json, sys
sys.path.insert(0, {src!r}); sys.path.insert(0, {tests!r})
from test_parse_determinism import _digests, ROOTS
print(json.dumps(_digests(ROOTS)))
"""


@pytest.fixture(scope="module")
def in_process():
    return _digests(ROOTS)


def test_fixture_set_is_not_empty(in_process):
    assert len(in_process) > 200, len(in_process)


def test_reparse_in_one_process_is_identical(in_process):
    again = _digests(ROOTS)
    differing = sorted(k for k in in_process if again.get(k) != in_process[k])
    assert not differing, f"{len(differing)} file(s) parse differently on a second parse: {differing[:10]}"


@pytest.mark.parametrize("seed", ["1", "2"])
def test_parse_is_identical_across_processes_and_hash_seeds(in_process, seed):
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEO4J_")}
    env["PYTHONHASHSEED"] = seed
    code = _CHILD.format(src=str(REPO / "src"), tests=str(Path(__file__).parent))
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=str(REPO), timeout=600
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    other = json.loads(proc.stdout.strip().splitlines()[-1])
    assert set(other) == set(in_process)
    differing = sorted(k for k in in_process if other[k] != in_process[k])
    assert not differing, f"{len(differing)} file(s) parse differently under PYTHONHASHSEED={seed}: {differing[:10]}"
