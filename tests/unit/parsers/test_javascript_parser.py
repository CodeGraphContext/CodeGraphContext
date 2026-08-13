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


def test_parse_javascript_cyclomatic_complexity(js_parser, temp_test_dir):
    code = """
function simple() {
    return 1;
}

function complex(x) {
    if (x > 0) {
        for (let i = 0; i < x; i++) {
            if (i % 2 === 0 && x > 5) {
                console.log(i);
            }
        }
    } else if (x < 0) {
        return -1;
    }
    return 0;
}
"""
    f = temp_test_dir / "complexity.js"
    f.write_text(code)

    result = js_parser.parse(f)

    functions_by_name = {fn["name"]: fn for fn in result["functions"]}

    assert "cyclomatic_complexity" in functions_by_name["simple"]
    assert functions_by_name["simple"]["cyclomatic_complexity"] == 1

    assert functions_by_name["complex"]["cyclomatic_complexity"] > 1


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



def test_parse_javascript_destructured_and_rest_parameters(js_parser, temp_test_dir):
    """Regression test for #1527 — destructured and rest params must be extracted."""
    code = """
function plain(a, b) { return a + b; }
function withDefault(a, b = 10) { return a + b; }
function withRest(a, ...rest) { return rest; }
function withObj({ x, y }) { return x + y; }
function withArr([first, second]) { return first; }
const arrow = ({label}) => label;
"""
    f = temp_test_dir / "params.js"
    f.write_text(code)

    result = js_parser.parse(f)
    funcs = {fn["name"]: fn for fn in result["functions"]}

    assert "a" in funcs["plain"]["args"]
    assert "b" in funcs["plain"]["args"]

    assert "a" in funcs["withDefault"]["args"]
    assert "b" in funcs["withDefault"]["args"]

    assert "a" in funcs["withRest"]["args"]
    rest_params = [p for p in funcs["withRest"]["args"] if p.startswith("...")]
    assert len(rest_params) == 1, f"Expected one rest param, got {funcs['withRest']['args']}"

    # Destructured object — must not silently drop all params
    assert len(funcs["withObj"]["args"]) > 0, "withObj should have at least one param placeholder"

    # Destructured array — must not silently drop all params
    assert len(funcs["withArr"]["args"]) > 0, "withArr should have at least one param placeholder"

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