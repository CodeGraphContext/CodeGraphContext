"""#1673: the SCIP pipeline must converge with the discovery census.

A user with a mixed C#/other repo saw `cgc index .` report
"repository '.' has only 32 of 46 files indexed. Continuing." on EVERY run,
forever, and the run finished with no summary at all. Root causes: files
whose supplemental Tree-sitter parse errored (or whose write raised) got no
File node of any kind, and the SCIP path never populated the CLI summary.

Driven with a fake scip module against a real embedded database.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.graph_builder import GraphBuilder
from codegraphcontext.tools.indexing.scip_pipeline import run_scip_index_async
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

kuzu = pytest.importorskip("kuzu")


class _DBM:
    def __init__(self, driver):
        self._driver = driver

    def get_driver(self, graph_name=None):
        return self._driver

    def get_backend_type(self):
        return "kuzudb"


class _JM:
    def update_job(self, *a, **k):
        pass


def _fake_scip_module(covered_file: Path):
    """A scip_indexer module double: 'indexes' exactly one file."""

    class FakeIndexer:
        def run(self, path, lang, tmpdir):
            return Path(tmpdir) / "index.scip"  # existence is not checked

    class FakeParser:
        def parse(self, scip_file, path):
            return {
                "files": {
                    str(covered_file.resolve()): {
                        "path": str(covered_file.resolve()),
                        "lang": "c_sharp",
                        "imports": [],
                        "functions": [
                            {"name": "Covered", "line_number": 1, "end_line": 2, "args": []}
                        ],
                        "classes": [],
                        "variables": [],
                        "function_calls_scip": [],
                        "module_level_calls_scip": [],
                    }
                }
            }

    return SimpleNamespace(ScipIndexer=FakeIndexer, ScipIndexParser=FakeParser)


def test_scip_run_converges_with_discovery_census(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    covered = repo / "Program.cs"
    covered.write_text("class P { void Covered() {} }\n", encoding="utf-8")
    (repo / "helper.py").write_text("def helper():\n    pass\n", encoding="utf-8")
    (repo / "README.md").write_text("# readme\n", encoding="utf-8")
    (repo / "notes.json").write_text("{}\n", encoding="utf-8")

    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        gb = GraphBuilder(_DBM(driver), _JM(), asyncio.new_event_loop())
        summary: dict = {}
        asyncio.new_event_loop().run_until_complete(
            run_scip_index_async(
                repo,
                False,
                None,
                "c_sharp",
                gb._writer,
                _JM(),
                gb.parsers.keys(),
                gb.get_parser,
                _fake_scip_module(covered),
                None,
                index_summary=summary,
            )
        )

        # Every discovered file must have a File node under the repository —
        # the resume check compares exactly these two numbers.
        expected_count = gb.estimate_processing_time(repo)[0]
        with driver.session() as s:
            row = s.run(
                "MATCH (r:Repository {path: $p})-[:CONTAINS*]->(f:File) "
                "RETURN count(DISTINCT f) AS c",
                p=str(repo.resolve()),
            ).data()[0]
        assert row["c"] >= expected_count, (
            f"graph has {row['c']} File nodes but discovery counts "
            f"{expected_count} — 'only N of M files indexed' would loop forever"
        )

        # And the run must produce a summary (it used to finish silently).
        assert summary.get("total_scanned_files", 0) >= 1
        assert "files_by_extension" in summary
    finally:
        manager.close_driver()


def test_supplement_parse_failure_still_records_the_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    covered = repo / "Program.cs"
    covered.write_text("class P {}\n", encoding="utf-8")
    broken = repo / "broken.py"
    broken.write_text("def x():\n    pass\n", encoding="utf-8")

    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        gb = GraphBuilder(_DBM(driver), _JM(), asyncio.new_event_loop())

        real_get_parser = gb.get_parser

        class _ExplodingParser:
            def parse(self, *a, **k):
                raise RuntimeError("simulated parser crash under load")

        def flaky_get_parser(suffix):
            if suffix == ".py":
                return _ExplodingParser()
            return real_get_parser(suffix)

        asyncio.new_event_loop().run_until_complete(
            run_scip_index_async(
                repo, False, None, "c_sharp", gb._writer, _JM(),
                gb.parsers.keys(), flaky_get_parser, _fake_scip_module(covered),
                None, index_summary={},
            )
        )
        with driver.session() as s:
            row = s.run(
                "MATCH (f:File) WHERE f.path ENDS WITH 'broken.py' RETURN count(f) AS c"
            ).data()[0]
        assert row["c"] == 1, "a file whose parse crashed vanished from the graph"
    finally:
        manager.close_driver()
