import pytest
from unittest.mock import MagicMock

from codegraphcontext.tools.languages.php import PhpTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


class TestPhpImports:
    """PHP `use` handling.

    The imports query used to capture `use_declaration`, which is the *trait*
    use inside a class body — not a top-level import. That dropped every real
    import and labelled trait uses as imports instead.
    """

    @pytest.fixture(scope="class")
    def parser(self):
        manager = get_tree_sitter_manager()
        wrapper = MagicMock()
        wrapper.language_name = "php"
        wrapper.language = manager.get_language_safe("php")
        wrapper.parser = manager.create_parser("php")
        return PhpTreeSitterParser(wrapper)

    def _imports(self, parser, tmp_path, code):
        f = tmp_path / "sample.php"
        f.write_text(code, encoding="utf-8")
        return parser.parse(str(f))["imports"]

    def test_plain_import(self, parser, tmp_path):
        imports = self._imports(parser, tmp_path, "<?php\nuse App\\Models\\User;\n")
        assert len(imports) == 1
        assert imports[0]["name"] == "User"
        assert imports[0]["full_import_name"] == "App\\Models\\User"
        assert imports[0]["alias"] is None

    def test_aliased_import(self, parser, tmp_path):
        imports = self._imports(
            parser, tmp_path, "<?php\nuse App\\Models\\Post as BlogPost;\n"
        )
        assert len(imports) == 1
        assert imports[0]["name"] == "BlogPost"
        assert imports[0]["alias"] == "BlogPost"
        assert imports[0]["full_import_name"] == "App\\Models\\Post"

    def test_group_import_expands_with_prefix(self, parser, tmp_path):
        """`use Foo\\Bar\\{A, B as C};` is two imports, both prefix-qualified."""
        imports = self._imports(parser, tmp_path, "<?php\nuse Foo\\Bar\\{A, B as C};\n")
        assert len(imports) == 2
        by_full = {i["full_import_name"]: i for i in imports}
        assert set(by_full) == {"Foo\\Bar\\A", "Foo\\Bar\\B"}
        assert by_full["Foo\\Bar\\A"]["alias"] is None
        assert by_full["Foo\\Bar\\B"]["alias"] == "C"

    def test_function_import(self, parser, tmp_path):
        imports = self._imports(parser, tmp_path, "<?php\nuse function Baz\\helper;\n")
        assert len(imports) == 1
        assert imports[0]["full_import_name"] == "Baz\\helper"
        assert imports[0]["name"] == "helper"

    def test_trait_use_is_not_an_import(self, parser, tmp_path):
        """A `use` inside a class body pulls in a trait; it is not an import."""
        code = (
            "<?php\n"
            "trait Greets { public function hi() { return 1; } }\n"
            "class Svc { use Greets; }\n"
        )
        f = tmp_path / "trait.php"
        f.write_text(code, encoding="utf-8")
        result = parser.parse(str(f))

        assert result["imports"] == []
        assert [c["name"] for c in result.get("classes", [])] == ["Svc"]
        assert [t["name"] for t in result.get("traits", [])] == ["Greets"]

    def test_imports_are_ordered_by_line(self, parser, tmp_path):
        code = (
            "<?php\n"
            "use App\\Models\\User;\n"
            "use App\\Models\\Post as BlogPost;\n"
            "use function Baz\\helper;\n"
        )
        imports = self._imports(parser, tmp_path, code)
        assert [i["line_number"] for i in imports] == [2, 3, 4]
