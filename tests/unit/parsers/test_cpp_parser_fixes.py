"""Regression tests for six independent bugs in the C++ tree-sitter parser.

Each bug produced incorrect graph data or silently dropped code elements. Every
bug gets a test pinning the fixed behaviour, plus preservation tests pinning the
neighbouring behaviour the fix must not disturb.

Fixes live in `src/codegraphcontext/tools/languages/cpp.py`.
"""

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


def _parse(cpp_parser, temp_test_dir, code, name="sample.cpp"):
    f = temp_test_dir / name
    f.write_text(code, encoding="utf-8")
    return cpp_parser.parse(f)


# --- Bug 1: local quoted includes kept their surrounding double quotes,
# because _find_imports stripped only '<>' and not '"'. ---

def test_local_quoted_include_strips_quotes(cpp_parser, temp_test_dir):
    result = _parse(cpp_parser, temp_test_dir, '#include "local.h"\n')

    names = [i["name"] for i in result["imports"]]
    assert names == ["local.h"]
    assert all('"' not in n for n in names)


def test_system_include_still_strips_angle_brackets(cpp_parser, temp_test_dir):
    """Preservation: the '<>' stripping that already worked must keep working."""
    result = _parse(
        cpp_parser, temp_test_dir, '#include <stdio.h>\n#include "local.h"\n'
    )

    assert [i["name"] for i in result["imports"]] == ["stdio.h", "local.h"]


# --- Bug 2: an initialized declaration reported type None, because node.parent
# is the init_declarator (which has no 'type' field), not the declaration. ---

def test_initialized_variable_reports_its_type(cpp_parser, temp_test_dir):
    result = _parse(cpp_parser, temp_test_dir, "int x = 5;\ndouble ratio = 1.5;\n")

    variables = {v["name"]: v for v in result["variables"]}
    assert variables["x"]["type"] == "int"
    assert variables["x"]["value"] == "5"
    assert variables["ratio"]["type"] == "double"


def test_class_field_declaration_keeps_type_and_context(cpp_parser, temp_test_dir):
    """Preservation: field_declaration carries 'type' on the node itself, not on
    a parent, so the Bug 2 fix must not walk up an extra level for fields."""
    code = """
class Foo {
    int m_count;
    double m_ratio;
};
"""
    result = _parse(cpp_parser, temp_test_dir, code)

    variables = {v["name"]: v for v in result["variables"]}
    assert variables["m_count"]["type"] == "int"
    assert variables["m_count"]["class_context"] == "Foo"
    assert variables["m_ratio"]["type"] == "double"


# --- Bug 3: a declaration with no initializer was never captured at all,
# because the variables query only matched init_declarator shapes. ---

def test_uninitialized_variable_is_captured(cpp_parser, temp_test_dir):
    result = _parse(cpp_parser, temp_test_dir, "int count;\nint initialized = 7;\n")

    variables = {v["name"]: v for v in result["variables"]}
    assert "count" in variables, "uninitialized declaration must be captured"
    assert variables["count"]["type"] == "int"
    assert variables["count"]["value"] is None
    # the initialized sibling must not be dropped, and nothing duplicated
    assert variables["initialized"]["type"] == "int"
    assert [v["name"] for v in result["variables"]].count("count") == 1


# --- Bug 4: a method defined inline in a class body got no class_context, so
# the indexer could not build the Class-[:CONTAINS]->Function edge for it. ---

def test_inline_class_method_gets_class_context(cpp_parser, temp_test_dir):
    code = """
class Foo {
public:
    void bar() {}
    int baz(int n) { return n; }
};
"""
    result = _parse(cpp_parser, temp_test_dir, code)

    functions = {fn["name"]: fn for fn in result["functions"]}
    assert functions["bar"].get("class_context") == "Foo"
    assert functions["baz"].get("class_context") == "Foo"


def test_inline_method_in_nested_class_uses_innermost_class(cpp_parser, temp_test_dir):
    code = """
class Outer {
public:
    class Inner {
    public:
        void deep() {}
    };
    void shallow() {}
};
"""
    result = _parse(cpp_parser, temp_test_dir, code)

    functions = {fn["name"]: fn for fn in result["functions"]}
    assert functions["deep"].get("class_context") == "Inner"
    assert functions["shallow"].get("class_context") == "Outer"


def test_file_scope_function_has_no_class_context(cpp_parser, temp_test_dir):
    """Preservation: the ancestor walk added for Bug 4 must not invent a class
    context for functions that genuinely have none."""
    code = """
void process() {}

class Foo {
public:
    void member() {}
};
"""
    result = _parse(cpp_parser, temp_test_dir, code)

    functions = {fn["name"]: fn for fn in result["functions"]}
    assert functions["process"].get("class_context") is None
    assert functions["member"].get("class_context") == "Foo"


def test_qualified_method_context_survives_the_ancestor_walk(cpp_parser, temp_test_dir):
    """Preservation: '::' splitting must still win over the ancestor walk."""
    result = _parse(cpp_parser, temp_test_dir, "void Foo::bar() {}\n")

    bar = next(fn for fn in result["functions"] if fn["name"] == "bar")
    assert bar.get("class_context") == "Foo"


