"""SCIP occurrences carry their range either in the deprecated `range` / `enclosing_range`
lists or in the typed `single_line_*` / `multi_line_*` fields (scip-go writes only the
typed ones). When both are present the typed form wins.
"""

from pathlib import Path

import pytest

from codegraphcontext.tools import scip_pb2
from codegraphcontext.tools.scip_indexer import ScipIndexParser, _occurrence_range


def _occ(legacy=None, single=None, multi=None) -> scip_pb2.Occurrence:
    occ = scip_pb2.Occurrence()
    if legacy is not None:
        occ.range.extend(legacy)
    if single is not None:
        occ.single_line_range.line, occ.single_line_range.start_character, occ.single_line_range.end_character = single
    if multi is not None:
        r = occ.multi_line_range
        r.start_line, r.start_character, r.end_line, r.end_character = multi
    return occ


@pytest.mark.parametrize(
    "occ, expected",
    [
        (_occ(legacy=[4, 2, 7]), [4, 2, 7]),
        (_occ(legacy=[4, 2, 6, 1]), [4, 2, 6, 1]),
        (_occ(single=(4, 2, 7)), [4, 2, 7]),
        (_occ(multi=(4, 2, 6, 1)), [4, 2, 6, 1]),
        (_occ(multi=(4, 2, 4, 9)), [4, 2, 4, 9]),
        (_occ(legacy=[4, 2, 7], single=(4, 2, 7)), [4, 2, 7]),
        (_occ(legacy=[99, 0, 3], single=(10, 2, 5)), [10, 2, 5]),
        (_occ(legacy=[99, 0, 3], multi=(10, 2, 12, 1)), [10, 2, 12, 1]),
        (_occ(), []),
    ],
    ids=[
        "legacy",
        "legacy-multi",
        "single",
        "multi",
        "multi-one-line",
        "both-equal",
        "both-differ-single",
        "both-differ-multi",
        "neither",
    ],
)
def test_occurrence_range(occ: scip_pb2.Occurrence, expected: list) -> None:
    assert _occurrence_range(occ) == expected


def test_enclosing_range_prefers_the_typed_form() -> None:
    occ = scip_pb2.Occurrence()
    occ.enclosing_range.extend([99, 0, 120, 1])
    occ.multi_line_enclosing_range.start_line = 10
    occ.multi_line_enclosing_range.end_line = 14
    assert _occurrence_range(occ, "typed_enclosing_range", "enclosing_range") == [10, 0, 14, 0]
    assert _occurrence_range(scip_pb2.Occurrence(), "typed_enclosing_range", "enclosing_range") == []


SOURCE = "package sample\n\nfunc Make() int {\n\treturn 1\n}\n\nfunc Use() int {\n\treturn Make()\n}\n"
MAKE, USE = "scip-go gomod example.com/sample . sample/Make().", "scip-go gomod example.com/sample . sample/Use()."


def test_typed_only_definitions_and_calls(tmp_path: Path) -> None:
    index = scip_pb2.Index()
    doc = index.documents.add()
    doc.relative_path = "sample.go"
    for symbol, (line, start, end), (enc_start, enc_end) in ((MAKE, (2, 5, 9), (2, 4)), (USE, (6, 5, 8), (6, 8))):
        definition = doc.occurrences.add()
        definition.symbol, definition.symbol_roles = symbol, 1
        definition.single_line_range.line, definition.single_line_range.start_character = line, start
        definition.single_line_range.end_character = end
        definition.multi_line_enclosing_range.start_line = enc_start
        definition.multi_line_enclosing_range.end_line = enc_end
        doc.symbols.add(symbol=symbol, kind=scip_pb2.SymbolInformation.Function)
    call = doc.occurrences.add()
    call.symbol = MAKE
    call.single_line_range.line, call.single_line_range.start_character, call.single_line_range.end_character = 7, 8, 12
    (tmp_path / "index.scip").write_bytes(index.SerializeToString())
    (tmp_path / "sample.go").write_text(SOURCE)

    file_data = ScipIndexParser().parse(tmp_path / "index.scip", tmp_path)["files"][
        str((tmp_path / "sample.go").resolve())
    ]

    assert sorted((f["name"], f["line_number"]) for f in file_data["functions"]) == [("Make", 3), ("Use", 7)]
    assert [(c["caller_symbol"], c["callee_name"], c["ref_line"]) for c in file_data["function_calls_scip"]] == [
        (USE, "Make", 8)
    ]
    assert file_data["module_level_calls_scip"] == []


def test_typed_range_wins_over_a_different_legacy_range(tmp_path: Path) -> None:
    index = scip_pb2.Index()
    doc = index.documents.add()
    doc.relative_path = "sample.go"
    definition = doc.occurrences.add()
    definition.symbol, definition.symbol_roles = MAKE, 1
    definition.range.extend([98, 5, 9])
    definition.single_line_range.line, definition.single_line_range.start_character = 2, 5
    definition.single_line_range.end_character = 9
    doc.symbols.add(symbol=MAKE, kind=scip_pb2.SymbolInformation.Function)
    (tmp_path / "index.scip").write_bytes(index.SerializeToString())
    (tmp_path / "sample.go").write_text(SOURCE)

    file_data = ScipIndexParser().parse(tmp_path / "index.scip", tmp_path)["files"][
        str((tmp_path / "sample.go").resolve())
    ]

    assert [(f["name"], f["line_number"]) for f in file_data["functions"]] == [("Make", 3)]
