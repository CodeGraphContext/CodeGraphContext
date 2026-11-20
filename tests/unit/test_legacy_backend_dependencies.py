"""Dependency policy for the staged Kuzu retirement."""

import tomllib
from pathlib import Path

from packaging.requirements import Requirement


PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _requirements(values):
    return {Requirement(value).name: Requirement(value) for value in values}


def test_kuzu_is_optional_and_ladybug_is_the_maintained_core_backend():
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    core = _requirements(project["dependencies"])
    extras = project["optional-dependencies"]

    assert "kuzu" not in core
    assert "ladybug" in core
    assert ">=0.19" in str(core["ladybug"].specifier)
    assert "<0.20" in str(core["ladybug"].specifier)
    assert str(_requirements(extras["kuzu"])["kuzu"].specifier) == "==0.11.3"
    assert str(_requirements(extras["dev"])["kuzu"].specifier) == "==0.11.3"
