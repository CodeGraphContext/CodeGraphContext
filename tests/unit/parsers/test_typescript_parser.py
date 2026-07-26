from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.typescript import TypescriptTreeSitterParser, pre_scan_typescript
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def ts_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("typescript"):
        pytest.skip("TypeScript tree-sitter grammar is not available in this environment")

    wrapper = MagicMock()
    wrapper.language_name = "typescript"
    wrapper.language = manager.get_language_safe("typescript")
    wrapper.parser = manager.create_parser("typescript")
    return TypescriptTreeSitterParser(wrapper)


def test_tree_sitter_dispatches_typescript_parser():
    parser = TreeSitterParser("typescript")
    assert isinstance(parser.language_specific_parser, TypescriptTreeSitterParser)


def test_parse_typescript_functions_and_classes(ts_parser, temp_test_dir):
    code = """
import { readFile } from 'fs';
import path from 'path';

interface Animal {
    name: string;
    speak(): void;
}

class Dog implements Animal {
    name: string;

    constructor(name: string) {
        this.name = name;
    }

    speak(): void {
        console.log(this.name);
    }
}

function greet(name: string): string {
    return 'Hello, ' + name;
}

const add = (a: number, b: number): number => {
    return a + b;
};
"""
    f = temp_test_dir / "sample.ts"
    f.write_text(code)

    result = ts_parser.parse(f)

    assert result["lang"] == "typescript"

    function_names = {fn["name"] for fn in result["functions"]}
    assert "greet" in function_names
    assert "add" in function_names

    class_names = {cls["name"] for cls in result["classes"]}
    assert "Dog" in class_names

    import_names = {imp["name"] for imp in result["imports"]}
    assert "fs" in import_names or "path" in import_names


def test_parse_typescript_function_calls(ts_parser, temp_test_dir):
    code = """
function main(): void {
    const result = greet('world');
    console.log(result);
}

function greet(name: string): string {
    return 'Hello, ' + name;
}
"""
    f = temp_test_dir / "calls.ts"
    f.write_text(code)

    result = ts_parser.parse(f)

    call_names = {call["name"] for call in result["function_calls"]}
    assert "greet" in call_names or "log" in call_names


def test_pre_scan_typescript_indexes_functions(temp_test_dir):
    code = """
function helper(): void {}

function main(): void {
    helper();
}
"""
    f = temp_test_dir / "scanner.ts"
    f.write_text(code)

    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "typescript"
    wrapper.language = manager.get_language_safe("typescript")
    wrapper.parser = manager.create_parser("typescript")

    imports_map = pre_scan_typescript([f], wrapper)

    assert "helper" in imports_map or "main" in imports_map
