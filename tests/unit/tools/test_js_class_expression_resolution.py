"""Issue #1864: JS class expressions (``const X = class {...}``) get a Class node.

Without one, ``new X()`` / ``X.m()`` resolved to a same-named class in an
unrelated, unimported file and were labelled EXTRACTED.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
from codegraphcontext.tools.indexing.resolution.inheritance import (
    build_inheritance_and_csharp_files,
)
from codegraphcontext.tools.languages.javascript import (
    JavascriptTreeSitterParser,
    pre_scan_javascript,
)
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


SHAPES_JS = """\
const Shape = class {
  area() { return 0; }
  static create() { return new Shape(); }
};

function useShape() {
  const s = new Shape();
  Shape.create();
  return s.area();
}
"""

OTHER_JS = """\
export class Shape {
  area() { return 42; }
  static create() { return new Shape(); }
}
"""

INHERIT_JS = """\
class Base {
  greet() { return 'base'; }
}

const Mid = class extends Base {
  greet() { return super.greet() + '!'; }
};

let Leaf;
Leaf = class Named extends Mid {
  greet() { return super.greet() + '?'; }
};

const ns = {};
ns.Widget = class {
  render() { return 1; }
};

function build() {
  new Leaf();
  return new ns.Widget();
}
"""

DUPLICATE_JS = """\
var Thing = class {
  run() { return this.step(); }
  step() { return 1; }
};

function later() {
  Thing = class {
    run() { return this.step(); }
    step() { return 2; }
  };
}
"""


@pytest.fixture(scope="module")
def js_parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "javascript"
    wrapper.language = manager.get_language_safe("javascript")
    wrapper.parser = manager.create_parser("javascript")
    return wrapper, JavascriptTreeSitterParser(wrapper)


def _index(js_parser, tmp_path: Path, sources: dict):
    wrapper, parser = js_parser
    paths = []
    for name, code in sources.items():
        path = tmp_path / name
        path.write_text(code)
        paths.append(path)

    files = []
    for path in paths:
        parsed = parser.parse(path)
        files.append({
            "path": path.resolve().as_posix(),
            "lang": "javascript",
            "functions": parsed["functions"],
            "classes": parsed.get("classes", []),
            "function_calls": parsed["function_calls"],
            "imports": parsed.get("imports", []),
            "variables": parsed.get("variables", []),
        })
    imports_map = pre_scan_javascript(paths, wrapper)
    return files, imports_map


def _calls(files, imports_map):
    groups = build_function_call_groups(files, imports_map)
    return [edge for group in groups for edge in group]


def test_class_expression_creates_class_node_named_by_binding(js_parser, tmp_path):
    files, _ = _index(js_parser, tmp_path, {"shapes.js": SHAPES_JS})
    shapes = files[0]

    assert [(c["name"], c["line_number"]) for c in shapes["classes"]] == [("Shape", 1)]
    owners = {fn["name"]: fn.get("class_context") for fn in shapes["functions"]}
    assert owners["area"] == "Shape"
    assert owners["create"] == "Shape"
    assert owners["useShape"] is None


def test_calls_resolve_to_same_file_class_expression_not_unrelated_file(js_parser, tmp_path):
    files, imports_map = _index(
        js_parser, tmp_path, {"shapes.js": SHAPES_JS, "other.js": OTHER_JS}
    )
    shapes_path = files[0]["path"]
    edges = [
        e for e in _calls(files, imports_map)
        if e.get("caller_file_path") == shapes_path
    ]

    targets = {
        (e.get("line_number"), e["called_name"]): e.get("called_file_path")
        for e in edges
    }
    # new Shape() in useShape, Shape.create() in useShape, new Shape() in create
    assert targets[(7, "Shape")] == shapes_path
    assert targets[(8, "create")] == shapes_path
    assert targets[(3, "Shape")] == shapes_path
    assert all(e.get("called_file_path") == shapes_path for e in edges)


def test_class_expression_bindings_inheritance_and_super(js_parser, tmp_path):
    files, imports_map = _index(js_parser, tmp_path, {"inherit.js": INHERIT_JS})
    data = files[0]

    classes = {c["name"]: (c["line_number"], c["bases"]) for c in data["classes"]}
    assert classes == {
        "Base": (1, []),
        "Mid": (5, ["Base"]),
        # Named class expression: the outer binding is what callers use.
        "Leaf": (10, ["Mid"]),
        # Member-expression binding is named by its property.
        "Widget": (15, []),
    }

    inheritance, _ = build_inheritance_and_csharp_files(files, imports_map)
    links = {(row["child_name"], row["parent_name"]) for row in inheritance}
    assert ("Mid", "Base") in links
    assert ("Leaf", "Mid") in links

    edges = _calls(files, imports_map)
    super_targets = {
        e.get("line_number"): (e.get("called_context"), e.get("called_line_number"))
        for e in edges
        if e["called_name"] == "greet"
    }
    assert super_targets[6] == ("Base", 2)
    assert super_targets[11] == ("Mid", 6)

    new_targets = {
        e["called_name"]: e.get("called_line_number")
        for e in edges
        if e.get("line_number") in (20, 21)
    }
    assert new_targets == {"Leaf": 10, "Widget": 15}


def test_duplicate_class_expression_names_keep_distinct_owners(js_parser, tmp_path):
    files, imports_map = _index(js_parser, tmp_path, {"dup.js": DUPLICATE_JS})
    data = files[0]

    assert [(c["name"], c["line_number"]) for c in data["classes"]] == [
        ("Thing", 1),
        ("Thing", 7),
    ]
    owners = {
        (fn["name"], fn["line_number"]): (fn.get("class_context"), fn.get("class_context_line"))
        for fn in data["functions"]
        if fn["name"] in ("run", "step")
    }
    assert owners == {
        ("run", 2): ("Thing", 1),
        ("step", 3): ("Thing", 1),
        ("run", 8): ("Thing", 7),
        ("step", 9): ("Thing", 7),
    }

    this_targets = {
        e.get("line_number"): e.get("called_line_number")
        for e in _calls(files, imports_map)
        if e["called_name"] == "step"
    }
    assert this_targets == {2: 3, 8: 9}
