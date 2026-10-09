"""ScipIndexParser routes definitions by SymbolInformation.kind, using the numbers
of the SCIP schema: Enum 11, Interface 21, Protocol 42. Getter 18, Instance 20 and
Type 54 are different kinds and must not be taken for Enum / Interface / Protocol.
Kinds the parser infers for producers that report 0 use the same numbers.
"""

from pathlib import Path

import pytest

from codegraphcontext.tools import scip_pb2
from codegraphcontext.tools.scip_indexer import ScipIndexParser


def _parse(tmp_path: Path, symbol: str, kind: int, source: str) -> dict:
    index = scip_pb2.Index()
    doc = index.documents.add()
    doc.relative_path = "Sample.src"
    definition = doc.occurrences.add()
    definition.symbol = symbol
    definition.symbol_roles = 1  # Definition
    definition.range.extend([0, 0, 1])
    sym_info = doc.symbols.add()
    sym_info.symbol = symbol
    sym_info.kind = kind
    scip_path = tmp_path / "index.scip"
    scip_path.write_bytes(index.SerializeToString())
    (tmp_path / "Sample.src").write_text(source)
    return ScipIndexParser().parse(scip_path, tmp_path)["files"][str((tmp_path / "Sample.src").resolve())]


def _buckets(file_data: dict) -> list:
    return sorted(
        b for b in ("classes", "interfaces", "structs", "enums", "traits", "functions", "variables") if file_data.get(b)
    )


@pytest.mark.parametrize(
    "kind, symbol, bucket",
    [
        (scip_pb2.SymbolInformation.Enum, "pkg . . sample/Color#", "enums"),
        (scip_pb2.SymbolInformation.Interface, "pkg . . sample/Reader#", "interfaces"),
        (scip_pb2.SymbolInformation.Protocol, "pkg . . sample/Drawable#", "interfaces"),
        (scip_pb2.SymbolInformation.Class, "pkg . . sample/Widget#", "classes"),
        (scip_pb2.SymbolInformation.Struct, "pkg . . sample/Point#", "structs"),
        (scip_pb2.SymbolInformation.Trait, "pkg . . sample/Show#", "traits"),
        (scip_pb2.SymbolInformation.Function, "pkg . . sample/make().", "functions"),
        (scip_pb2.SymbolInformation.Method, "pkg . . sample/Point#read().", "functions"),
        (scip_pb2.SymbolInformation.Field, "pkg . . sample/Point#name.", "variables"),
        (scip_pb2.SymbolInformation.Variable, "pkg . . sample/count.", "variables"),
    ],
)
def test_producer_kind_routes_to_its_bucket(tmp_path: Path, kind: int, symbol: str, bucket: str) -> None:
    assert _buckets(_parse(tmp_path, symbol, kind, "x\n")) == [bucket]


@pytest.mark.parametrize(
    "kind, not_bucket",
    [
        (scip_pb2.SymbolInformation.Getter, "enums"),
        (scip_pb2.SymbolInformation.Instance, "interfaces"),
        (scip_pb2.SymbolInformation.Type, "interfaces"),
    ],
)
def test_other_kinds_are_not_taken_for_enum_interface_or_protocol(tmp_path: Path, kind: int, not_bucket: str) -> None:
    assert not_bucket not in _buckets(_parse(tmp_path, "pkg . . sample/Thing#", kind, "x\n"))


def test_zero_kind_interface_from_source_is_an_interface(tmp_path: Path) -> None:
    file_data = _parse(tmp_path, "scip-php composer . . sample/IFoo#", 0, "interface IFoo\n")
    assert _buckets(file_data) == ["interfaces"]


def test_zero_kind_cxx_enum_is_an_enum(tmp_path: Path) -> None:
    file_data = _parse(tmp_path, "cxx . . $ Color#", 0, "enum Color {\n")
    assert _buckets(file_data) == ["enums"]
