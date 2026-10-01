"""Unit tests for wire.language_scanner (MULTI_REPO_LINKS PR #7)."""
from __future__ import annotations

from pathlib import Path

from codegraphcontext.wire import scan_repo_go_http, scan_repo_python_http


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_python_scanner_finds_flask_route(tmp_path: Path):
    _write(tmp_path / "app.py", """
from flask import Flask
app = Flask(__name__)
@app.route("/x")
def x(): return "hi"
""")
    r = scan_repo_python_http(tmp_path)
    assert len(r.servers) == 1
    assert r.servers[0].path == "/x"


def test_python_scanner_ignores_files_without_triggers(tmp_path: Path):
    _write(tmp_path / "util.py", "def f(): return 1\n")
    r = scan_repo_python_http(tmp_path)
    assert r.servers == []
    assert r.files_scanned == 1


def test_go_scanner_finds_gin_route(tmp_path: Path):
    _write(tmp_path / "main.go", """
package main
import "github.com/gin-gonic/gin"
func main() { r := gin.Default(); r.GET("/x", h) }
""")
    r = scan_repo_go_http(tmp_path)
    assert len(r.servers) == 1
    assert r.servers[0].method == "GET"


def test_python_scanner_empty_repo(tmp_path: Path):
    r = scan_repo_python_http(tmp_path)
    assert r.servers == [] and r.files_scanned == 0
