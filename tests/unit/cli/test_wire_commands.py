"""CLI: `cgc wire` subgroup (PR #2)."""

import json
from pathlib import Path

from typer.testing import CliRunner

from codegraphcontext.cli.main import app


runner = CliRunner()


def test_wire_example_prints_valid_yaml():
    result = runner.invoke(app, ["wire", "example"])
    assert result.exit_code == 0
    assert "version: 1" in result.output
    assert "topics:" in result.output
    assert "endpoints:" in result.output


def test_wire_validate_accepts_generated_example(tmp_path: Path):
    example_result = runner.invoke(app, ["wire", "example"])
    (tmp_path / ".cgc").mkdir()
    (tmp_path / ".cgc" / "wire.yml").write_text(example_result.output, encoding="utf-8")

    result = runner.invoke(app, ["wire", "validate", str(tmp_path / ".cgc" / "wire.yml")])
    assert result.exit_code == 0
    assert "valid" in result.output


def test_wire_validate_rejects_bad_file(tmp_path: Path):
    bad = tmp_path / "wire.yml"
    bad.write_text("version: 999\n", encoding="utf-8")
    result = runner.invoke(app, ["wire", "validate", str(bad)])
    assert result.exit_code == 1
    assert "Invalid wire.yml" in result.output


def test_wire_validate_reports_missing_file(tmp_path: Path):
    result = runner.invoke(app, ["wire", "validate", str(tmp_path / "nope.yml")])
    assert result.exit_code == 2
    assert "not found" in result.output.lower()


def test_wire_list_reports_zero_when_no_sources(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CGC_WIRE", raising=False)
    result = runner.invoke(app, ["wire", "list", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "Wire hint sources" in result.output
    assert "Merged: 0 topics, 0 endpoints, 0 aliases" in result.output


def test_wire_list_counts_repo_hints(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CGC_WIRE", raising=False)
    (tmp_path / ".cgc").mkdir()
    (tmp_path / ".cgc" / "wire.yml").write_text(
        "version: 1\ntopics:\n  - {system: kafka, name: orders, produced_by: [pkg.P.pub]}\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["wire", "list", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "Merged: 1 topics" in result.output


def test_wire_show_json_shape(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CGC_WIRE", raising=False)
    (tmp_path / ".cgc").mkdir()
    (tmp_path / ".cgc" / "wire.yml").write_text(
        "version: 1\ntopics:\n  - {system: kafka, name: orders, produced_by: [pkg.P.pub]}\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["wire", "show", "--repo", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    # CliRunner captures stderr into stdout; the MULTI_REPO_LINKS notice trails
    # the JSON payload. raw_decode reads just the first complete JSON object.
    stdout = result.output.strip()
    start = stdout.index("{")
    payload, _end = json.JSONDecoder().raw_decode(stdout[start:])
    assert payload["counts_by_source"]["repo"] == 1
    assert payload["topics"][0]["name"] == "orders"


def test_wire_show_unknown_format_errors(tmp_path: Path):
    result = runner.invoke(app, ["wire", "show", "--repo", str(tmp_path), "--format", "toml"])
    assert result.exit_code == 2
    assert "Unknown --format" in result.output
