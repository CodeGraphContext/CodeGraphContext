from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.cpp import CppTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def cpp_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("cpp"):
        pytest.skip("C++ tree-sitter grammar is not available in this environment")

    wrapper = MagicMock()
    wrapper.language_name = "cpp"
    wrapper.language = manager.get_language_safe("cpp")
    wrapper.parser = manager.create_parser("cpp")
    return CppTreeSitterParser(wrapper)


def test_enum_parsing(cpp_parser, temp_test_dir):
    code = """
enum Color { RED, GREEN, BLUE };

enum class Status { OK = 0, ERROR = 1 };
"""
    f = temp_test_dir / "enums.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    enum_names = [e["name"] for e in result.get("enums", [])]
    assert "Color" in enum_names
    assert "Status" in enum_names


def test_file_with_enums_and_classes(cpp_parser, temp_test_dir):
    """Ensure files containing both enums and classes parse without errors."""
    code = """
enum DataType { INT = 0, VARCHAR = 1 };

class Foo {
public:
    void bar() {}
};
"""
    f = temp_test_dir / "mixed.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    assert any(c["name"] == "Foo" for c in result["classes"])
    assert any(e["name"] == "DataType" for e in result.get("enums", []))
