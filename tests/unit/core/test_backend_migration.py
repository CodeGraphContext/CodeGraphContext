"""Migration safety and process boundaries without loading native drivers."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core import backend_migration as migration
from codegraphcontext.core.backend_migration import DatabaseLocation, MigrationError


@pytest.fixture
def locations(tmp_path):
    source = tmp_path / "source"
    source.touch()
    return DatabaseLocation("kuzudb", source), DatabaseLocation("ladybugdb", tmp_path / "target")


def test_export_and_import_are_isolated_and_keep_checkpoint(monkeypatch, tmp_path, locations):
    calls = []
    monkeypatch.setenv("CGC_RUNTIME_DB_PATH", "/unrelated-context")
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "neo4j")

    def run(command, **kwargs):
        calls.append((command, kwargs["env"]))
        if command[3] == "export":
            Path(command[5]).write_bytes(b"exported graph")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(migration.subprocess, "run", run)
    checkpoint = tmp_path / "checkpoint.cgc"
    migration.migrate_graph(*locations, checkpoint, source_python="/older/python")

    assert [command[0] for command, _ in calls] == ["/older/python", sys.executable]
    assert [command[3] for command, _ in calls] == ["export", "import"]
    assert [env["CGC_RUNTIME_DB_TYPE"] for _, env in calls] == ["kuzudb", "ladybugdb"]
    assert all("CGC_RUNTIME_DB_PATH" not in env for _, env in calls)
    assert checkpoint.read_bytes() == b"exported graph"
    assert locations[0].path.exists()


@pytest.mark.parametrize("target_suffix", ["source", "source/child"])
def test_rejects_overlapping_database_paths(tmp_path, locations, target_suffix):
    with pytest.raises(MigrationError, match="must not overlap"):
        migration.migrate_graph(
            locations[0], DatabaseLocation("ladybugdb", tmp_path / target_suffix), tmp_path / "checkpoint.cgc"
        )


def test_rejects_bundle_inside_database(tmp_path, locations):
    with pytest.raises(MigrationError, match="outside both"):
        migration.migrate_graph(*locations, locations[1].path / "checkpoint.cgc")


def test_existing_checkpoint_is_never_overwritten(tmp_path, locations):
    checkpoint = tmp_path / "checkpoint.cgc"
    checkpoint.write_text("previous backup")
    with pytest.raises(MigrationError, match="Cannot create"):
        migration.migrate_graph(*locations, checkpoint)
    assert checkpoint.read_text() == "previous backup"


def test_missing_source_does_not_create_database(tmp_path, locations):
    locations[0].path.unlink()
    with pytest.raises(MigrationError, match="Source database does not exist"):
        migration.migrate_graph(*locations, tmp_path / "checkpoint.cgc")
    assert not locations[0].path.exists()


@pytest.mark.parametrize("backend", ["kuzudb", "ladybugdb", "falkordb"])
def test_embedded_endpoints_require_explicit_paths(backend):
    with pytest.raises(MigrationError, match="explicit database path"):
        DatabaseLocation(backend).normalized()


def test_remote_endpoint_rejects_misleading_local_path(tmp_path):
    with pytest.raises(MigrationError, match="connection settings"):
        DatabaseLocation("neo4j", tmp_path).normalized()


@pytest.mark.parametrize("failed_stage", ["export", "import"])
def test_failed_stage_stops_migration_and_preserves_only_complete_export(
    monkeypatch, tmp_path, locations, failed_stage
):
    stages = []

    def run(stage, location, checkpoint, python):
        stages.append(stage)
        if stage == failed_stage:
            raise MigrationError("driver unavailable")
        checkpoint.write_text("complete export")

    monkeypatch.setattr(migration, "_run_stage", run)
    checkpoint = tmp_path / "checkpoint.cgc"
    with pytest.raises(MigrationError, match="driver unavailable"):
        migration.migrate_graph(*locations, checkpoint)
    assert stages == (["export"] if failed_stage == "export" else ["export", "import"])
    assert checkpoint.exists() is (failed_stage == "import")


@pytest.fixture
def worker(monkeypatch):
    import codegraphcontext.core as core
    from codegraphcontext.core.cgc_bundle import CGCBundle

    manager = MagicMock()
    manager.get_backend_type.return_value = "neo4j"
    monkeypatch.setattr(core, "get_database_manager", lambda **kwargs: manager)
    importer = MagicMock(return_value=(True, "imported"))
    monkeypatch.setattr(CGCBundle, "import_from_bundle", importer)
    return manager, importer


@pytest.mark.parametrize("record", [None, {}, {"count": None}, {"count": 1}, {"count": "0"}])
def test_worker_refuses_populated_or_uncertain_target(worker, record, tmp_path):
    manager, importer = worker
    session = manager.get_driver.return_value.session.return_value.__enter__.return_value
    session.run.return_value.single.return_value = record
    with pytest.raises((MigrationError, KeyError)):
        migration._run_worker("import", "neo4j", tmp_path / "graph.cgc", "")
    importer.assert_not_called()
    manager.close_driver.assert_called_once()


def test_worker_does_not_import_when_empty_check_fails(worker, tmp_path):
    manager, importer = worker
    session = manager.get_driver.return_value.session.return_value.__enter__.return_value
    session.run.side_effect = RuntimeError("connection failed")
    with pytest.raises(RuntimeError, match="connection failed"):
        migration._run_worker("import", "neo4j", tmp_path / "graph.cgc", "")
    importer.assert_not_called()
    manager.close_driver.assert_called_once()


def test_worker_refuses_factory_fallback(worker, tmp_path):
    manager, importer = worker
    with pytest.raises(MigrationError, match="refusing fallback"):
        migration._run_worker("import", "falkordb", tmp_path / "graph.cgc", "")
    importer.assert_not_called()
    manager.close_driver.assert_called_once()


def test_worker_imports_into_confirmed_empty_target_without_clearing(worker, tmp_path):
    manager, importer = worker
    session = manager.get_driver.return_value.session.return_value.__enter__.return_value
    session.run.return_value.single.return_value = {"count": 0}
    checkpoint = tmp_path / "graph.cgc"
    migration._run_worker("import", "neo4j", checkpoint, "")
    importer.assert_called_once_with(checkpoint, clear_existing=False)
    manager.close_driver.assert_called_once()
