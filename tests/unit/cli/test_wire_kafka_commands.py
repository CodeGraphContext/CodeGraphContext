"""CLI: `cgc wire extract kafka` (PR #4)."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codegraphcontext.cli.main import app

runner = CliRunner()


def _make_kafka_repo(tmp_path: Path) -> Path:
    """Create a small repo with one producer, one consumer, and a resolvable placeholder."""
    src = tmp_path / "src/main/java/com/acme"
    src.mkdir(parents=True)
    (src / "Prod.java").write_text("""
        package com.acme;
        import org.springframework.kafka.core.KafkaTemplate;
        class Prod { void publish() { kafkaTemplate.send("${kafka.topic.orders}", p); } }
    """, encoding="utf-8")
    (src / "Cons.java").write_text("""
        package com.acme;
        import org.springframework.kafka.annotation.KafkaListener;
        class Cons {
            @KafkaListener(topics = "orders-created")
            public void handle(String s) {}
        }
    """, encoding="utf-8")
    resources = tmp_path / "src/main/resources"
    resources.mkdir(parents=True)
    (resources / "application.properties").write_text(
        "kafka.topic.orders=orders-resolved\n", encoding="utf-8"
    )
    return tmp_path


def _parse_json_before_notice(stdout: str) -> dict:
    """Peel the trailing MULTI_REPO_LINKS notice off before json.loads."""
    start = stdout.find("{")
    payload, _end = json.JSONDecoder().raw_decode(stdout[start:])
    return payload


def test_extract_kafka_table_runs_without_error(tmp_path: Path):
    """Table renderer is a preview UI; content assertions run against `--format json`.

    Rich's Console captures terminal width at import time, so CliRunner cannot
    reliably widen it for row content in this process. We only assert that the
    table command exits cleanly and emits the group headers + summary line.
    """
    _make_kafka_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "extract", "kafka", "--repo", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "Kafka producers (1)" in result.stdout
    assert "MULTI_REPO_LINKS" in result.stdout


def test_extract_kafka_json_output_is_machine_readable(tmp_path: Path):
    _make_kafka_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "extract", "kafka", "--repo", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0
    payload = _parse_json_before_notice(result.stdout)
    assert payload["profile"] == ""
    assert len(payload["producers"]) == 1
    assert payload["producers"][0]["topic_resolved"] == "orders-resolved"
    assert payload["producers"][0]["confidence"] == "INFERRED"
    assert len(payload["consumers"]) == 1
    assert payload["consumers"][0]["topic_raw"] == "orders-created"


def test_extract_kafka_active_profile_wins_over_base(tmp_path: Path):
    repo = _make_kafka_repo(tmp_path)
    (repo / "src/main/resources/application-prod.properties").write_text(
        "kafka.topic.orders=orders-prod\n", encoding="utf-8"
    )
    result = runner.invoke(
        app, ["wire", "extract", "kafka", "--repo", str(repo),
              "--profile", "prod", "--format", "json"]
    )
    assert result.exit_code == 0
    payload = _parse_json_before_notice(result.stdout)
    assert payload["profile"] == "prod"
    assert payload["producers"][0]["topic_resolved"] == "orders-prod"


def test_extract_kafka_empty_repo_is_ok(tmp_path: Path):
    result = runner.invoke(
        app, ["wire", "extract", "kafka", "--repo", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0
    payload = _parse_json_before_notice(result.stdout)
    assert payload["producers"] == []
    assert payload["consumers"] == []


def test_extract_kafka_unknown_format_exits_nonzero(tmp_path: Path):
    _make_kafka_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "extract", "kafka", "--repo", str(tmp_path), "--format", "yaml"]
    )
    assert result.exit_code != 0
    assert "Unknown --format" in result.stdout


def test_extract_kafka_json_payload_records_files_scanned(tmp_path: Path):
    _make_kafka_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "extract", "kafka", "--repo", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0
    payload = _parse_json_before_notice(result.stdout)
    # Prod.java + Cons.java under src/main/java, both scanned.
    assert payload["files_scanned"] == 2
    assert payload["files_skipped"] == 0
    assert payload["repo"].endswith(str(tmp_path.name)) or Path(payload["repo"]) == tmp_path.resolve()


def test_extract_kafka_json_records_fqn_and_call_shape(tmp_path: Path):
    _make_kafka_repo(tmp_path)
    result = runner.invoke(
        app, ["wire", "extract", "kafka", "--repo", str(tmp_path), "--format", "json"]
    )
    payload = _parse_json_before_notice(result.stdout)
    assert payload["producers"][0]["fqn"] == "com.acme.Prod.publish"
    assert payload["producers"][0]["call_shape"] == "template.send"
    assert payload["consumers"][0]["fqn"] == "com.acme.Cons.handle"
    assert payload["consumers"][0]["is_pattern"] is False
