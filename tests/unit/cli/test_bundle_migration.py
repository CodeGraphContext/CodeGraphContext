from typer.testing import CliRunner

from codegraphcontext.cli import main as cli
from codegraphcontext.core import backend_migration as migration


def test_migration_cli_delegates_without_initializing_active_context(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "_load_credentials", lambda: None)
    def reject_context(*args):
        raise AssertionError("context opened")

    monkeypatch.setattr(cli, "_initialize_services", reject_context)
    monkeypatch.setattr(migration, "migrate_graph", lambda *args, **kwargs: calls.append((args, kwargs)) or "migrated")
    checkpoint = tmp_path / "graph.cgc"
    result = CliRunner().invoke(cli.app, [
        "bundle", "migrate", str(checkpoint), "--from", "kuzudb", "--to", "ladybugdb",
        "--source-path", str(tmp_path / "old"), "--target-path", str(tmp_path / "new"),
        "--source-python", "/older/python",
    ])
    assert result.exit_code == 0, result.output
    args, kwargs = calls[0]
    assert args == (
        migration.DatabaseLocation("kuzudb", tmp_path / "old"),
        migration.DatabaseLocation("ladybugdb", tmp_path / "new"),
        checkpoint,
    )
    assert kwargs == {"source_python": "/older/python"}


def test_migration_cli_failure_is_nonzero(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_load_credentials", lambda: None)

    def fail(*args, **kwargs):
        raise migration.MigrationError("target is occupied")

    monkeypatch.setattr(migration, "migrate_graph", fail)
    result = CliRunner().invoke(cli.app, [
        "bundle", "migrate", str(tmp_path / "graph.cgc"), "--from", "neo4j", "--to", "ladybugdb",
    ])
    assert result.exit_code == 1
    assert "target is occupied" in result.output


def test_migration_cli_rejects_unknown_backend_before_opening_databases():
    result = CliRunner().invoke(cli.app, ["bundle", "migrate", "graph.cgc", "--from", "typo", "--to", "neo4j"])
    assert result.exit_code == 2
    assert "Unknown backend" in result.output
