"""Tests for path_ignore helpers (dead code / IGNORE_DIRS alignment)."""

from pathlib import Path

from codegraphcontext.cli.config_manager import DEFAULT_CONFIG
from codegraphcontext.utils.path_ignore import (
    cypher_path_not_under_ignore_dirs,
    file_path_has_ignore_dir_segment,
)


def test_default_config_lists_node_modules():
    assert "node_modules" in DEFAULT_CONFIG["IGNORE_DIRS"]


def test_cypher_fragment_contains_node_modules():
    frag = cypher_path_not_under_ignore_dirs("func.path", ignore_dir_names=["node_modules"])
    assert "func.path" in frag
    assert "node_modules" in frag
    assert frag.strip().startswith("AND NOT")


def test_file_path_has_ignore_dir_segment():
    root = Path("/proj")
    assert file_path_has_ignore_dir_segment(Path("/proj/node_modules/foo/a.js"), root) is True
    assert file_path_has_ignore_dir_segment(Path("/proj/src/a.js"), root) is False
