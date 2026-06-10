from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.javascript import JavascriptTreeSitterParser, pre_scan_javascript
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def js_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("javascript"):
        pytest.skip("JavaScript tree-sitter grammar is not available in this environment")

    wrapper = MagicMock()
    wrapper.language_name = "javascript"
    wrapper.language = manager.get_language_safe("javascript")
    wrapper.parser = manager.create_parser("javascript")
    return JavascriptTreeSitterParser(wrapper)


def test_tree_sitter_dispatches_javascript_parser():
    parser = TreeSitterParser("javascript")
    assert isinstance(parser.language_specific_parser, JavascriptTreeSitterParser)


def test_parse_javascript_functions_and_classes(js_parser, temp_test_dir):
    code = """
import { readFile } from 'fs';
import path from 'path';

class Animal {
    constructor(name) {
        this.name = name;
    }

    speak() {
        console.log(this.name);
    }
}

function greet(name) {
    return 'Hello, ' + name;
}

const add = (a, b) => {
    return a + b;
};
"""
    f = temp_test_dir / "sample.js"
    f.write_text(code)

    result = js_parser.parse(f)

    assert result["lang"] == "javascript"

    function_names = {fn["name"] for fn in result["functions"]}
    assert "greet" in function_names
    assert "add" in function_names

    class_names = {cls["name"] for cls in result["classes"]}
    assert "Animal" in class_names

    import_names = {imp["name"] for imp in result["imports"]}
    assert "fs" in import_names or "path" in import_names


def test_parse_javascript_function_calls(js_parser, temp_test_dir):
    code = """
function main() {
    const result = greet('world');
    console.log(result);
}

function greet(name) {
    return 'Hello, ' + name;
}
"""
    f = temp_test_dir / "calls.js"
    f.write_text(code)

    result = js_parser.parse(f)

    call_names = {call["name"] for call in result["function_calls"]}
    assert "greet" in call_names or "log" in call_names


def test_pre_scan_javascript_indexes_functions(temp_test_dir):
    code = """
function helper() {}

function main() {
    helper();
}
"""
    f = temp_test_dir / "scanner.js"
    f.write_text(code)

    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "javascript"
    wrapper.language = manager.get_language_safe("javascript")
    wrapper.parser = manager.create_parser("javascript")

    imports_map = pre_scan_javascript([f], wrapper)

    assert "helper" in imports_map or "main" in imports_map
