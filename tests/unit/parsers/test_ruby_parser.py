"""Ruby parser defects (#1523, #1527).

Both were silent: the graph simply lacked nodes and edges that should have
been there, with no parse error to indicate it.
"""

import pytest
from unittest.mock import MagicMock

from codegraphcontext.tools.languages.ruby import RubyTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


class TestRubyParser:
    @pytest.fixture(scope="class")
    def parser(self):
        manager = get_tree_sitter_manager()
        wrapper = MagicMock()
        wrapper.language_name = "ruby"
        wrapper.language = manager.get_language_safe("ruby")
        wrapper.parser = manager.create_parser("ruby")
        return RubyTreeSitterParser(wrapper)

    def _parse(self, parser, tmp_path, code):
        f = tmp_path / "sample.rb"
        f.write_text(code, encoding="utf-8")
        return parser.parse(str(f))

    # ------------------------------------------------------------- #1523
    def test_nested_class_does_not_replace_its_parent(self, parser, tmp_path):
        """Names were matched to classes by byte range, so an inner class's
        name landed on the outer class (the first container in document order)
        and the inner entry, left nameless, was dropped. `class Client`
        wrapping `class TimeoutError` produced exactly one class — named
        TimeoutError, carrying Client's line range.
        """
        code = (
            "class Client\n"
            "  class TimeoutError < StandardError\n"
            "  end\n"
            "end\n"
        )
        result = self._parse(parser, tmp_path, code)
        by_name = {c["name"]: c for c in result["classes"]}

        assert set(by_name) == {"Client", "TimeoutError"}
        assert by_name["Client"]["line_number"] == 1
        assert by_name["TimeoutError"]["line_number"] == 2
        # The inner class keeps its own superclass rather than losing it.
        assert by_name["TimeoutError"]["bases"] == ["StandardError"]
        assert by_name["Client"]["bases"] == []

    def test_sibling_classes_are_both_kept(self, parser, tmp_path):
        code = "class A < Base\nend\n\nclass B\nend\n"
        result = self._parse(parser, tmp_path, code)
        by_name = {c["name"]: c for c in result["classes"]}
        assert set(by_name) == {"A", "B"}
        assert by_name["A"]["bases"] == ["Base"]

    def test_class_nested_in_a_module(self, parser, tmp_path):
        code = "module M\n  class Inner\n  end\nend\n"
        result = self._parse(parser, tmp_path, code)
        assert "Inner" in {c["name"] for c in result["classes"]}

    # ------------------------------------------------------------- #1527
    def test_method_parameters_are_extracted(self, parser, tmp_path):
        """Parameters live in a `method_parameters` child, not directly on the
        method, so scanning the method's own children found only its name —
        which the code explicitly skipped. Every Ruby method reported zero
        parameters and no HAS_PARAMETER edge was ever created.
        """
        result = self._parse(parser, tmp_path, "def add(a, b)\n  a + b\nend\n")
        fn = next(f for f in result["functions"] if f["name"] == "add")
        assert fn["args"] == ["a", "b"]

    def test_all_parameter_forms(self, parser, tmp_path):
        code = "def complex(a, b = 1, *rest, key:, **opts, &blk)\n  a\nend\n"
        result = self._parse(parser, tmp_path, code)
        fn = next(f for f in result["functions"] if f["name"] == "complex")
        assert fn["args"] == ["a", "b", "*rest", "key", "**opts", "&blk"]

    def test_method_without_parameters(self, parser, tmp_path):
        result = self._parse(parser, tmp_path, "def none\n  1\nend\n")
        fn = next(f for f in result["functions"] if f["name"] == "none")
        assert fn["args"] == []

    def test_method_name_is_never_treated_as_a_parameter(self, parser, tmp_path):
        result = self._parse(parser, tmp_path, "def solo(x)\n  x\nend\n")
        fn = next(f for f in result["functions"] if f["name"] == "solo")
        assert "solo" not in fn["args"]
