"""#1625: a stale venv can silently test a different tree-sitter grammar.

Parser behaviour is grammar-version dependent (e.g. the Kotlin
single-line-object misparse of #1600 exists on 1.14.x but not 0.13.x), so a
venv holding a package outside pyproject's pin makes the suite pass while
disagreeing with CI. This test turns that silent divergence into a loud,
named failure at the top of any run.
"""
import re
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _pinned_requirement(name: str) -> Requirement:
    text = PYPROJECT.read_text(encoding="utf-8")
    for raw in re.findall(r'"([^"]+)"', text):
        try:
            req = Requirement(raw)
        except Exception:
            continue
        if req.name.lower().replace("_", "-") == name:
            return req
    raise AssertionError(f"{name} not found in pyproject.toml dependencies")


def test_tree_sitter_language_pack_matches_pyproject_pin():
    req = _pinned_requirement("tree-sitter-language-pack")
    installed = Version(metadata.version("tree-sitter-language-pack"))
    assert installed in req.specifier, (
        f"Installed tree-sitter-language-pack {installed} violates the "
        f"pyproject pin '{req.specifier}'. Parser results in this environment "
        f"differ from CI's — recreate the venv (pip install -e .[dev]) before "
        f"trusting any parser test outcome (#1625)."
    )
