
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
        f.write_text(code, encoding="utf-8")

        # Act
        result = parser.parse(str(f))
        assert isinstance(result, dict)

        # Assert
        # We expect a list of nodes/edges or a structure containing them
        # This structure depends on the actual return type of .parse()
        # For now, I will assert keys exist.
        
        print(f"DEBUG: Parser result keys: {result.keys()}")
        
        assert "functions" in result
        funcs = result["functions"]
        # The parser appends a synthetic "<module>" frame for module-level
        # context (see _attach_module_context); exclude it when asserting on
        # user-defined functions.
        user_funcs = [f for f in funcs if f["name"] != "<module>"]
        assert len(user_funcs) == 1
        assert user_funcs[0]["name"] == "hello"

    def test_module_level_call_uses_module_context(self, parser, temp_test_dir):
        """Top-level executable calls should be linked from a synthetic module frame."""
        code = "from pkg.utils import helper\n\nresult = helper()\n"
        f = temp_test_dir / "__main__.py"
        f.write_text(code, encoding="utf-8")

        result = parser.parse(str(f))
        assert isinstance(result, dict)

        module_func = next(
            func for func in result["functions"]
            if func["name"] == "<module>"
        )
        helper_call = next(
            call for call in result["function_calls"]
            if call["name"] == "helper"
        )

        assert module_func["line_number"] == 1
        assert module_func["context_type"] == "module"
        assert helper_call["context"] == ("<module>", "module", 1)

    def test_duplicate_import_keeps_earliest_source_line(self, parser, temp_test_dir):
        """Duplicate imports should be stable regardless of capture traversal order."""
        code = (
            "import os\n\n"
            "def env_based_import():\n"
            "    if os.getenv('USE_UJSON') == '1':\n"
            "        try:\n"
            "            import ujson as json\n"
            "        except Exception:\n"
            "            import json\n"
            "    else:\n"
            "        import json\n"
            "    return json.dumps({'a': 1})\n"
        )
        f = temp_test_dir / "imports.py"
        f.write_text(code)

        result = parser.parse(str(f))
        json_import = next(
            imp for imp in result["imports"]
            if imp["name"] == "json" and imp["full_import_name"] == "json"
        )

        assert json_import["line_number"] == 8

    def test_nested_module_level_calls_attribute_to_outer_callee(self, parser, temp_test_dir):
        """Nested call expressions attribute inner calls to the outer callee."""
        code = (
            "def f1(x): return x + 1\n"
            "def f2(x): return x * 2\n"
            "def f3(x): return x - 3\n\n"
            "result = f1(f2(f3(10)))\n"
        )
        f = temp_test_dir / "function_chains.py"
        f.write_text(code)

        result = parser.parse(str(f))
        calls = {call["name"]: call for call in result["function_calls"]}

        assert calls["f1"]["context"] == ("<module>", "module", 1)
        assert calls["f2"]["context"][0] == "f1"
        assert calls["f2"]["context"][1] == "nested_call"
        assert calls["f3"]["context"][0] == "f2"
        assert calls["f3"]["context"][1] == "nested_call"

    def test_nested_call_inside_method_uses_enclosing_function_context(self, parser, temp_test_dir):
        """Calls nested inside method arguments (e.g. list.append(helper())) should
        attribute to the enclosing function, not the method name."""
        code = (
            "def _helper(x): return x * 2\n"
            "def process(data, results):\n"
            "    results.append(_helper(data))\n"
        )
        f = temp_test_dir / "method_nested.py"
        f.write_text(code)

        result = parser.parse(str(f))
        calls = [c for c in result["function_calls"] if c["name"] == "_helper"]
        assert len(calls) == 1
        helper_call = calls[0]
        # _helper's caller should be "process" (the enclosing function),
        # NOT "append" (which is a method, not a Function node in the graph).
        assert helper_call["context"][0] == "process"
        assert helper_call["context"][1] == "function_definition"

    def test_method_name_collision_uses_enclosing_function_context(self, parser, temp_test_dir):
        """When a local function has the same name as a method call,
        nested calls inside the method's arguments should still
        attribute to the enclosing function, not the colliding local function."""
        code = (
            "def append(item): return item\n"
            "def process(data, results):\n"
            "    results.append(append(data))\n"
        )
        f = temp_test_dir / "collision.py"
        f.write_text(code)
        result = parser.parse(str(f))
        calls = [c for c in result["function_calls"] if c["name"] == "append"]
        # Find the direct call `append(data)` inside `results.append(...)`
        # It should have context pointing to "process", not "append"
        inner_append_call = [c for c in calls if c["full_name"] == "append"]
        assert len(inner_append_call) == 1
        assert inner_append_call[0]["context"][0] == "process"

    def test_multiline_from_import_captures_all_names(self, parser, temp_test_dir):
        """Multi-line from...import(...) must capture ALL imported names,
        not just the first one (child_by_field_name vs children_by_field_name)."""
        code = (
            "from pkg.utils import (\n"
            "    VERSION,\n"
            "    _configure_stdio,\n"
            "    _get_logs_dir,\n"
            "    _setup_logging,\n"
            "    ROOT,\n"
            ")\n"
        )
        f = temp_test_dir / "multi_import.py"
        f.write_text(code)
        result = parser.parse(str(f))
        names = {imp["name"] for imp in result["imports"]}
        assert names == {"VERSION", "_configure_stdio", "_get_logs_dir", "_setup_logging", "ROOT"}
        # Also verify full_import_name
        full_names = {imp["full_import_name"] for imp in result["imports"]}
        assert "pkg.utils._configure_stdio" in full_names
        assert "pkg.utils.ROOT" in full_names

    def test_multiline_from_import_with_alias(self, parser, temp_test_dir):
        """from...import with aliases must capture both name and alias."""
        code = (
            "from pkg.utils import (\n"
            "    VERSION as VER,\n"
            "    configure as setup,\n"
            ")\n"
        )
        f = temp_test_dir / "alias_import.py"
        f.write_text(code)
        result = parser.parse(str(f))
        imports_by_name = {imp["name"]: imp for imp in result["imports"]}
        assert "VERSION" in imports_by_name
        assert imports_by_name["VERSION"]["alias"] == "VER"
        assert imports_by_name["VERSION"]["full_import_name"] == "pkg.utils.VERSION"
        assert "configure" in imports_by_name
        assert imports_by_name["configure"]["alias"] == "setup"
        assert imports_by_name["configure"]["full_import_name"] == "pkg.utils.configure"

    def test_parse_class_with_method(self, parser, temp_test_dir):
        """Parse a class with a method."""
        code = """
class Greeter:
    def greet(self, name):
        return f"Hello {name}"
"""
        f = temp_test_dir / "classes.py"
        f.write_text(code, encoding="utf-8")

        result = parser.parse(str(f))
        assert isinstance(result, dict)

        assert "classes" in result
        classes = result["classes"]
        assert len(classes) == 1
        assert classes[0]["name"] == "Greeter"

        # Check methods if they are nested or separate
        # Depending on implementation, methods might be in 'functions' with parent info
        # or inside 'classes'.
        # Let's assume they are captured.
