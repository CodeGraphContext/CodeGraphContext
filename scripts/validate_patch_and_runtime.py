#!/usr/bin/env python3
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_REPO = "/workspace/Subproject-HMM"
TARGET_SYMBOL = "get_or_create_stream_scheduler"
TARGET_CONTEXT = "/workspace/Subproject-HMM/hmm_pipeline_v3/core/context.py"

CHECKS = {
    "src/codegraphcontext/server.py": [
        "def _read_request_blocking(self) -> Tuple[Optional[dict], Optional[str]]:",
        "def _write_response(self, response: dict, framing: Optional[str]) -> None:",
        "request, framing = await loop.run_in_executor(None, self._read_request_blocking)",
        "self._write_response(response, framing)",
        "if ctx.database and not os.environ.get('CGC_RUNTIME_DB_TYPE'):",
    ],
    "src/codegraphcontext/tools/graph_builder.py": [
        "if backend_type == 'kuzudb':",
        "function_code_search_fts",
        "class_code_search_fts",
        "variable_code_search_fts",
    ],
    "src/codegraphcontext/tools/code_finder.py": [
        "self._is_kuzu = self._backend_type == 'kuzudb'",
        "def _ensure_kuzu_fts_indexes(self) -> None:",
        "def _query_kuzu_fts(self, label: str, search_term: str, repo_path: Optional[str] = None)",
        "def _find_by_content_kuzu(self, search_term: str, repo_path: Optional[str] = None)",
    ],
    "src/codegraphcontext/cli/main.py": [
        "@app.command(name=\"watch-service-install\")",
        "@app.command(name=\"watch-service-status\")",
        "@app.command(name=\"watch-service-stop\")",
        "@app.command(name=\"watch-service-remove\")",
    ],
    "src/codegraphcontext/cli/cli_helpers.py": [
        "def watch_service_install_helper(",
        "def watch_service_status_helper(unit_name: str):",
        "def watch_service_stop_helper(unit_name: str, disable: bool = False):",
        "def watch_service_remove_helper(unit_name: str, keep_unit_file: bool = False):",
    ],
}


def assert_markers() -> None:
    for rel, needles in CHECKS.items():
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                raise AssertionError(f"missing marker in {rel}: {needle}")


def send(proc: subprocess.Popen, message: dict) -> None:
    payload = json.dumps(message).encode("utf-8")
    proc.stdin.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload)
    proc.stdin.flush()


def recv(proc: subprocess.Popen, timeout: int = 60) -> dict:
    start = time.time()
    header = b""
    while b"\r\n\r\n" not in header:
        if time.time() - start > timeout:
            raise TimeoutError("header timeout")
        ch = proc.stdout.read(1)
        if not ch:
            raise RuntimeError("EOF while reading header")
        header += ch

    h, body = header.split(b"\r\n\r\n", 1)
    content_length = None
    for line in h.decode(errors="replace").split("\r\n"):
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
            break
    if content_length is None:
        raise RuntimeError("missing Content-Length")

    while len(body) < content_length:
        chunk = proc.stdout.read(content_length - len(body))
        if not chunk:
            raise RuntimeError("EOF while reading body")
        body += chunk
    return json.loads(body.decode("utf-8"))


def tool_call(proc: subprocess.Popen, req_id: int, name: str, arguments: dict) -> dict:
    send(proc, {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    response = recv(proc, timeout=120)
    return json.loads(response["result"]["content"][0]["text"])


def runtime_validate() -> None:
    proc = subprocess.Popen(
        ["/workspace/.venv-mcp/bin/cgc", "--database", "kuzudb", "mcp", "start"],
        cwd=TARGET_REPO,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        send(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "validate-script", "version": "1"},
            },
        })
        init = recv(proc, timeout=30)
        if "result" not in init:
            raise AssertionError(f"initialize failed: {init}")

        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

        idx = tool_call(proc, 2, "execute_cypher_query", {"cypher_query": "CALL SHOW_INDEXES() RETURN table_name, index_name, index_type"})
        fts = [r for r in idx.get("results", []) if str(r.get("index_type", "")).upper() == "FTS"]
        if len(fts) < 3:
            raise AssertionError(f"expected >=3 FTS indexes, got {len(fts)}")

        find = tool_call(proc, 3, "find_code", {
            "query": TARGET_SYMBOL,
            "repo_path": TARGET_REPO,
            "fuzzy_search": True,
        })
        ranked = (find.get("results") or {}).get("ranked_results", [])
        if not ranked:
            raise AssertionError("find_code returned no ranked results")
        if not any(r.get("name") == TARGET_SYMBOL for r in ranked):
            raise AssertionError("target symbol missing from ranked results")

        rel = tool_call(proc, 4, "analyze_code_relationships", {
            "query_type": "find_callers",
            "target": TARGET_SYMBOL,
            "context": TARGET_CONTEXT,
            "repo_path": TARGET_REPO,
        })
        callers = ((rel.get("results") or {}).get("results") or [])
        if len(callers) == 0:
            raise AssertionError("no callers returned")

        print("VALIDATION_OK")
        print("FTS_INDEX_COUNT", len(fts))
        print("TARGET_RANKED_COUNT", len(ranked))
        print("CALLERS_COUNT", len(callers))
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=4)
        except Exception:
            proc.kill()


def cli_surface_validate() -> None:
    help_text = subprocess.check_output([
        "/workspace/.venv-mcp/bin/cgc", "help"
    ], text=True, stderr=subprocess.STDOUT)
    for command in [
        "watch-service-install",
        "watch-service-status",
        "watch-service-stop",
        "watch-service-remove",
    ]:
        if command not in help_text:
            raise AssertionError(f"missing CLI command in --help: {command}")


if __name__ == "__main__":
    assert_markers()
    cli_surface_validate()
    runtime_validate()
