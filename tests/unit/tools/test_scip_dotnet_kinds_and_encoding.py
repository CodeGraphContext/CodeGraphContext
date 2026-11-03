"""scip-dotnet indexes with and without SymbolInformation.kind / Document.position_encoding.

The fixtures are real scip-dotnet output for the same C#/VB sources:
``scip-dotnet-v0.2.16.scip`` (every kind 0, encoding unspecified) and
``scip-dotnet-a8d080c.scip`` (sourcegraph/scip-dotnet#124: explicit kinds, UTF-16 declared).
Symbol strings, occurrences and ranges are the same in both.
"""

from pathlib import Path

import pytest

from codegraphcontext.tools import scip_pb2
from codegraphcontext.tools.indexing.resolution.inheritance import build_inheritance_and_csharp_files
from codegraphcontext.tools.scip_indexer import ScipIndexParser

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "scip_dotnet_kinds"
LEGACY = "scip-dotnet-v0.2.16.scip"
MODERN = "scip-dotnet-a8d080c.scip"
CS, VB = "CsKinds/Kinds.cs", "VbKinds/Kinds.vb"

FUNCTIONS = sorted([
    (CS, "Area", 9), (CS, ".ctor", 15), (CS, "Origin", 16), (CS, "Twice", 25),
    (CS, ".cctor", 36), (CS, ".ctor", 37), (CS, ".ctor", 38), (CS, "Area", 40),
    (CS, "Add", 41), (CS, "M", 42), (CS, "M", 43), (CS, "Run", 45),
    (VB, "Twice", 3), (VB, "Go", 7), (VB, ".ctor", 14), (VB, ".ctor", 17), (VB, "Make", 20), (VB, "Use", 24),
])

CALLS = sorted([
    (CS, 16, "Point"), (CS, 47, "Calc"), (CS, 48, "M"), (CS, 48, "M"), (CS, 49, "Add"),
    (CS, 50, "Twice"), (CS, 51, "Origin"), (CS, 52, "Add"), (CS, 53, "Add"), (CS, 54, "M"),
    (VB, 8, "Twice"), (VB, 9, "Make"), (VB, 21, "Box"), (VB, 25, "Make"),
])


def _parse(index_name: str) -> dict:
    result = ScipIndexParser().parse(FIXTURE / index_name, FIXTURE)
    by_rel = {}
    for abs_path, file_data in result["files"].items():
        rel = Path(abs_path).relative_to(FIXTURE.resolve()).as_posix()
        by_rel[rel] = file_data
    return by_rel


def _names(files: dict, bucket: str) -> list:
    return sorted((rel, n["name"], n["line_number"]) for rel, fd in files.items() for n in fd.get(bucket, []))


def _calls(files: dict) -> list:
    return sorted(
        (rel, e["ref_line"], e["callee_name"])
        for rel, fd in files.items()
        for e in fd["function_calls_scip"] + fd["module_level_calls_scip"]
    )


def test_fixture_indexes_differ_only_in_kind_metadata() -> None:
    def load(name):
        index = scip_pb2.Index()
        index.ParseFromString((FIXTURE / name).read_bytes())
        return index

    legacy, modern = load(LEGACY), load(MODERN)
    utf16 = scip_pb2.PositionEncoding.UTF16CodeUnitOffsetFromLineStart
    assert {d.position_encoding for d in legacy.documents} == {0}
    assert {d.position_encoding for d in modern.documents} == {utf16}
    assert {s.kind for d in legacy.documents for s in d.symbols} == {0}
    modern_kinds = {s.kind for d in modern.documents for s in d.symbols}
    assert {scip_pb2.SymbolInformation.StaticMethod, scip_pb2.SymbolInformation.Constructor} <= modern_kinds
    for name, legacy_doc in ((d.relative_path, d) for d in legacy.documents):
        modern_doc = next(d for d in modern.documents if d.relative_path == name)
        assert list(modern_doc.occurrences) == list(legacy_doc.occurrences)


