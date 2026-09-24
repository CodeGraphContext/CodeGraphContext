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

    # #1526: bindings no longer collapse into one bare-module row — the
    # module lives in `source`, the binding in `name`.
    import_sources = {imp["source"] for imp in result["imports"]}
    assert "fs" in import_sources or "path" in import_sources


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


def test_parse_typescript_calls_inside_anonymous_callbacks(ts_parser, temp_test_dir):
    """Regression test for #1570 — calls inside anonymous callbacks must attribute context to nearest named enclosing function."""
    code = """
export const requestTimeout = (req, res, next) => {
  setTimeout(() => {
    customErrorHandler(req, res);
  }, 1000);
};
function customErrorHandler(...args: unknown[]) {}
"""
    f = temp_test_dir / "probe.ts"
    f.write_text(code)

    result = ts_parser.parse(f)

    calls_by_name = {call["name"]: call for call in result["function_calls"]}
    assert "customErrorHandler" in calls_by_name
    custom_error_call = calls_by_name["customErrorHandler"]
    assert custom_error_call["context"] is not None
    assert custom_error_call["context"][0] == "requestTimeout"


def test_parse_typescript_calls_inside_multilevel_nested_callbacks(ts_parser, temp_test_dir):
    """Ensure multi-level nested callbacks walk up to the enclosing named function."""
    code = """
function outerTask() {
  [1, 2, 3].forEach(() => {
    Promise.resolve().then(function() {
      setTimeout(() => {
        innerAction();
      }, 10);
    });
  });
}
function innerAction() {}
"""
    f = temp_test_dir / "nested_probe.ts"
    f.write_text(code)

    result = ts_parser.parse(f)

    calls_by_name = {call["name"]: call for call in result["function_calls"]}
    assert "innerAction" in calls_by_name
    inner_call = calls_by_name["innerAction"]
    assert inner_call["context"] is not None
    assert inner_call["context"][0] == "outerTask"


def test_parse_typescript_top_level_anonymous_iife(ts_parser, temp_test_dir):
    """Top-level anonymous IIFE should return None context without error."""
    code = """
(() => {
  topLevelInit();
})();
"""
    f = temp_test_dir / "iife.ts"
    f.write_text(code)

    result = ts_parser.parse(f)

    calls_by_name = {call["name"]: call for call in result["function_calls"]}
    assert "topLevelInit" in calls_by_name
    init_call = calls_by_name["topLevelInit"]
    assert init_call["context"] == (None, None, None)



def test_es_import_bindings_extracted_ts(temp_test_dir):
    """#1526: named/default/namespace bindings must not collapse to one row."""
    from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager
    from codegraphcontext.tools.languages.typescript import TypescriptTreeSitterParser
    from unittest.mock import MagicMock
    from pathlib import Path
    mgr = get_tree_sitter_manager()
    w = MagicMock()
    w.language_name = "typescript"
    w.language = mgr.get_language_safe("typescript")
    w.parser = mgr.create_parser("typescript")
    f = Path(temp_test_dir) / "sample.ts"
    f.write_text(
        "import React from 'react';\n"
        "import * as fs from 'fs';\n"
        "import { useState as us, useEffect } from 'react';\n",
        encoding="utf-8",
    )
    rows = TypescriptTreeSitterParser(w).parse(str(f))["imports"]
    assert {(r["name"], r["source"], r["alias"]) for r in rows} == {
        ("default", "react", "React"),
        ("*", "fs", "fs"),
        ("useState", "react", "us"),
        ("useEffect", "react", None),
    }
