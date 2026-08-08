"""C/C++ functions returning a pointer or reference (#1524).

The queries nested `pointer_declarator` *inside* `function_declarator`. The
real AST is the reverse — a pointer return type wraps the function declarator
from the outside:

    char* f() { }
    function_definition > pointer_declarator > function_declarator > identifier

So no function returning `T*`, `T**` or `T&` matched. Because `pre_scan_c` and
`pre_scan_cpp` carried their own copies of the same inverted shape, those
functions were missing as *call targets* too, not just as nodes.
"""

import pytest
from unittest.mock import MagicMock

from codegraphcontext.tools.languages.c import CTreeSitterParser, pre_scan_c
from codegraphcontext.tools.languages.cpp import CppTreeSitterParser, pre_scan_cpp
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


def _wrapper(lang):
    manager = get_tree_sitter_manager()
    w = MagicMock()
    w.language_name = lang
    w.language = manager.get_language_safe(lang)
    w.parser = manager.create_parser(lang)
    return w


C_SOURCE = """char* dup_str(const char* s) { return 0; }
int plain(void) { return 0; }
char** grid(void) { return 0; }
"""

CPP_SOURCE = """#include <string>
class Buf { public: char* data(); int size(); };
char* Buf::data() { return nullptr; }
int Buf::size() { return 0; }
std::string* make() { return nullptr; }
int plain() { return 0; }
int& ref() { static int x; return x; }
char** dd() { return nullptr; }
"""


class TestCPointerReturns:
    def _parse(self, tmp_path):
        f = tmp_path / "a.c"
        f.write_text(C_SOURCE, encoding="utf-8")
        return f, CTreeSitterParser(_wrapper("c")).parse(str(f))

    def test_pointer_returning_functions_are_extracted(self, tmp_path):
        _, result = self._parse(tmp_path)
        names = {fn["name"] for fn in result["functions"]}
        assert {"dup_str", "plain", "grid"} <= names

    def test_double_pointer_return(self, tmp_path):
        _, result = self._parse(tmp_path)
        assert "grid" in {fn["name"] for fn in result["functions"]}

    def test_pre_scan_registers_them_as_call_targets(self, tmp_path):
        """pre_scan builds the cross-file name map. Missing here means the
        function is unresolvable as a callee even once it becomes a node."""
        f, _ = self._parse(tmp_path)
        assert {"dup_str", "grid", "plain"} <= set(pre_scan_c([f], _wrapper("c")))


class TestCppPointerAndReferenceReturns:
    def _parse(self, tmp_path):
        f = tmp_path / "b.cpp"
        f.write_text(CPP_SOURCE, encoding="utf-8")
        return f, CppTreeSitterParser(_wrapper("cpp")).parse(str(f))

    @pytest.mark.parametrize("name", ["data", "size", "make", "plain", "ref", "dd"])
    def test_every_return_shape_is_extracted(self, tmp_path, name):
        _, result = self._parse(tmp_path)
        assert name in {fn["name"] for fn in result["functions"]}

    def test_out_of_line_pointer_method_keeps_its_class(self, tmp_path):
        """`char* Buf::data()` is pointer_declarator > function_declarator >
        qualified_identifier — the class context must survive the extra wrap."""
        _, result = self._parse(tmp_path)
        data = next(fn for fn in result["functions"] if fn["name"] == "data")
        assert data.get("class_context") == "Buf"

    def test_pre_scan_registers_them_as_call_targets(self, tmp_path):
        f, _ = self._parse(tmp_path)
        found = set(pre_scan_cpp([f], _wrapper("cpp")))
        assert {"data", "make", "ref", "plain"} <= found
        assert "Buf::data" in found, "qualified form must survive the pointer wrap"