@pytest.mark.parametrize("index_name", [LEGACY, MODERN])
def test_static_methods_constructors_and_module_methods_are_functions(index_name: str) -> None:
    assert _names(_parse(index_name), "functions") == FUNCTIONS


@pytest.mark.parametrize("index_name", [LEGACY, MODERN])
def test_calls_after_non_bmp_characters_are_found(index_name: str) -> None:
    assert _calls(_parse(index_name)) == CALLS


def test_modern_index_types_follow_their_kinds() -> None:
    files = _parse(MODERN)
    assert [n[1] for n in _names(files, "classes")] == ["Calc", "Ext", "Op", "Rec", "Box", "Util"]
    assert [n[1] for n in _names(files, "interfaces")] == ["IShape"]
    assert [n[1] for n in _names(files, "structs")] == ["Point"]
    assert [n[1] for n in _names(files, "enums")] == ["Color"]


ENUM_INTERFACES = ["IComparable", "IConvertible", "IFormattable", "ISpanFormattable"]


@pytest.mark.parametrize("index_name, child_label", [(LEGACY, "Class"), (MODERN, "Enum")])
def test_enum_keeps_the_interfaces_the_producer_reports(index_name: str, child_label: str) -> None:
    files = _parse(index_name)
    rows, _ = build_inheritance_and_csharp_files(list(files.values()), {})
    color = sorted((r["parent_name"], r.get("child_label")) for r in rows if r["child_name"] == "Color")
    assert color == [(name, child_label) for name in ENUM_INTERFACES]


def test_enum_without_relationships_has_no_inheritance(tmp_path: Path) -> None:
    index = scip_pb2.Index()
    doc = index.documents.add()
    doc.relative_path = "color.h"
    occ = doc.occurrences.add()
    occ.symbol = "cxx . . $ Color#"
    occ.symbol_roles = 1
    occ.range.extend([0, 5, 10])
    doc.symbols.add().symbol = "cxx . . $ Color#"
    (tmp_path / "color.h").write_text("enum Color { Red };\n")
    scip_path = tmp_path / "index.scip"
    scip_path.write_bytes(index.SerializeToString())
    fd = ScipIndexParser().parse(scip_path, tmp_path)["files"][str((tmp_path / "color.h").resolve())]
    assert [e["name"] for e in fd["enums"]] == ["Color"]
    assert "bases" not in fd["enums"][0]
    assert build_inheritance_and_csharp_files([fd], {})[0] == []


def test_rust_impl_symbols_do_not_become_enum_bases(tmp_path: Path) -> None:
    index = scip_pb2.Index()
    doc = index.documents.add()
    doc.relative_path = "shape.rs"
    shape = "rust-analyzer cargo c 0.1.0 Shape#"
    for symbol, roles in ((shape, 1), ("rust-analyzer cargo c 0.1.0 impl#[Shape][Display]fmt().", 0)):
        occ = doc.occurrences.add()
        occ.symbol = symbol
        occ.symbol_roles = roles
        occ.range.extend([0, 5, 10])
    info = doc.symbols.add()
    info.symbol = shape
    info.kind = scip_pb2.SymbolInformation.Enum
    (tmp_path / "shape.rs").write_text("enum Shape { A }\n")
    scip_path = tmp_path / "index.scip"
    scip_path.write_bytes(index.SerializeToString())
    fd = ScipIndexParser().parse(scip_path, tmp_path)["files"][str((tmp_path / "shape.rs").resolve())]
    assert [e["name"] for e in fd["enums"]] == ["Shape"]
    assert "bases" not in fd["enums"][0]


def test_legacy_index_types_are_unchanged() -> None:
    files = _parse(LEGACY)
    assert [n[1] for n in _names(files, "classes")] == [
        "Calc", "Changed", "Color", "Ext", "IShape", "Op", "Point", "Rec", "Box", "Util",
    ]
    assert not any(files[rel].get(b) for rel in files for b in ("interfaces", "structs", "enums"))


