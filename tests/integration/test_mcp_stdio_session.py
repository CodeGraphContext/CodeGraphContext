"""End-to-end MCP stdio session: initialize → tools/list → a real tool call.

This is how agents actually consume CGC; until now only the dispatcher was
tested (with mocks), so protocol-level breakage could ship unnoticed.
Hermetic: per-test HOME, embedded database.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def mcp_session(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "app.py").write_text("def greet(name):\n    return f'hi {name}'\n", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["DEFAULT_DATABASE"] = "kuzudb"
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    env["CGC_ALLOWED_ROOTS"] = str(repo)

    subprocess.run(
        [sys.executable, "-m", "codegraphcontext.cli.main", "index", str(repo)],
        capture_output=True, text=True, env=env, timeout=180, check=False,
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "codegraphcontext.cli.main", "mcp", "start"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env,
    )
    yield proc
    proc.kill()
    proc.wait(timeout=10)


def _send(proc, obj):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()


def _read_response(proc, want_id, max_lines=100):
    for _ in range(max_lines):
        line = proc.stdout.readline()
        if not line:
            return None
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want_id:
            return msg
    return None


def test_full_stdio_session(mcp_session):
    proc = mcp_session

    _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "test", "version": "0"}}})
    r = _read_response(proc, 1)
    assert r is not None and "result" in r, f"initialize failed: {r}"
    _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    r = _read_response(proc, 2)
    assert r is not None and "result" in r, f"tools/list failed: {r}"
    tools = {t["name"] for t in r["result"]["tools"]}
    assert "find_code" in tools and "add_code_to_graph" in tools
    assert len(tools) >= 20

    _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "find_code", "arguments": {"query": "greet"}}})
    r = _read_response(proc, 3)
    assert r is not None and "result" in r, f"tools/call failed: {r}"
    assert "greet" in json.dumps(r["result"]), "indexed function not found over MCP"
