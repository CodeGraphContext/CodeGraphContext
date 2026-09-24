"""CLI: `cgc wire config` subgroup (PR #3)."""

from pathlib import Path

from typer.testing import CliRunner

from codegraphcontext.cli.main import app

runner = CliRunner()


def _make_repo(tmp_path: Path) -> Path:
    resources = tmp_path / "src/main/resources"
    resources.mkdir(parents=True)
    (resources / "application.properties").write_text(
        "kafka.topic.orders=orders-base\ngrpc.host=localhost\n", encoding="utf-8"
    )
    (resources / "application-prod.yml").write_text(
        "kafka:\n  topic:\n    orders: orders-prod\n", encoding="utf-8"
    )
    return tmp_path


def test_wire_config_list_shows_all_entries(tmp_path: Path):
    _make_repo(tmp_path)
    result = runner.invoke(app, ["wire", "config", "list", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "kafka.topic.orders" in result.output
    assert "orders-base" in result.output
    assert "orders-prod" in result.output
    # Profile column shows both (base) and prod.
    assert "(base)" in result.output
    assert "prod" in result.output


def test_wire_config_list_filters_by_profile(tmp_path: Path):
    _make_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "config", "list", "--repo", str(tmp_path), "--profile", "prod"]
    )
    assert result.exit_code == 0
    assert "orders-prod" in result.output
    assert "orders-base" not in result.output


def test_wire_config_list_filters_by_key(tmp_path: Path):
    _make_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "config", "list", "--repo", str(tmp_path), "--key", "kafka"]
    )
    assert result.exit_code == 0
    assert "kafka.topic.orders" in result.output
    assert "grpc.host" not in result.output


def test_wire_config_resolve_success(tmp_path: Path):
    _make_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "config", "resolve", "${kafka.topic.orders}", "--repo", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "orders-base" in result.output


def test_wire_config_resolve_profile_wins(tmp_path: Path):
    _make_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "config", "resolve", "${kafka.topic.orders}",
              "--repo", str(tmp_path), "--profile", "prod"],
    )
    assert result.exit_code == 0
    assert "orders-prod" in result.output


def test_wire_config_resolve_unresolved_exits_nonzero(tmp_path: Path):
    _make_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "config", "resolve", "${no.such.key}", "--repo", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "unresolved" in result.output.lower()


def test_wire_config_resolve_default_used_when_key_missing(tmp_path: Path):
    _make_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "config", "resolve", "${no.such.key:fallback}", "--repo", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "fallback" in result.output
