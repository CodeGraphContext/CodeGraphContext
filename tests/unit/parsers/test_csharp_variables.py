"""C# field and local extraction (#1525).

`variables` was hardcoded to `[]` and `CSHARP_QUERIES` had no `variables`
entry at all, so C# produced zero `Variable` nodes. The larger cost was
downstream: `resolution/calls.py` uses local-variable declarations to infer a
receiver's type, so `var svc = new UserService(); svc.Save();` could not
resolve `Save` to `UserService.Save`.
"""

import pytest
from unittest.mock import MagicMock

from codegraphcontext.tools.languages.csharp import CSharpTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

SOURCE = """class UserService {
  private int _count = 1;
  public string Name;
  private static readonly int A = 1, B = 2;
  void Save() {
    int total = 0;
    var svc = new UserService();
  }
}
"""


class TestCSharpVariables:
    @pytest.fixture(scope="class")
    def parser(self):
        manager = get_tree_sitter_manager()
        w = MagicMock()
        w.language_name = "c_sharp"
        w.language = manager.get_language_safe("c_sharp")
        w.parser = manager.create_parser("c_sharp")
        return CSharpTreeSitterParser(w)

    @pytest.fixture
    def by_name(self, parser, tmp_path):
        f = tmp_path / "a.cs"
        f.write_text(SOURCE, encoding="utf-8")
        return {v["name"]: v for v in parser.parse(str(f))["variables"]}

    def test_variables_are_no_longer_empty(self, by_name):
        assert by_name, "C# produced no Variable rows at all"

    def test_fields_are_extracted(self, by_name):
        assert {"_count", "Name"} <= set(by_name)
        assert by_name["_count"]["type"] == "int"
        assert by_name["Name"]["type"] == "string"

    def test_locals_are_extracted(self, by_name):
        assert {"total", "svc"} <= set(by_name)

    def test_multiple_declarators_share_one_type(self, by_name):
        """`int A = 1, B = 2;` is one declaration with two declarators."""
        assert {"A", "B"} <= set(by_name)
        assert by_name["A"]["type"] == by_name["B"]["type"] == "int"
        assert by_name["A"]["value"] == "1"
        assert by_name["B"]["value"] == "2"

    def test_locals_carry_their_enclosing_method(self, by_name):
        assert by_name["total"]["context"] == "Save"
        assert by_name["svc"]["context"] == "Save"

    def test_fields_have_no_method_context_but_keep_their_class(self, by_name):
        assert by_name["_count"]["context"] is None
        assert by_name["_count"]["class_context"] == "UserService"
        assert by_name["svc"]["class_context"] == "UserService"

    def test_initialiser_is_captured(self, by_name):
        """tree-sitter-c-sharp has no `equals_value_clause` — the value is a
        direct sibling after the `=` token."""
        assert by_name["_count"]["value"] == "1"
        assert by_name["total"]["value"] == "0"
        assert by_name["Name"]["value"] is None

    def test_constructor_initialiser_is_preserved_for_type_inference(self, by_name):
        """The receiver-type inference case: `var svc = new UserService()`
        needs both the declared name and its initialiser."""
        svc = by_name["svc"]
        assert svc["type"] == "var"
        assert svc["value"] == "new UserService()"
