"""scip-java can emit a Reference occurrence with an empty `range`
(e.g. for a synthetic/implicit call site). ScipIndexParser.parse used
to index straight into that empty list (`r[0]`), raising
`IndexError: list index out of range` and aborting the whole SCIP run
for the repo — with the caller (run_scip_index_async) catching only a
generic Exception and logging just str(e), no traceback.
"""

from pathlib import Path

from codegraphcontext.tools import scip_pb2
from codegraphcontext.tools.scip_indexer import ScipIndexParser

METHOD_SYMBOL = "scip-java maven . . java/Foo#bar()."


def _index_with_empty_reference_range() -> bytes:
    index = scip_pb2.Index()
    doc = index.documents.add()
    doc.relative_path = "Foo.java"
    doc.language = "java"

    definition = doc.occurrences.add()
    definition.symbol = METHOD_SYMBOL
    definition.symbol_roles = 1  # Definition
    definition.range.extend([2, 4, 10])

    reference = doc.occurrences.add()
    reference.symbol = METHOD_SYMBOL
    reference.symbol_roles = 0  # Reference, empty range on purpose

    sym_info = doc.symbols.add()
    sym_info.symbol = METHOD_SYMBOL
    sym_info.display_name = "bar()"
    sym_info.kind = 26  # Method

    return index.SerializeToString()


def test_reference_occurrence_with_empty_range_is_skipped_not_fatal(tmp_path: Path) -> None:
    scip_path = tmp_path / "index.scip"
    scip_path.write_bytes(_index_with_empty_reference_range())
    (tmp_path / "Foo.java").write_text("class Foo {\n    void bar() {\n    }\n}\n")

    result = ScipIndexParser().parse(scip_path, tmp_path)

    file_data = result["files"][str((tmp_path / "Foo.java").resolve())]
    assert [f["name"] for f in file_data["functions"]] == ["bar"]
    assert file_data["function_calls_scip"] == []
    assert file_data["module_level_calls_scip"] == []
