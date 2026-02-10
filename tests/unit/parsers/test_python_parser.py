
import pytest
import json
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager
from codegraphcontext.tools.languages.python import PythonTreeSitterParser
from unittest.mock import MagicMock

class TestPythonParser:
    """
    Test the Python Parser logic.
    """

    @pytest.fixture(scope="class")
    def parser(self):
        # We need to construct a PythonTreeSitterParser
        # It takes a wrapper. Let's mock the wrapper or create a real one.
        # Real one:
        manager = get_tree_sitter_manager()
        
        # Create a mock wrapper that behaves like the one expected by PythonTreeSitterParser
        wrapper = MagicMock()
        wrapper.language_name = "python"
        wrapper.language = manager.get_language_safe("python")
        wrapper.parser = manager.create_parser("python")
        
        return PythonTreeSitterParser(wrapper)

    def test_parse_simple_function(self, parser, temp_test_dir):
        """Parse a simple python file and verify output."""
        code = "def hello():\n    print('world')"
        f = temp_test_dir / "test.py"
        f.write_text(code)

        # Act
        result = parser.parse(str(f))

        # Assert
        # We expect a list of nodes/edges or a structure containing them
        # This structure depends on the actual return type of .parse()
        # For now, I will assert keys exist.
        
        print(f"DEBUG: Parser result keys: {result.keys()}")
        
        assert "functions" in result
        funcs = result["functions"]
        assert len(funcs) == 1
        assert funcs[0]["name"] == "hello"

    def test_parse_class_with_method(self, parser, temp_test_dir):
        """Parse a class with a method."""
        code = """
class Greeter:
    def greet(self, name):
        return f"Hello {name}"
"""
        f = temp_test_dir / "classes.py"
        f.write_text(code)

        result = parser.parse(str(f))

        assert "classes" in result
        classes = result["classes"]
        assert len(classes) == 1
        assert classes[0]["name"] == "Greeter"

        # Check methods if they are nested or separate
        # Depending on implementation, methods might be in 'functions' with parent info
        # or inside 'classes'.
        # Let's assume they are captured.

