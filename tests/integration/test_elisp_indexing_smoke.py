import asyncio
import shutil
from pathlib import Path

import pytest

pytest.importorskip("kuzu")

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.core.jobs import JobManager, JobStatus
from codegraphcontext.tools.advanced_language_query_tool import Advanced_language_query
from codegraphcontext.tools.graph_builder import GraphBuilder
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


def _fresh_kuzu_manager(db_path: Path) -> KuzuDBManager:
    if KuzuDBManager._instance is not None:
        KuzuDBManager._instance.close_driver()
    KuzuDBManager._instance = None
    KuzuDBManager._db = None
    KuzuDBManager._pool = None
    KuzuDBManager._conn = None
    return KuzuDBManager(db_path=str(db_path))


@pytest.mark.integration
def test_elisp_fixture_indexes_end_to_end_with_kuzu(
    tmp_path, sample_projects_path, monkeypatch
):
    if not get_tree_sitter_manager().is_language_available("elisp"):
        pytest.skip("Emacs Lisp tree-sitter grammar is not available")

    monkeypatch.setenv("DEFAULT_DATABASE", "kuzudb")
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "kuzudb")
    monkeypatch.setenv("SCIP_INDEXER", "false")
    monkeypatch.setenv("ENABLE_INHERIT_RESOLVE", "false")
    monkeypatch.setenv("ENABLE_VECTOR_RESOLVE", "false")

    source_repo = sample_projects_path / "sample_project_elisp"
    repo = tmp_path / "sample_project_elisp"
    shutil.copytree(source_repo, repo)

    manager = _fresh_kuzu_manager(tmp_path / "kuzu-db")
    try:
        job_manager = JobManager()

        async def index_fixture() -> str:
            builder = GraphBuilder(manager, job_manager, asyncio.get_running_loop())
            job_id = job_manager.create_job(str(repo), is_dependency=False)
            await builder.build_graph_from_path_async(repo, job_id=job_id)
            return job_id

        job_id = asyncio.run(index_fixture())
        job = job_manager.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED

        with manager.get_driver().session() as session:
            files = session.run("""
                MATCH (f:File)
                WHERE f.path ENDS WITH '.el'
                RETURN f.name AS file_name
                ORDER BY file_name
                """).data()
            assert {row["file_name"] for row in files} == {
                "foo-core.el",
                "foo-ui.el",
            }

            functions = session.run("""
                MATCH (fn:Function)
                WHERE fn.lang = 'elisp'
                RETURN fn.name AS function_name
                """).data()
            assert {
                "foo-core-format",
                "foo-core-greet",
                "foo-core-increment",
                "foo-core-with-name",
                "foo-ui-render",
                "foo-ui-after-render",
            }.issubset({row["function_name"] for row in functions})

            variables = session.run("""
                MATCH (v:Variable)
                WHERE v.lang = 'elisp'
                RETURN v.name AS variable_name
                """).data()
            assert {
                "foo-core-count",
                "foo-core-default-name",
                "foo-core-loud",
            }.issubset({row["variable_name"] for row in variables})

            imported_modules = session.run("""
                MATCH (:File)-[:IMPORTS]->(m:Module)
                RETURN m.name AS module_name
                """).data()
            assert {"cl-lib", "foo-core", "foo-ui"}.issubset(
                {row["module_name"] for row in imported_modules}
            )

            calls = session.run("""
                MATCH (caller:Function)-[:CALLS]->(callee:Function)
                WHERE caller.lang = 'elisp'
                RETURN caller.name AS caller_name, callee.name AS callee_name
                """).data()
            assert {
                ("foo-core-greet", "foo-core-format"),
                ("foo-core-greet", "foo-core-increment"),
                ("foo-ui-render", "foo-core-greet"),
                ("foo-ui-render", "foo-ui-after-render"),
            }.issubset({(row["caller_name"], row["callee_name"]) for row in calls})

        advanced_query = Advanced_language_query(manager).advanced_language_query(
            "elisp", "function"
        )
        assert advanced_query["success"] is True
        assert {
            "foo-core-greet",
            "foo-ui-render",
        }.issubset({row["name"] for row in advanced_query["results"]})
    finally:
        manager.close_driver()
