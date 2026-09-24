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

    # #1526: bindings no longer collapse into one bare-module row — the
    # module lives in `source`, the binding in `name`.
    import_sources = {imp["source"] for imp in result["imports"]}
    assert "fs" in import_sources or "path" in import_sources


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


def test_parse_javascript_calls_inside_anonymous_callbacks(js_parser, temp_test_dir):
    """Regression test for #1570 — calls inside anonymous callbacks in JS must attribute context to nearest named enclosing function."""
    code = """
const handleRequest = (req, res) => {
  setTimeout(function() {
    processError(req, res);
  }, 1000);
};
function processError() {}
"""
    f = temp_test_dir / "probe.js"
    f.write_text(code)

    result = js_parser.parse(f)

    calls_by_name = {call["name"]: call for call in result["function_calls"]}
    assert "processError" in calls_by_name
    err_call = calls_by_name["processError"]
    assert err_call["context"] is not None
    assert err_call["context"][0] == "handleRequest"


def test_parse_javascript_calls_inside_class_method_callbacks(js_parser, temp_test_dir):
    """Calls inside class method callbacks must attribute context to the method."""
    code = """
class DataService {
  fetchItems() {
    api.get('/items').then((response) => {
      handleSuccess(response);
    });
  }
}
function handleSuccess() {}
"""
    f = temp_test_dir / "service.js"
    f.write_text(code)

    result = js_parser.parse(f)

    calls_by_name = {call["name"]: call for call in result["function_calls"]}
    assert "handleSuccess" in calls_by_name
    success_call = calls_by_name["handleSuccess"]
    assert success_call["context"] is not None
    assert success_call["context"][0] == "fetchItems"

class TestEsImportBindings:
    """#1526: import_clause is an unnamed child, so every ES import used to
    collapse into one bare-module row, losing named/default/namespace
    bindings."""

    def _imports(self, tmp_path, code):
        from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager
        from codegraphcontext.tools.languages.javascript import JavascriptTreeSitterParser
        from unittest.mock import MagicMock
        mgr = get_tree_sitter_manager()
        w = MagicMock()
        w.language_name = "javascript"
        w.language = mgr.get_language_safe("javascript")
        w.parser = mgr.create_parser("javascript")
        f = tmp_path / "sample.js"
        f.write_text(code, encoding="utf-8")
        return JavascriptTreeSitterParser(w).parse(str(f))["imports"]

    def test_named_imports_produce_one_row_per_binding(self, tmp_path):
        rows = self._imports(tmp_path, "import { useState as us, useEffect } from 'react';\n")
        assert {(r["name"], r["source"], r["alias"]) for r in rows} == {
            ("useState", "react", "us"),
            ("useEffect", "react", None),
        }

    def test_default_and_namespace_imports(self, tmp_path):
        rows = self._imports(tmp_path, "import React from 'react';\nimport * as fs from 'fs';\n")
        assert ("default", "react", "React") in {(r["name"], r["source"], r["alias"]) for r in rows}
        assert ("*", "fs", "fs") in {(r["name"], r["source"], r["alias"]) for r in rows}

    def test_combined_default_and_named_clause(self, tmp_path):
        rows = self._imports(tmp_path, "import Def, { named } from 'mod';\n")
        assert {(r["name"], r["alias"]) for r in rows} == {("default", "Def"), ("named", None)}

    def test_side_effect_import_stays_bare(self, tmp_path):
        rows = self._imports(tmp_path, "import 'polyfill';\n")
        assert rows == [{"name": "polyfill", "source": "polyfill", "alias": None,
                         "line_number": 1, "lang": "javascript"}]
