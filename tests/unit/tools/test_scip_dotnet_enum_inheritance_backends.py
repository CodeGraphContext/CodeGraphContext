"""The INHERITS edges of a scip-dotnet enum are written from the node that the index's kinds give it."""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.tools.indexing.resolution.inheritance import build_inheritance_and_csharp_files
from codegraphcontext.tools.scip_indexer import ScipIndexParser

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "scip_dotnet_kinds"
INTERFACES = ["IComparable", "IConvertible", "IFormattable", "ISpanFormattable"]


@pytest.fixture()
def graph(tmp_path: Path):
    # The two native engines must run in separate interpreters.
    backend = os.environ.get("CGC_SCIP_ENUM_TEST_BACKEND", "kuzudb")
    pytest.importorskip("ladybug" if backend == "ladybugdb" else "kuzu")
    if backend == "ladybugdb":
        from codegraphcontext.core import ladybugdb_unavailable_reason
        reason = ladybugdb_unavailable_reason()
        if reason:
            pytest.skip(reason)
        from codegraphcontext.core.database_ladybug import LadybugDBManager as Manager
    else:
        from codegraphcontext.core.database_kuzu import KuzuDBManager as Manager
    manager = Manager(str(tmp_path / "db"))
    driver = manager.get_driver()
    writer = GraphWriter(driver, SimpleNamespace(get_backend_type=lambda: backend))
    writer.add_repository_to_graph(FIXTURE.resolve())
    yield writer, driver
    manager.close_driver()


@pytest.mark.parametrize(
    "index_name, label",
    [("scip-dotnet-v0.2.16.scip", "Class"), ("scip-dotnet-a8d080c.scip", "Enum")],
)
def test_enum_inheritance_is_written_from_the_enum_node(graph, index_name: str, label: str) -> None:
    writer, driver = graph
    files = ScipIndexParser().parse(FIXTURE / index_name, FIXTURE)["files"]
    written = [fd for path, fd in files.items() if Path(path).exists()]
    for fd in written:
        fd["repo_path"] = str(FIXTURE.resolve())
        writer.add_file_to_graph(fd, "scip_dotnet_kinds", {})
    rows, csharp_files = build_inheritance_and_csharp_files(written, {})
    writer.write_inheritance_links(rows, csharp_files, {})

    with driver.session() as session:
        edges = session.run(
            "MATCH (c {name: 'Color'})-[:INHERITS]->(p) RETURN labels(c)[0] AS child, labels(p)[0] AS parent, p.name AS name"
        ).data()
        colors = session.run("MATCH (c {name: 'Color'}) RETURN labels(c)[0] AS label").data()
    assert sorted((e["child"], e["parent"], e["name"]) for e in edges) == [(label, "ExternalClass", n) for n in INTERFACES]
    assert [c["label"] for c in colors] == [label]


def test_ladybug_writes_the_same_enum_inheritance() -> None:
    env = {**os.environ, "CGC_SCIP_ENUM_TEST_BACKEND": "ladybugdb"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-q", "-k", "written_from_the_enum_node", "-p", "no:cacheprovider"],
        env=env, capture_output=True, text=True, timeout=120,
    )
    output = result.stdout + result.stderr
    if "2 skipped" in result.stdout:
        pytest.skip("Ladybug native engine is unavailable in the subprocess")
    assert result.returncode == 0, output
    assert "2 passed" in result.stdout, output