def _single_reference_index(tmp_path: Path, line, start: int, end: int, encoding: int, tool: str) -> list:
    index = scip_pb2.Index()
    index.metadata.tool_info.name = tool
    doc = index.documents.add()
    doc.relative_path = "a.src"
    doc.position_encoding = encoding
    target = "pkg . . a/Target()."
    definition = doc.occurrences.add()
    definition.symbol = target
    definition.symbol_roles = 1
    definition.range.extend([0, 0, 1])
    reference = doc.occurrences.add()
    reference.symbol = target
    reference.range.extend([1, start, end])
    info = doc.symbols.add()
    info.symbol = target
    info.kind = scip_pb2.SymbolInformation.Function
    raw = line if isinstance(line, bytes) else line.encode("utf-8")
    (tmp_path / "a.src").write_bytes(b"def\n" + raw + b"\n")
    scip_path = tmp_path / "index.scip"
    scip_path.write_bytes(index.SerializeToString())
    fd = ScipIndexParser().parse(scip_path, tmp_path)["files"][str((tmp_path / "a.src").resolve())]
    return [e["ref_line"] for e in fd["function_calls_scip"] + fd["module_level_calls_scip"]]


LINE = 'x = "🚀é"; Target(1)'
E = scip_pb2.PositionEncoding


@pytest.mark.parametrize(
    "encoding, start, tool",
    [
        (E.UTF16CodeUnitOffsetFromLineStart, 11, "any"),
        (E.UTF8CodeUnitOffsetFromLineStart, 14, "any"),
        (E.UTF32CodeUnitOffsetFromLineStart, 10, "any"),
        (E.UnspecifiedPositionEncoding, 10, "scip-python"),
        (E.UnspecifiedPositionEncoding, 11, "scip-dotnet"),
    ],
)
def test_reference_columns_follow_the_declared_encoding(tmp_path: Path, encoding: int, start: int, tool: str) -> None:
    assert _single_reference_index(tmp_path, LINE, start, start + 6, encoding, tool) == [2]


@pytest.mark.parametrize(
    "encoding, start",
    [(E.UTF8CodeUnitOffsetFromLineStart, 10), (E.UTF16CodeUnitOffsetFromLineStart, 10)],
)
def test_a_column_in_another_encoding_is_not_a_call(tmp_path: Path, encoding: int, start: int) -> None:
    assert _single_reference_index(tmp_path, LINE, start, start + 6, encoding, "any") == []


def test_utf8_columns_count_an_undecodable_byte_once(tmp_path: Path) -> None:
    line = "xé Target(1)".encode("latin-1")
    assert _single_reference_index(tmp_path, line, 3, 9, E.UTF8CodeUnitOffsetFromLineStart, "any") == [2]


@pytest.mark.parametrize(
    "kind, symbol",
    [
        (scip_pb2.SymbolInformation.Event, "scip-dotnet nuget . . Fx/Calc#Changed#"),
        (scip_pb2.SymbolInformation.Module, "rust-analyzer cargo demo 0.1.0 util/"),
        (scip_pb2.SymbolInformation.Property, "scip-dotnet nuget . . Fx/Calc#Prop."),
        (9999, "pkg . . sample/Thing#"),
    ],
)
def test_kinds_without_a_cgc_node_type_are_not_materialized(tmp_path: Path, kind: int, symbol: str) -> None:
    index = scip_pb2.Index()
    doc = index.documents.add()
    doc.relative_path = "a.src"
    occ = doc.occurrences.add()
    occ.symbol = symbol
    occ.symbol_roles = 1
    occ.range.extend([0, 0, 1])
    info = doc.symbols.add()
    info.symbol = symbol
    info.kind = kind
    (tmp_path / "a.src").write_text("x\n")
    scip_path = tmp_path / "index.scip"
    scip_path.write_bytes(index.SerializeToString())
    fd = ScipIndexParser().parse(scip_path, tmp_path)["files"][str((tmp_path / "a.src").resolve())]
    assert not any(fd.get(b) for b in ("functions", "classes", "interfaces", "structs", "enums", "traits", "variables"))
