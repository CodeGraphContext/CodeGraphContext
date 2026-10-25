"""Unit tests for wire.python_extractor (MULTI_REPO_LINKS PR #7)."""
from __future__ import annotations

from pathlib import Path

from codegraphcontext.wire import (
    extract_python_from_source,
    looks_like_python_http_source,
)


P = Path("app.py")


def _extract(src: str):
    return extract_python_from_source(src, P)


def test_looks_like_triggers_on_common_imports():
    assert looks_like_python_http_source("from flask import Flask")
    assert looks_like_python_http_source("from fastapi import APIRouter")
    assert not looks_like_python_http_source("print('hi')")


def test_flask_route_defaults_to_get():
    src = """
from flask import Flask
app = Flask(__name__)
@app.route("/hello")
def hello():
    return "hi"
"""
    r = _extract(src)
    assert len(r.servers) == 1
    s = r.servers[0]
    assert s.method == "GET"
    assert s.path == "/hello"
    assert s.framework == "flask"
    assert s.fqn == "app.hello"


def test_flask_route_with_methods_list_expands_verbs():
    src = """
from flask import Flask
app = Flask(__name__)
@app.route("/thing", methods=["POST", "PUT"])
def thing(): pass
"""
    r = _extract(src)
    verbs = sorted(s.method for s in r.servers)
    assert verbs == ["POST", "PUT"]


def test_fastapi_shorthand_decorators():
    src = """
from fastapi import FastAPI
app = FastAPI()
@app.get("/items")
def list_items(): pass
@app.post("/items")
def create_item(): pass
"""
    r = _extract(src)
    pairs = {(s.method, s.path) for s in r.servers}
    assert ("GET", "/items") in pairs
    assert ("POST", "/items") in pairs
    assert all(s.framework == "fastapi" for s in r.servers)


def test_router_decorator_supported():
    src = """
from fastapi import APIRouter
router = APIRouter()
@router.get("/x")
def x(): pass
"""
    r = _extract(src)
    assert len(r.servers) == 1
    assert r.servers[0].path == "/x"


def test_non_http_source_yields_empty():
    r = _extract("import os\nprint('hi')")
    assert r.is_empty()
