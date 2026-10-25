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
def test_hcl_fixture_indexes_end_to_end_with_kuzu(tmp_path, sample_projects_path, monkeypatch):
    """The HCL properties land in the embedded backend's declared columns, and a local module
    meets every configuration that consumes it on one Module node."""
    if not get_tree_sitter_manager().is_language_available("hcl"):
        pytest.skip("HCL tree-sitter grammar is not available")

    monkeypatch.setenv("DEFAULT_DATABASE", "kuzudb")
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "kuzudb")
    monkeypatch.setenv("SCIP_INDEXER", "false")
    monkeypatch.setenv("ENABLE_INHERIT_RESOLVE", "false")
    monkeypatch.setenv("ENABLE_VECTOR_RESOLVE", "false")

    repo = tmp_path / "sample_project_hcl"
    shutil.copytree(sample_projects_path / "sample_project_hcl", repo)
    repo = repo.resolve()

    manager = _fresh_kuzu_manager(tmp_path / "kuzu-db")
    try:
        job_manager = JobManager()

        async def index_fixture() -> str:
            builder = GraphBuilder(manager, job_manager, asyncio.get_running_loop())
            job_id = job_manager.create_job(str(repo), is_dependency=False)
            await builder.build_graph_from_path_async(repo, job_id=job_id)
            return job_id

        job = job_manager.get_job(asyncio.run(index_fixture()))
        assert job is not None
        assert job.status == JobStatus.COMPLETED

        with manager.get_driver().session() as session:
            files = session.run("""
                MATCH (f:File) WHERE f.language = 'hcl'
                RETURN f.relative_path AS relative_path
                """).data()
            assert {row["relative_path"] for row in files} == {
                "main.tf",
                "terraform.tfvars",
                "root.hcl",
                "modules/bucket/main.tf",
                "live/vpc/terragrunt.hcl",
                "live/app/terragrunt.hcl",
            }

            blocks = session.run("""
                MATCH (c:Class) WHERE c.lang = 'hcl'
                RETURN c.name AS name, c.node_type AS node_type
                """).data()
            assert {
                ("provider.aws", "provider"),
                ("aws_s3_bucket.artifacts", "resource"),
                ("data.aws_caller_identity.current", "data"),
                ("module.network", "module"),
                ("module.logs", "module"),
                ("generate.provider", "generate"),
                ("dependency.vpc", "dependency"),
            }.issubset({(row["name"], row["node_type"]) for row in blocks})
            assert not any(row["name"].startswith("provider.registry") for row in blocks)

            variables = {
                row["name"]: row
                for row in session.run("""
                    MATCH (v:Variable) WHERE v.lang = 'hcl'
                    RETURN v.name AS name, v.value AS value, v.docstring AS docstring
                    """).data()
            }
            assert variables["var.bucket_name"]["docstring"] == (
                "Name of the artifact bucket.\nMust be globally unique."
            )
            assert variables["var.bucket_name"]["value"] == '"example-artifacts"'
            assert {"output.bucket_arn", "local.tags", "inputs", "region"} <= set(variables)

            consumers = session.run("""
                MATCH (f:File)-[:IMPORTS]->(m:Module)
                MATCH (d:Directory {path: m.name})
                RETURN f.relative_path AS consumer, d.path AS module_dir
                """).data()
            assert {(row["consumer"], row["module_dir"]) for row in consumers} == {
                ("main.tf", (repo / "modules" / "bucket").as_posix()),
                ("live/app/terragrunt.hcl", (repo / "modules" / "bucket").as_posix()),
                ("live/app/terragrunt.hcl", (repo / "live" / "vpc").as_posix()),
            }

            modules = {row["name"] for row in session.run(
                "MATCH (:File)-[:IMPORTS]->(m:Module) RETURN DISTINCT m.name AS name"
            ).data()}
            assert not any("find_in_parent_folders" in name for name in modules)

        advanced_query = Advanced_language_query(manager).advanced_language_query("hcl", "class")
        assert advanced_query["success"] is True
        assert {"aws_s3_bucket.artifacts", "module.logs"} <= {
            row["name"] for row in advanced_query["results"]
        }
    finally:
        manager.close_driver()
