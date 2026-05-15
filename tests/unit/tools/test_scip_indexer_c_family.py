"""Unit tests for SCIP C/C++/C# indexer helpers and parser heuristics."""

import json
from pathlib import Path

import pytest

from codegraphcontext.tools.scip_indexer import ScipIndexParser, ScipIndexer


def test_compdb_host_paths_to_container(tmp_path: Path) -> None:
    proj = tmp_path / "myproj"
    proj.mkdir()
    scratch = tmp_path / "out"
    scratch.mkdir()
    comp = scratch / "cgc_compile_commands.json"
    comp.write_text(
        json.dumps(
            [
                {
                    "directory": str(proj.resolve()),
                    "command": "clang++ -c main.cpp",
                    "file": "main.cpp",
                }
            ]
        )
    )
    out = ScipIndexer._compdb_host_paths_to_container(str(comp), proj, scratch)
    data = json.loads(Path(out).read_text())
    assert data[0]["directory"] == "/src"
    assert data[0]["file"] == "main.cpp"


def test_resolve_compdb_writes_absolute_directories_to_scratch(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    comp = proj / "compile_commands.json"
    comp.write_text(
        json.dumps(
            [
                {
                    "directory": ".",
                    "command": "cc -c main.c",
                    "file": "main.c",
                }
            ]
        )
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    out = ScipIndexer._resolve_compdb_paths(str(comp), proj, scratch)
    assert Path(out).parent == scratch
    data = json.loads(Path(out).read_text())
    assert data[0]["directory"] == str(proj.resolve())


def test_infer_cxx_enum_vs_struct_vs_class() -> None:
    p = ScipIndexParser()
    lines = [
        "enum Color {",
        "enum class Direction {",
        "struct MyStruct {",
        "union MyUnion {",
        "class Foo {",
    ]
    assert p._infer_cxx_zero_kind("cxx . . $ Color#", 1, lines) == 18
    assert p._infer_cxx_zero_kind("cxx . . $ Direction#", 2, lines) == 18
    assert p._infer_cxx_zero_kind("cxx . . $ MyStruct#", 3, lines) == 49
    assert p._infer_cxx_zero_kind("cxx . . $ MyUnion#", 4, lines) == 49
    assert p._infer_cxx_zero_kind("cxx . . $ Foo#", 5, lines) == 7


def test_infer_cxx_method_and_free_function() -> None:
    p = ScipIndexParser()
    lines = ["void f();"]
    assert p._infer_cxx_zero_kind("cxx . . $ Dog#speak(deadbeef).", 1, lines) == 26
    assert p._infer_cxx_zero_kind("cxx . . $ Dog#speak().", 1, lines) == 26
    assert p._infer_cxx_zero_kind("cxx . . $ add(deadbeef).", 1, lines) == 17


def test_name_from_symbol_strips_clang_hash_suffix() -> None:
    p = ScipIndexParser()
    assert p._name_from_symbol("cxx . . $ Dog#speak(83f5f38750778ac8).") == "speak"
    assert p._name_from_symbol("cxx . . $ add(24764cae04130674).") == "add"


def test_find_csharp_project_nested(sample_projects_path: Path) -> None:
    root = sample_projects_path / "sample_project_csharp"
    if not root.is_dir():
        pytest.skip("sample_project_csharp fixture missing")
    csproj = ScipIndexer._find_csharp_project(root)
    assert csproj is not None
    assert csproj.name == "Example.App.csproj"


def test_build_command_csharp_includes_working_directory(sample_projects_path: Path) -> None:
    root = sample_projects_path / "sample_project_csharp"
    if not root.is_dir():
        pytest.skip("sample_project_csharp fixture missing")
    idx = ScipIndexer()
    out = Path("/tmp/out.scip")
    cmd = idx._build_command("csharp", "scip-dotnet", root.resolve(), out)
    assert cmd is not None
    assert "--working-directory" in cmd
    assert "Example.App.csproj" in "".join(str(c) for c in cmd)
