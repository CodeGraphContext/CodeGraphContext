"""A call of a parameter with no callback target (`fn()` in `def apply(fn)`) is a
Function->Parameter CALLS edge, written on a real embedded database.

The writer filtered the target on `line_number`, which a Parameter does not have
(it stores `function_line_number`): Kùzu/LadybugDB refused every such batch and
Neo4j/FalkorDB matched nothing.
"""

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("kuzu")

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.core.jobs import JobManager
from codegraphcontext.tools.graph_builder import GraphBuilder


def _fresh_kuzu_manager(db_path: Path) -> KuzuDBManager:
    if KuzuDBManager._instance is not None:
        KuzuDBManager._instance.close_driver()
    KuzuDBManager._instance = None
    KuzuDBManager._db = None
    KuzuDBManager._pool = None
    KuzuDBManager._conn = None
    return KuzuDBManager(db_path=str(db_path))


@pytest.mark.integration
def test_parameter_call_edges_are_written(tmp_path, monkeypatch):
    monkeypatch.setenv("DEFAULT_DATABASE", "kuzudb")
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "kuzudb")
    monkeypatch.setenv("SCIP_INDEXER", "false")
    monkeypatch.setenv("ENABLE_INHERIT_RESOLVE", "false")
    monkeypatch.setenv("ENABLE_VECTOR_RESOLVE", "false")

    repo = tmp_path / "param_calls"
    repo.mkdir()
    (repo / "m.py").write_text("def apply(fn):\n    return fn()\n", encoding="utf-8")

    manager = _fresh_kuzu_manager(tmp_path / "kuzu-db")
    try:
        job_manager = JobManager()

        async def index() -> None:
            builder = GraphBuilder(manager, job_manager, asyncio.get_running_loop())
            job_id = job_manager.create_job(str(repo), is_dependency=False)
            await builder.build_graph_from_path_async(repo, job_id=job_id)

        asyncio.run(index())
        with manager.get_driver().session() as session:
            rows = session.run(
                "MATCH (:Function {name: 'apply'})-[r:CALLS]->(p:Parameter {name: 'fn'}) RETURN count(r) AS n"
            ).data()
        assert rows[0]["n"] == 1
    finally:
        manager.close_driver()
