import pytest

from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser


def test_tree_sitter_parser_rejects_unknown_language_before_loading_grammar():
    with pytest.raises(ValueError, match="Unsupported language parser: pythno"):
        TreeSitterParser("pythno")

