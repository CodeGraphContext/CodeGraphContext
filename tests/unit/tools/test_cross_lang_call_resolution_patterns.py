"""Pattern tests for cross-language CALLS resolution gaps (CGC_GRAPH_INCONSISTENCIES IDs 4–36)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import os

from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
from codegraphcontext.tools.indexing.resolution.inheritance import (
    build_companion_of_links,
    build_decorated_by_links,
    build_elixir_implements_links,
    build_embeds_links,
    build_go_implements_links,
    build_haskell_implements_links,
    build_inheritance_and_csharp_files,
    build_metaclass_links,
    build_partial_of_links,
    build_part_of_links,
)
from codegraphcontext.tools.languages.c import CTreeSitterParser
from codegraphcontext.tools.languages.cpp import CppTreeSitterParser
from codegraphcontext.tools.languages.elixir import ElixirTreeSitterParser
from codegraphcontext.tools.languages.go import GoTreeSitterParser
from codegraphcontext.tools.languages.haskell import HaskellTreeSitterParser
from codegraphcontext.tools.languages.java import JavaTreeSitterParser
from codegraphcontext.tools.languages.lua import LuaTreeSitterParser
from codegraphcontext.tools.languages.perl import PerlTreeSitterParser
from codegraphcontext.tools.languages.php import PhpTreeSitterParser
from codegraphcontext.tools.languages.ruby import RubyTreeSitterParser
from codegraphcontext.tools.languages.rust import RustTreeSitterParser
from codegraphcontext.tools.languages.scala import ScalaTreeSitterParser
from codegraphcontext.tools.languages.csharp import CSharpTreeSitterParser
from codegraphcontext.tools.languages.dart import DartTreeSitterParser
from codegraphcontext.tools.languages.swift import SwiftTreeSitterParser
from codegraphcontext.tools.languages.typescript import TypescriptTreeSitterParser
from codegraphcontext.tools.languages.python import PythonTreeSitterParser
from codegraphcontext.tools.languages.kotlin import KotlinTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "sample_projects"


@pytest.fixture(scope="module")
def manager():
    return get_tree_sitter_manager()


def _parser(manager, lang: str):
    wrapper = MagicMock()
    wrapper.language_name = lang
    wrapper.language = manager.get_language_safe(lang)
    wrapper.parser = manager.create_parser(lang)
    return wrapper


class TestCrossLangCallResolutionPatterns:
    def test_c_xmacro_enum_members(self, manager):
        wrapper = _parser(manager, "c")
        parser = CTreeSitterParser(wrapper)
        data = parser.parse(str(FIXTURES / "sample_project_c" / "tough_macros.c"))
        names = {member["name"] for member in data.get("enum_members", [])}
        assert names == {"COLOR_RED", "COLOR_GREEN", "COLOR_BLUE"}

    def test_c_define_handler_macro_functions(self, manager):
        wrapper = _parser(manager, "c")
        parser = CTreeSitterParser(wrapper)
        data = parser.parse(str(FIXTURES / "sample_project_c" / "tough_macros.c"))
        handlers = {
            (fn["name"], fn["line_number"])
            for fn in data.get("functions", [])
            if fn.get("name", "").startswith("handle_")
        }
        assert handlers == {
            ("handle_input", 13),
            ("handle_output", 14),
            ("handle_error", 15),
        }

    def test_c_function_pointer_callback(self, manager):
        wrapper = _parser(manager, "c")
        parser = CTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_c"
        files = []
        for name in ("main.c", "utils.c", "tough_macros.c"):
            parsed = parser.parse(str(base / name))
            files.append({
                "path": str((base / name).resolve()),
                "lang": "c",
                "functions": parsed["functions"],
                "classes": parsed.get("classes", []),
                "function_calls": parsed["function_calls"],
                "imports": parsed.get("imports", []),
            })
        fn_to_fn, *_ = build_function_call_groups(files, {})
        edges = [
            e for e in fn_to_fn
            if e["caller_name"] == "process_entity" and e["called_name"] == "my_callback"
        ]
        assert len(edges) == 1
        edge = edges[0]
        assert edge["line_number"] == 6
        assert edge["called_line_number"] == 5
        assert edge["called_file_path"].endswith("main.c")

    def test_cpp_template_overload_disambiguation(self, manager):
        wrapper = _parser(manager, "cpp")
        parser = CppTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_cpp" / "templates.cpp"
        parsed = parser.parse(str(path))
        fn_to_fn, *_ = build_function_call_groups([{
            "path": str(path.resolve()),
            "lang": "cpp",
            "functions": parsed["functions"],
            "classes": parsed.get("classes", []),
            "function_calls": parsed["function_calls"],
            "imports": [],
        }], {})
        lines = {
            (e["line_number"], e["called_line_number"])
            for e in fn_to_fn
            if e["caller_name"] == "templateDemo" and e["called_name"] == "add"
        }
        assert lines == {(11, 5), (12, 8)}

    def test_lua_require_alias_method_call(self, manager):
        wrapper = _parser(manager, "lua")
        parser = LuaTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_lua"
        files = []
        imports_map = {}
        for name in ("main.lua", "utils.lua", "rectangle.lua"):
            parsed = parser.parse(str(base / name))
            file_path = str((base / name).resolve())
            files.append({
                "path": file_path,
                "lang": "lua",
                "functions": parsed["functions"],
                "classes": [],
                "function_calls": parsed["function_calls"],
                "imports": parsed.get("imports", []),
            })
            for fn in parsed["functions"]:
                imports_map.setdefault(fn["name"], []).append(file_path)
            imports_map.setdefault(Path(name).stem, []).append(file_path)
        fn_to_fn, *_ = build_function_call_groups(files, imports_map)
        edge = next(
            e for e in fn_to_fn
            if e["caller_name"] == "main" and e["called_name"] == "greet"
        )
        assert edge["line_number"] == 5
        assert edge["called_line_number"] == 3

    def test_swift_protocol_extension_calls(self, manager):
        wrapper = _parser(manager, "swift")
        parser = SwiftTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_swift" / "ToughCases.swift"
        parsed = parser.parse(str(path))
        fn_to_fn, *_ = build_function_call_groups([{
            "path": str(path.resolve()),
            "lang": "swift",
            "functions": parsed["functions"],
            "classes": parsed.get("classes", []),
            "traits": parsed.get("traits", []),
            "function_calls": parsed["function_calls"],
            "imports": parsed.get("imports", []),
            "variables": parsed.get("variables", []),
        }], {})
        edges = {
            (e["full_call_name"], e["called_line_number"], e.get("called_context"))
            for e in fn_to_fn
            if e["caller_name"] == "testProtocols"
        }
        assert ("m.doWork", 12, "Workable") in edges
        assert ("d.doWork", 26, "Developer") in edges
        assert ("m.extraHelp", 16, "Workable") in edges

    def test_go_struct_implements_shape(self, manager):
        wrapper = _parser(manager, "go")
        parser = GoTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_go" / "interfaces.go"
        parsed = parser.parse(str(path))
        file_data = {
            "path": str(path.resolve()),
            "lang": "go",
            "functions": parsed["functions"],
            "structs": parsed["structs"],
            "interfaces": parsed["interfaces"],
        }
        links = build_go_implements_links([file_data])
        shape_impls = {
            (row["child_name"], row["parent_name"])
            for row in links
            if row["parent_name"] == "Shape"
        }
        assert shape_impls == {
            ("Circle", "Shape"),
            ("Rectangle", "Shape"),
            ("Triangle", "Shape"),
        }

    def test_elixir_alias_and_use_macro_calls(self, manager):
        wrapper = _parser(manager, "elixir")
        parser = ElixirTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_elixir"
        files = []
        imports_map = {}
        for rel in (
            "main.ex",
            "tough_cases.ex",
            "lib/worker.ex",
            "lib/utils.ex",
            "lib/protocol.ex",
        ):
            path = base / rel
            if not path.exists():
                continue
            parsed = parser.parse(str(path))
            file_path = str(path.resolve())
            files.append({
                "path": file_path,
                "lang": "elixir",
                "functions": parsed["functions"],
                "classes": [],
                "function_calls": parsed["function_calls"],
                "imports": parsed.get("imports", []),
                "modules": parsed.get("modules", []),
            })
            for fn in parsed["functions"]:
                ctx = fn.get("context") or fn.get("class_context")
                if ctx:
                    imports_map.setdefault(ctx, []).append(file_path)
                imports_map.setdefault(fn["name"], []).append(file_path)

        fn_to_fn, *_ = build_function_call_groups(files, imports_map)
        edges = {
            (e["caller_name"], e["called_name"], e.get("called_context"), e["line_number"])
            for e in fn_to_fn
        }
        assert ("run", "start_link", "MyApp.Worker", 10) in edges
        assert ("run", "log_execution", "MyApp.Utils", 9) in edges
        assert ("run", "serialize", "MyApp.Serializable", 15) in edges
        assert ("perform", "identity", "Tough.Cases", 22) in edges
        assert ("perform", "log", "Tough.Cases", 21) in edges

    def test_java_static_import_method_and_proxy_dispatch(self, manager, monkeypatch):
        monkeypatch.setenv("SKIP_EXTERNAL_RESOLUTION", "false")
        os.environ["SKIP_EXTERNAL_RESOLUTION"] = "false"

        wrapper = _parser(manager, "java")
        parser = JavaTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_java" / "src" / "com" / "example" / "app"
        files = []
        imports_map = {}
        for path in sorted(base.rglob("*.java")):
            parsed = parser.parse(str(path))
            file_path = str(path.resolve())
            files.append({
                "path": file_path,
                "lang": "java",
                "package": parsed.get("package"),
                "functions": parsed["functions"],
                "classes": parsed.get("classes", []),
                "function_calls": parsed["function_calls"],
                "imports": parsed.get("imports", []),
            })
            for cls in parsed.get("classes", []):
                imports_map.setdefault(cls["name"], []).append(file_path)
            for fn in parsed["functions"]:
                ctx = fn.get("context") or fn.get("class_context")
                if ctx:
                    imports_map.setdefault(ctx, []).append(file_path)
                imports_map.setdefault(fn["name"], []).append(file_path)

        fn_to_fn, fn_to_class, *_ = build_function_call_groups(files, imports_map)
        main_edges = {
            (e["full_call_name"], e["called_name"], e["line_number"], e.get("called_line_number"))
            for e in fn_to_fn + fn_to_class
            if e.get("caller_name") == "main" and e["caller_file_path"].endswith("Main.java")
        }
        assert ("CollectionUtils.sumOfSquares", "sumOfSquares", 18, 8) in main_edges
        assert ("IOHelper.readFirstLine", "readFirstLine", 22, 10) in main_edges
        assert ("GreetingServiceImpl", "GreetingServiceImpl", 14, 7) in main_edges

        proxy_edges = {
            (e["called_name"], e.get("called_context"), e.get("called_line_number"))
            for e in fn_to_fn
            if e.get("caller_name") == "run" and e.get("line_number") == 169
        }
        assert ("process", "DataService", 128) in proxy_edges
        assert ("process", "DataServiceImpl", 132) in proxy_edges

    def test_haskell_typeclass_instances_and_constructor_call(self, manager):
        wrapper = _parser(manager, "haskell")
        parser = HaskellTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_haskell"
        files = []
        imports_map = {}
        for path in sorted(base.rglob("*.hs")):
            parsed = parser.parse(str(path))
            file_path = str(path.resolve())
            files.append({
                "path": file_path,
                "lang": "haskell",
                "functions": parsed["functions"],
                "classes": parsed.get("classes", []),
                "function_calls": parsed["function_calls"],
                "imports": parsed.get("imports", []),
                "typeclass_instances": parsed.get("typeclass_instances", []),
            })
            for cls in parsed.get("classes", []):
                imports_map.setdefault(cls["name"], []).append(file_path)
            for fn in parsed["functions"]:
                ctx = fn.get("context") or fn.get("class_context")
                if ctx:
                    imports_map.setdefault(ctx, []).append(file_path)
                imports_map.setdefault(fn["name"], []).append(file_path)

        impl_links = {
            (row["child_name"], row["parent_name"])
            for row in build_haskell_implements_links(files)
        }
        assert ("User", "Descriptive") in impl_links
        assert ("Product", "Descriptive") in impl_links

        fn_to_fn, fn_to_class, *_ = build_function_call_groups(files, imports_map)
        person_edges = {
            (e["full_call_name"], e["called_name"], e["line_number"], e.get("called_line_number"))
            for e in fn_to_fn + fn_to_class
            if e["caller_file_path"].endswith("Main.hs") and e.get("full_call_name") == "Person"
        }
        assert ("Person", "Person", 8, 3) in person_edges

    def test_perl_isa_inheritance_super_and_file_new(self, manager, monkeypatch):
        monkeypatch.setenv("SKIP_EXTERNAL_RESOLUTION", "false")
        os.environ["SKIP_EXTERNAL_RESOLUTION"] = "false"

        wrapper = _parser(manager, "perl")
        parser = PerlTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_perl"
        files = []
        imports_map = {}
        paths = sorted(base.rglob("*.pl")) + sorted((base / "lib").rglob("*.pm"))
        for path in paths:
            parsed = parser.parse(str(path))
            file_path = str(path.resolve())
            files.append({
                "path": file_path,
                "lang": "perl",
                "functions": parsed["functions"],
                "classes": parsed.get("classes", []),
                "function_calls": parsed["function_calls"],
                "imports": parsed.get("imports", []),
            })
            for cls in parsed.get("classes", []):
                imports_map.setdefault(cls["name"], []).append(file_path)
            for fn in parsed["functions"]:
                ctx = fn.get("context") or fn.get("class_context")
                if ctx:
                    imports_map.setdefault(ctx, []).append(file_path)
                imports_map.setdefault(fn["name"], []).append(file_path)

        inheritance, _ = build_inheritance_and_csharp_files(files, imports_map)
        assert any(
            row["child_name"] == "Dog" and row["parent_name"] == "Animal"
            for row in inheritance
        )

        groups = build_function_call_groups(files, imports_map)
        fn_to_fn, file_to_fn = groups[0], groups[4]
        super_edges = {
            (e.get("called_context"), e.get("called_line_number"))
            for e in fn_to_fn
            if e.get("line_number") == 24
        }
        assert ("Animal", 14) in super_edges

        new_edges = {
            (e["called_name"], e.get("called_line_number"))
            for e in file_to_fn
            if e["caller_file_path"].endswith("main.pl") and e.get("line_number") == 7
        }
        assert ("new", 6) in new_edges

    def test_ruby_new_resolves_to_initialize(self, manager, monkeypatch):
        monkeypatch.setenv("SKIP_EXTERNAL_RESOLUTION", "false")
        os.environ["SKIP_EXTERNAL_RESOLUTION"] = "false"

        wrapper = _parser(manager, "ruby")
        parser = RubyTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_ruby" / "tough_cases.rb"
        parsed = parser.parse(str(path))
        file_path = str(path.resolve())
        imports_map = {}
        for fn in parsed["functions"]:
            imports_map.setdefault(fn["name"], []).append(file_path)
        for cls in parsed.get("classes", []):
            imports_map.setdefault(cls["name"], []).append(file_path)

        fn_to_fn, *_ = build_function_call_groups([{
            "path": file_path,
            "lang": "ruby",
            "functions": parsed["functions"],
            "classes": parsed.get("classes", []),
            "function_calls": parsed["function_calls"],
            "imports": [],
        }], imports_map)

        edge = next(
            e for e in fn_to_fn
            if e.get("caller_name") == "test_callbacks"
            and e.get("called_name") == "initialize"
        )
        assert edge["line_number"] == 46
        assert edge["called_line_number"] == 32
        assert edge.get("called_context") == "CallbackRegistry"

    def test_php_trait_conflict_resolution(self, manager, monkeypatch):
        monkeypatch.setenv("SKIP_EXTERNAL_RESOLUTION", "false")
        os.environ["SKIP_EXTERNAL_RESOLUTION"] = "false"

        wrapper = _parser(manager, "php")
        parser = PhpTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_php" / "tough_cases.php"
        parsed = parser.parse(str(path))
        file_path = str(path.resolve())
        imports_map = {}
        for fn in parsed["functions"]:
            ctx = fn.get("class_context")
            if ctx:
                imports_map.setdefault(ctx, []).append(file_path)
            imports_map.setdefault(fn["name"], []).append(file_path)
        for cls in parsed.get("classes", []):
            imports_map.setdefault(cls["name"], []).append(file_path)

        fn_to_fn, *_ = build_function_call_groups([{
            "path": file_path,
            "lang": "php",
            "functions": parsed["functions"],
            "classes": parsed.get("classes", []),
            "function_calls": parsed["function_calls"],
            "imports": parsed.get("imports", []),
        }], imports_map)

        edges = {
            (e["line_number"], e["called_name"], e.get("called_context"), e.get("called_line_number"))
            for e in fn_to_fn
            if e.get("caller_name") == "run"
        }
        assert (27, "execute", "Beta", 15) in edges
        assert (28, "shared", "Alpha", 11) in edges
        assert (29, "shared", "Beta", 16) in edges

    def test_rust_module_super_and_trait_specialization(self, manager, monkeypatch):
        monkeypatch.setenv("SKIP_EXTERNAL_RESOLUTION", "false")
        os.environ["SKIP_EXTERNAL_RESOLUTION"] = "false"

        wrapper = _parser(manager, "rust")
        parser = RustTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_rust" / "src" / "tough_cases.rs"
        parsed = parser.parse(str(path))
        file_path = str(path.resolve())
        assert any(f["name"] == "snappy_compress" for f in parsed["functions"])

        imports_map = {fn["name"]: [file_path] for fn in parsed["functions"]}
        fn_to_fn, *_ = build_function_call_groups([{
            "path": file_path,
            "lang": "rust",
            "functions": parsed["functions"],
            "classes": [],
            "function_calls": parsed["function_calls"],
            "imports": [],
        }], imports_map)

        edges = {
            (e.get("full_call_name"), e.get("called_line_number"), e.get("called_context"))
            for e in fn_to_fn
            if e.get("caller_name") == "call_both"
        }
        assert ("super::action()", 27, "outer") in edges
        assert ("action()", 30, "outer::inner") in edges

        spec = next(
            e for e in fn_to_fn
            if e.get("caller_name") == "test_specialization"
            and e.get("called_name") == "specialized_action"
        )
        assert spec["line_number"] == 105
        assert spec["called_line_number"] == 98

    def test_scala_case_class_apply(self, manager, monkeypatch):
        monkeypatch.setenv("SKIP_EXTERNAL_RESOLUTION", "false")
        os.environ["SKIP_EXTERNAL_RESOLUTION"] = "false"

        wrapper = _parser(manager, "scala")
        parser = ScalaTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_scala"
        files = []
        imports_map = {}
        for path in sorted(base.rglob("*.scala")):
            parsed = parser.parse(str(path))
            file_path = str(path.resolve())
            files.append({
                "path": file_path,
                "lang": "scala",
                "functions": parsed["functions"],
                "classes": parsed.get("classes", []),
                "objects": parsed.get("objects", []),
                "function_calls": parsed["function_calls"],
                "imports": parsed.get("imports", []),
            })
            for obj in parsed.get("objects", []):
                imports_map.setdefault(obj["name"], []).append(file_path)
            for fn in parsed["functions"]:
                ctx = fn.get("context") or fn.get("class_context")
                if ctx:
                    imports_map.setdefault(ctx, []).append(file_path)
                imports_map.setdefault(fn["name"], []).append(file_path)

        fn_to_fn, *_ = build_function_call_groups(files, imports_map)
        apply_edge = next(
            e for e in fn_to_fn
            if e.get("caller_name") == "main"
            and e.get("called_name") == "apply"
            and e.get("line_number") == 4
        )
        assert apply_edge["called_line_number"] == 12

    def test_csharp_partial_of_and_cross_file_call(self, manager, monkeypatch):
        monkeypatch.setenv("SKIP_EXTERNAL_RESOLUTION", "false")
        os.environ["SKIP_EXTERNAL_RESOLUTION"] = "false"

        wrapper = _parser(manager, "csharp")
        parser = CSharpTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_csharp"
        files = []
        imports_map = {}
        for path in sorted(base.glob("ToughCases*.cs")):
            parsed = parser.parse(str(path))
            file_path = str(path.resolve())
            files.append({
                "path": file_path,
                "lang": parser.language_name,
                "namespace": parsed.get("namespace"),
                "functions": parsed["functions"],
                "classes": parsed.get("classes", []),
                "function_calls": parsed["function_calls"],
                "imports": parsed.get("imports", []),
            })
            for cls in parsed.get("classes", []):
                imports_map.setdefault(cls["name"], []).append(file_path)
            for fn in parsed["functions"]:
                ctx = fn.get("class_context")
                if ctx:
                    imports_map.setdefault(ctx, []).append(file_path)
                imports_map.setdefault(fn["name"], []).append(file_path)

        partial_links = build_partial_of_links(files)
        assert any(
            row["child_name"] == "MultiPartClass"
            and row["path"].endswith("ToughCases_PartB.cs")
            and row["resolved_parent_file_path"].endswith("ToughCases.cs")
            for row in partial_links
        )

        fn_to_fn, *_ = build_function_call_groups(files, imports_map)
        edge = next(
            e for e in fn_to_fn
            if e.get("caller_name") == "MethodFromPartA"
            and e.get("called_name") == "MethodFromPartB"
        )
        assert edge["line_number"] == 15
        assert edge["called_line_number"] == 11

    def test_dart_main_perform_action_and_part_of(self, manager, monkeypatch):
        monkeypatch.setenv("SKIP_EXTERNAL_RESOLUTION", "false")
        os.environ["SKIP_EXTERNAL_RESOLUTION"] = "false"

        wrapper = _parser(manager, "dart")
        parser = DartTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_dart" / "lib"
        files = []
        imports_map = {}
        for path in sorted(base.rglob("*.dart")):
            parsed = parser.parse(str(path))
            if "error" in parsed:
                parsed = {
                    "path": str(path),
                    "functions": [],
                    "classes": [],
                    "function_calls": [],
                    "imports": [],
                    "library_parts": [],
                }
            file_path = str(path.resolve())
            files.append({
                "path": file_path,
                "lang": "dart",
                "functions": parsed.get("functions", []),
                "classes": parsed.get("classes", []),
                "function_calls": parsed.get("function_calls", []),
                "imports": parsed.get("imports", []),
                "variables": parsed.get("variables", []),
                "library_parts": parsed.get("library_parts", []),
            })
            for cls in parsed.get("classes", []):
                imports_map.setdefault(cls["name"], []).append(file_path)
            for fn in parsed.get("functions", []):
                imports_map.setdefault(fn["name"], []).append(file_path)

        from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports

        def get_parser(ext):
            return DartTreeSitterParser(wrapper)

        prescan_map = pre_scan_for_imports(list(base.rglob("*.dart")), {".dart"}, get_parser)
        fn_to_fn, *_ = build_function_call_groups(files, prescan_map)
        edge = next(
            e for e in fn_to_fn
            if e.get("caller_name") == "main" and e.get("called_name") == "performAction"
        )
        assert edge["line_number"] == 5
        assert edge["called_line_number"] == 18
        assert edge.get("called_context") == "User"

        part_links = build_part_of_links(files)
        assert any(
            row["child_path"].endswith("tough_cases_part.dart")
            and row["parent_path"].endswith("tough_cases.dart")
            for row in part_links
        )

    def test_typescript_dynamic_import_calls_static_import_file(self, manager):
        wrapper = _parser(manager, "typescript")
        parser = TypescriptTreeSitterParser(wrapper)
        base = FIXTURES / "sample_project_typescript"
        files = []
        for name in ("src/tough_cases.ts", "src/tough_circular_b.ts"):
            path = base / name
            parsed = parser.parse(str(path))
            files.append({
                "path": str(path.resolve()),
                "lang": "typescript",
                "functions": parsed["functions"],
                "classes": parsed.get("classes", []),
                "function_calls": parsed["function_calls"],
                "imports": parsed.get("imports", []),
            })
        *_, fn_to_file = build_function_call_groups(files, {})
        edge = next(
            e for e in fn_to_file
            if e.get("caller_name") == "loadModuleDynamically"
        )
        assert edge["line_number"] == 31
        assert edge["called_name"] == "tough_circular_b.ts"
        assert edge["called_file_path"].endswith("tough_circular_b.ts")

    def test_typescript_decorated_by_validate_on_update_age(self, manager):
        wrapper = _parser(manager, "typescript")
        parser = TypescriptTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_typescript" / "src" / "decorators-metadata.ts"
        parsed = parser.parse(str(path))
        file_data = {
            "path": str(path.resolve()),
            "lang": "typescript",
            "functions": parsed["functions"],
            "classes": parsed.get("classes", []),
            "imports": parsed.get("imports", []),
        }
        edges = build_decorated_by_links([file_data], {})
        edge = next(
            e for e in edges
            if e["decorated_name"] == "updateAge"
            and e["decorated_context"] == "User"
            and e["decorator_name"] == "Validate"
        )
        assert edge["line_number"] == 363

    def test_python_metaclass_links(self, manager):
        wrapper = _parser(manager, "python")
        parser = PythonTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project" / "advanced_classes.py"
        parsed = parser.parse(str(path))
        file_data = {
            "path": str(path.resolve()),
            "lang": "python",
            "classes": parsed["classes"],
            "imports": parsed.get("imports", []),
        }
        links = build_metaclass_links([file_data], {})
        assert any(
            row["child_name"] == "WithMeta" and row["parent_name"] == "Meta"
            for row in links
        )
        assert any(
            row["child_name"] == "WithMeta2" and row["parent_name"] == "Meta"
            for row in links
        )

    def test_kotlin_companion_of_links(self, manager):
        wrapper = _parser(manager, "kotlin")
        parser = KotlinTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_kotlin" / "ToughCases.kt"
        parsed = parser.parse(str(path))
        file_data = {
            "path": str(path.resolve()),
            "lang": "kotlin",
            "classes": parsed.get("classes", []),
            "objects": parsed.get("objects", []),
        }
        links = build_companion_of_links([file_data])
        assert any(
            row["companion_name"] == "Companion"
            and row["owner_name"] == "DatabaseConnection"
            for row in links
        )

    def test_go_struct_embeds_base(self, manager):
        wrapper = _parser(manager, "go")
        parser = GoTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_go" / "tough_cases.go"
        parsed = parser.parse(str(path))
        file_data = {
            "path": str(path.resolve()),
            "lang": "go",
            "structs": parsed.get("structs", []),
        }
        links = build_embeds_links([file_data])
        assert any(
            row["child_name"] == "Extended" and row["parent_name"] == "Base"
            for row in links
        )

    def test_elixir_defimpl_implements_protocol(self, manager):
        wrapper = _parser(manager, "elixir")
        parser = ElixirTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_elixir" / "tough_cases.ex"
        parsed = parser.parse(str(path))
        file_data = {
            "path": str(path.resolve()),
            "lang": "elixir",
            "modules": parsed.get("modules", []),
        }
        links = build_elixir_implements_links([file_data])
        assert any(
            row["child_name"] == "Package" and row["parent_name"] == "Shippable"
            for row in links
        )

    def test_lua_metatable_variable_inherits(self, manager):
        wrapper = _parser(manager, "lua")
        parser = LuaTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_lua" / "tough_cases.lua"
        parsed = parser.parse(str(path))
        file_data = {
            "path": str(path.resolve()),
            "lang": "lua",
            "variables": parsed.get("variables", []),
        }
        inh, _ = build_inheritance_and_csharp_files([file_data], {})
        assert any(
            row["child_name"] == "Extended" and row["parent_name"] == "Base"
            for row in inh
        )

    def test_php_dynamic_member_resolves_sibling_method(self, manager, monkeypatch):
        monkeypatch.setenv("SKIP_EXTERNAL_RESOLUTION", "false")
        os.environ["SKIP_EXTERNAL_RESOLUTION"] = "false"

        wrapper = _parser(manager, "php")
        parser = PhpTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project_php" / "tough_cases.php"
        parsed = parser.parse(str(path))
        file_path = str(path.resolve())
        fn_to_fn, *_ = build_function_call_groups([{
            "path": file_path,
            "lang": "php",
            "functions": parsed["functions"],
            "classes": parsed.get("classes", []),
            "function_calls": parsed["function_calls"],
            "imports": [],
        }], {fn["name"]: [file_path] for fn in parsed["functions"]})
        edge = next(
            e for e in fn_to_fn
            if e.get("caller_name") == "invokeDynamically"
            and e.get("called_name") == "targetMethod"
        )
        assert edge["line_number"] == 64

    def test_python_universal_module_node(self, manager):
        wrapper = _parser(manager, "python")
        parser = PythonTreeSitterParser(wrapper)
        path = FIXTURES / "sample_project" / "edge_cases" / "empty.py"
        parsed = parser.parse(str(path))
        assert any(
            fn["name"] == "<module>" and fn["line_number"] == 1
            for fn in parsed["functions"]
        )
