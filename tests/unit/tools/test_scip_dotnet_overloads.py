"""Tests for scip-dotnet overload symbols."""

from pathlib import Path

from codegraphcontext.tools import scip_pb2
from codegraphcontext.tools.scip_indexer import ScipIndexParser

PREFIX = "scip-dotnet nuget . . Overloads/"
SOURCE = """namespace Overloads
{
    public class Calc
    {
        public void M() { }
        public void M(int x) { }
        public void M(string x) { }

        public void Caller()
        {
            M();
            M(1);
            M("a");
        }
    }
}
"""
OCCURRENCES = [
    ("Calc#", [2, 17, 21], 1),
    ("Calc#M().", [4, 20, 21], 1),
    ("Calc#M(+1).", [5, 20, 21], 1),
    ("Calc#M(+1).(x)", [5, 26, 27], 1),
    ("Calc#M(+2).", [6, 20, 21], 1),
    ("Calc#M(+2).(x)", [6, 29, 30], 1),
    ("Calc#Caller().", [8, 20, 26], 1),
    ("Calc#M().", [10, 12, 13], 0),
    ("Calc#M(+1).", [11, 12, 13], 0),
    ("Calc#M(+2).", [12, 12, 13], 0),
]


def _parse(tmp_path: Path) -> dict:
    index = scip_pb2.Index()
    doc = index.documents.add()
    doc.relative_path = "Calc.cs"
    doc.language = "C#"
    for suffix, rng, roles in OCCURRENCES:
        occ = doc.occurrences.add()
        occ.symbol = PREFIX + suffix
        occ.range.extend(rng)
        occ.symbol_roles = roles
    for suffix in dict.fromkeys(s for s, _, roles in OCCURRENCES if roles & 1):
        info = doc.symbols.add()
        info.symbol = PREFIX + suffix
        info.kind = 0
    scip_path = tmp_path / "index.scip"
    scip_path.write_bytes(index.SerializeToString())
    (tmp_path / "Calc.cs").write_text(SOURCE)
    result = ScipIndexParser().parse(scip_path, tmp_path)
    return result["files"][str((tmp_path / "Calc.cs").resolve())]


def test_every_dotnet_overload_definition_becomes_a_function_node(tmp_path: Path) -> None:
    file_data = _parse(tmp_path)
    assert sorted(f["line_number"] for f in file_data["functions"]) == [5, 6, 7, 9]


def test_dotnet_overload_names_drop_the_disambiguator(tmp_path: Path) -> None:
    parser = ScipIndexParser()
    assert parser._name_from_symbol(PREFIX + "Calc#M().") == "M"
    assert parser._name_from_symbol(PREFIX + "Calc#M(+1).") == "M"
    assert parser._name_from_symbol(PREFIX + "Calc#M(+12).") == "M"

    file_data = _parse(tmp_path)
    calls = file_data["function_calls_scip"] + file_data["module_level_calls_scip"]
    assert sorted((c["ref_line"], c["callee_name"]) for c in calls) == [(11, "M"), (12, "M"), (13, "M")]
    assert len({c["callee_symbol"] for c in calls}) == 3
