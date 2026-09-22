"""CLI: `cgc wire extract {http,grpc,python,go}` and `cgc wire discover` (PR #5-#8)."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codegraphcontext.cli.main import app

runner = CliRunner()


def _parse_json_before_notice(stdout: str) -> dict:
    start = stdout.find("{")
    payload, _end = json.JSONDecoder().raw_decode(stdout[start:])
    return payload


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ── extract http ────────────────────────────────────────────────────────────

def test_extract_http_json(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Api.java", """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api { @GetMapping("/x") public void x() {} }
    """)
    result = runner.invoke(app, ["wire", "extract", "http", "--repo", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    payload = _parse_json_before_notice(result.stdout)
    assert len(payload["servers"]) == 1
    assert payload["servers"][0]["path"] == "/x"


def test_extract_http_table_runs_cleanly(tmp_path: Path):
    result = runner.invoke(app, ["wire", "extract", "http", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "HTTP servers" in result.stdout
    assert "MULTI_REPO_LINKS" in result.stdout


def test_extract_http_unknown_format_exits_nonzero(tmp_path: Path):
    result = runner.invoke(app, ["wire", "extract", "http", "--repo", str(tmp_path), "--format", "bogus"])
    assert result.exit_code != 0


# ── extract grpc ────────────────────────────────────────────────────────────

def test_extract_grpc_json(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Impl.java", """
        package com.acme;
        import io.grpc.stub.StreamObserver;
        public class OrdersImpl extends OrdersServiceGrpc.OrdersServiceImplBase {
            public void createOrder(Req r, StreamObserver<Resp> o) {}
        }
    """)
    result = runner.invoke(app, ["wire", "extract", "grpc", "--repo", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    payload = _parse_json_before_notice(result.stdout)
    assert len(payload["servers"]) == 1
    assert payload["servers"][0]["service"] == "OrdersService"


def test_extract_grpc_table_runs_cleanly(tmp_path: Path):
    result = runner.invoke(app, ["wire", "extract", "grpc", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "gRPC servers" in result.stdout


# ── extract python ──────────────────────────────────────────────────────────

def test_extract_python_json(tmp_path: Path):
    _write(tmp_path / "app.py", """
from flask import Flask
app = Flask(__name__)
@app.route("/x")
def x(): return "hi"
""")
    result = runner.invoke(app, ["wire", "extract", "python", "--repo", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    payload = _parse_json_before_notice(result.stdout)
    assert len(payload["servers"]) == 1
    assert payload["servers"][0]["framework"] == "flask"


# ── extract go ──────────────────────────────────────────────────────────────

def test_extract_go_json(tmp_path: Path):
    _write(tmp_path / "main.go", """
package main
import "github.com/gin-gonic/gin"
func main() { r := gin.Default(); r.GET("/x", h) }
""")
    result = runner.invoke(app, ["wire", "extract", "go", "--repo", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    payload = _parse_json_before_notice(result.stdout)
    assert len(payload["servers"]) == 1
    assert payload["servers"][0]["method"] == "GET"


# ── discover ────────────────────────────────────────────────────────────────

def test_discover_json_finds_matched_topic(tmp_path: Path):
    a = tmp_path / "repoA"; b = tmp_path / "repoB"
    _write(a / "src/main/java/com/acme/Prod.java", """
        package com.acme;
        import org.springframework.kafka.core.KafkaTemplate;
        class Prod { KafkaTemplate<String,String> kt; void go() { kt.send("orders", "p"); } }
    """)
    _write(b / "src/main/java/com/acme/Cons.java", """
        package com.acme;
        import org.springframework.kafka.annotation.KafkaListener;
        class Cons { @KafkaListener(topics = "orders") public void h(String s) {} }
    """)
    result = runner.invoke(app, ["wire", "discover", "--repo", str(a), "--repo", str(b), "--format", "json"])
    assert result.exit_code == 0
    payload = _parse_json_before_notice(result.stdout)
    matched = [t for t in payload["topics"] if t["matched"]]
    assert len(matched) == 1
    assert matched[0]["name"] == "orders"


def test_discover_table_runs_cleanly(tmp_path: Path):
    result = runner.invoke(app, ["wire", "discover", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "Matched" in result.stdout
    assert "MULTI_REPO_LINKS" in result.stdout


def test_discover_unknown_format_exits_nonzero(tmp_path: Path):
    result = runner.invoke(app, ["wire", "discover", "--repo", str(tmp_path), "--format", "bogus"])
    assert result.exit_code != 0