# --- Bug 5: function-like macros use the preproc_function_def node type, which
# the preproc_def-only query never matched, so they were missed entirely. ---

def test_function_like_macro_is_extracted(cpp_parser, temp_test_dir):
    code = """
#define SQUARE(x) ((x)*(x))
#define ADD(a, b) ((a)+(b))
#define NOARGS() 0
"""
    result = _parse(cpp_parser, temp_test_dir, code)

    macros = {m["name"]: m for m in result["macros"]}
    assert "SQUARE" in macros
    assert macros["SQUARE"]["params"] == ["x"]
    assert macros["ADD"]["params"] == ["a", "b"]
    assert macros["NOARGS"]["params"] == []


def test_object_like_macro_still_extracted(cpp_parser, temp_test_dir):
    """Preservation: adding the preproc_function_def alternative must not
    disturb the object-like macros that already matched."""
    code = """
#define MAX_SIZE 100
#define SQUARE(x) ((x)*(x))
"""
    result = _parse(cpp_parser, temp_test_dir, code)

    macros = {m["name"]: m for m in result["macros"]}
    assert "MAX_SIZE" in macros
    assert "SQUARE" in macros


# --- Bug 6: end_line was one past the real last line, because tree-sitter's
# end_point already rolls to column 0 of the next row for the trailing newline
# and the code then added 1 on top of that. ---

def test_single_line_macro_end_line_is_its_own_line(cpp_parser, temp_test_dir):
    result = _parse(cpp_parser, temp_test_dir, "#define MAX 100\n")

    macro = result["macros"][0]
    assert macro["line_number"] == 1
    assert macro["end_line"] == 1


def test_multi_line_macro_end_line_covers_continuations(cpp_parser, temp_test_dir):
    """Preservation: a line-continued macro must still span to its real end."""
    code = "#define SUM(a, b) \\\n    ((a) + \\\n     (b))\n"
    result = _parse(cpp_parser, temp_test_dir, code)

    macro = next(m for m in result["macros"] if m["name"] == "SUM")
    assert macro["line_number"] == 1
    assert macro["end_line"] == 3


def test_lambda_assignment_still_extracted_as_function(cpp_parser, temp_test_dir):
    """Preservation: the variables query changes must not steal lambdas away
    from _find_lambda_assignments or duplicate them as plain variables."""
    result = _parse(
        cpp_parser, temp_test_dir, "auto fn = [](int x) { return x; };\n"
    )

    assert any(fn["name"] == "fn" for fn in result["functions"])
    assert "fn" not in [v["name"] for v in result["variables"]]


def test_all_six_bug_scenarios_in_one_file(cpp_parser, temp_test_dir):
    """Integration: every bug scenario together, to catch cross-interference."""
    code = """#include <stdio.h>
#include "local.h"
#define MAX 100
#define SQUARE(x) ((x)*(x))

int total = 5;
int pending;

class Foo {
    int m_count;
public:
    void bar() {}
};

void Foo::other() {}

void free_fn() {}
"""
    result = _parse(cpp_parser, temp_test_dir, code, name="all_bugs.cpp")

    assert [i["name"] for i in result["imports"]] == ["stdio.h", "local.h"]

    macros = {m["name"]: m for m in result["macros"]}
    assert macros["MAX"]["end_line"] == 3
    assert macros["SQUARE"]["params"] == ["x"]

    variables = {v["name"]: v for v in result["variables"]}
    assert variables["total"]["type"] == "int"
    assert variables["pending"]["type"] == "int"
    assert variables["m_count"]["class_context"] == "Foo"

    functions = {fn["name"]: fn for fn in result["functions"]}
    assert functions["bar"]["class_context"] == "Foo"
    assert functions["other"]["class_context"] == "Foo"
    assert functions["free_fn"].get("class_context") is None


def test_lambda_parameters_are_extracted(cpp_parser, tmp_path):
    """#1527 case 5: lambda assignments always produced args: []."""
    code = (
        "#include <string>\n"
        "auto add = [](int a, int b){ return a + b; };\n"
        "auto greet = [](const std::string& name, char* buf){ return name; };\n"
        "auto zero = [](){ return 0; };\n"
    )
    f = tmp_path / "lambdas.cpp"
    f.write_text(code, encoding="utf-8")
    functions = {fn["name"]: fn for fn in cpp_parser.parse(str(f))["functions"]}
    # C++ args follow the project's "type name" convention, same as
    # regular function_definitions extracted through the shared helper.
    assert functions["add"]["args"] == ["int a", "int b"]
    # The type field excludes qualifiers/pointer declarators, so refs and
    # pointers render as the extractor has always rendered them for
    # function_definitions ("std::string & name", "char buf").
    assert functions["greet"]["args"] == ["std::string & name", "char buf"]
    assert functions["zero"]["args"] == []
