"""Pattern tests for Python CALLS resolution gaps (CGC_GRAPH_INCONSISTENCIES IDs 1–3)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
from codegraphcontext.tools.languages.python import PythonTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

SAMPLE_PROJECT = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "sample_projects"
    / "sample_project"
)


@pytest.fixture(scope="module")
def parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "python"
    wrapper.language = manager.get_language_safe("python")
    wrapper.parser = manager.create_parser("python")
    return PythonTreeSitterParser(wrapper)


def _resolve_file(parser, relative_path: str):
    source_path = SAMPLE_PROJECT / relative_path
    parsed = parser.parse(str(source_path))
    file_data = [{
        "path": str(source_path.resolve()),
        "lang": "python",
        "functions": parsed["functions"],
        "classes": parsed.get("classes", []),
        "function_calls": parsed["function_calls"],
        "imports": [],
    }]
    return build_function_call_groups(file_data, {})


def _fn_edges(groups):
    fn_to_fn = groups[0]
    fn_to_param = groups[8]
    return fn_to_fn, fn_to_param


class TestPythonCallResolutionPatterns:
    def test_list_comprehension_calls_square(self, parser):
        """ID 1: calls() -> square inside list comprehension."""
        fn_to_fn, _ = _fn_edges(_resolve_file(parser, "advanced_calls.py"))
        edge = next(
            e for e in fn_to_fn
            if e["caller_name"] == "calls" and e["called_name"] == "square"
        )
        assert edge["line_number"] == 5

    def test_higher_order_calls_parameter_func(self, parser):
        """ID 2: higher_order(func, data) -> CALLS Parameter:func."""
        _, fn_to_param = _fn_edges(_resolve_file(parser, "advanced_functions.py"))
        edge = next(
            e for e in fn_to_param
            if e["caller_name"] == "higher_order" and e["called_name"] == "func"
        )
        assert edge["line_number"] == 8
        assert edge["called_line_number"] == 7

    def test_super_greet_resolves_to_parent_class(self, parser):
        """ID 3: B.greet super().greet() -> A.greet."""
        fn_to_fn, _ = _fn_edges(_resolve_file(parser, "class_instantiation.py"))
        edge = next(
            e for e in fn_to_fn
            if e["caller_name"] == "greet"
            and e.get("called_context") == "A"
            and e.get("full_call_name") == "super().greet"
        )
        assert edge["line_number"] == 5
        assert edge["called_line_number"] == 2
