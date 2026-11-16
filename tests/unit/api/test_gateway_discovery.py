"""Trust, context ownership, and CLI fallback regressions for local reads."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from time import monotonic
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from codegraphcontext import gateway_discovery as discovery
from codegraphcontext.api import auth
from codegraphcontext.cli import cli_helpers, config_manager
from codegraphcontext.server import MCPServer


pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX private-state protocol")


@pytest.fixture
def owner(tmp_path, monkeypatch):
    root = tmp_path / "config"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(config_manager, "CONFIG_DIR", root)
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "ladybugdb")
    monkeypatch.delenv("CGC_RUNTIME_DB_PATH", raising=False)
    monkeypatch.setattr(auth, "get_configured_api_key", lambda: "fixture-api-key")
    ctx = config_manager.ResolvedContext(
        "global", "", "ladybugdb", str(tmp_path / "graph"), str(root / "global" / ".cgcignore")
    )
    manager = MagicMock()
    manager.get_backend_type.return_value = "ladybugdb"
    manager.db_path = ctx.db_path
    server = MCPServer.__new__(MCPServer)
    server._context_lock = threading.RLock()
    server.resolved_context = ctx
    server.db_manager = manager
    server.code_finder = MagicMock()
    server.code_finder.list_indexed_repositories.return_value = [
        {"name": "fixture", "path": "/fixture", "is_dependency": False}
    ]
    owner = discovery.GatewayOwner(("127.0.0.1", 12345))
    server._gateway_owner = owner
    owner.publish(server)
    assert owner.record is not None
    owner.server = server
    owner.path = root / "gateways" / (owner.record["identity"] + ".json")
    return owner


def request_for(owner, *, api_key="fixture-api-key", operation="list", path=None):
    request = {
        "version": 1, "instance": owner.instance, "identity": owner.record["identity"],
        "generation": owner.generation, "nonce": "a" * 32, "operation": operation, "path": path,
    }
    request["proof"] = discovery._signature(owner.secret, request)
    request["auth"] = discovery._signature(api_key, request)
    return request


def install_transport(monkeypatch, owner, transform=lambda value: value):
    connections = []

    class Reply:
        def __init__(self, data, status):
            self.data = json.dumps(data).encode()
            self.status = status

        def read(self, size):
            return self.data[:size]

        def close(self):
            pass

    class Connection:
        def __init__(self, host, port, timeout):
            self.host, self.port, self.timeout = host, port, timeout
            self.sock = MagicMock()
            connections.append(self)

        def connect(self):
            pass

        def close(self):
            pass

        def request(self, method, path, **kwargs):
            self.method, self.path, self.kwargs = method, path, kwargs

        def getresponse(self):
            response = owner.read(owner.server, json.loads(self.kwargs["body"]))
            assert response is not None
            return Reply(transform(response[0]), response[1])

    monkeypatch.setattr(discovery.http.client, "HTTPConnection", Connection)
    return connections


def test_owner_only_atomic_state_and_verified_read_never_send_api_key(owner, monkeypatch):
    connections = install_transport(monkeypatch, owner)
    assert owner.path.stat().st_mode & 0o777 == 0o600
    assert owner.path.parent.stat().st_mode & 0o777 == 0o700
    assert "fixture-api-key" not in owner.path.read_text()
    data = discovery.try_gateway_read(owner.server.resolved_context, "list")
    assert data["repositories"][0]["name"] == "fixture"
    connection = connections[0]
    assert (connection.host, connection.port) == ("127.0.0.1", 12345)
    assert (connection.method, connection.path) == ("POST", "/api/v1/cli/read")
    assert connection.timeout == 0.3
    connection.sock.settimeout.assert_called_once_with(5)
    assert "fixture-api-key" not in connection.kwargs["body"].decode()
    assert connection.kwargs["headers"] == {"Content-Type": "application/json"}
    owner.server.db_manager.get_driver.assert_not_called()
    assert not list(owner.path.parent.glob(".tmp-*"))


@pytest.mark.parametrize("kind", ["broad_mode", "symlink", "fifo", "directory", "oversized", "malformed", "nested_json", "remote", "unknown_version", "dead_pid"])
def test_untrusted_or_stale_records_fall_back_without_network(owner, monkeypatch, kind):
    record = json.loads(owner.path.read_text())
    if kind == "broad_mode":
        owner.path.chmod(0o644)
    elif kind in {"symlink", "fifo", "directory"}:
        owner.path.unlink()
        if kind == "symlink":
            target = owner.path.parent / "target"
            target.write_text(json.dumps(record))
            target.chmod(0o600)
            owner.path.symlink_to(target)
        elif kind == "fifo":
            os.mkfifo(owner.path, 0o600)
        else:
            owner.path.mkdir()
    elif kind == "oversized":
        owner.path.write_text(" " * 4097)
    elif kind == "malformed":
        owner.path.write_text("not json")
    elif kind == "nested_json":
        owner.path.write_text("[" * 1500 + "]" * 1500)
    elif kind == "dead_pid":
        monkeypatch.setattr(os, "kill", lambda *args: (_ for _ in ()).throw(ProcessLookupError()))
    else:
        record["host" if kind == "remote" else "version"] = "example.com" if kind == "remote" else 2
        owner.path.write_text(json.dumps(record))
    network = MagicMock(side_effect=AssertionError("Unsafe record reached network"))
    monkeypatch.setattr(discovery.http.client, "HTTPConnection", network)
    assert discovery.try_gateway_read(owner.server.resolved_context, "list") is None
    network.assert_not_called()


def test_missing_state_and_unsafe_parent_fall_back(owner, monkeypatch):
    owner.path.unlink()
    assert discovery.try_gateway_read(owner.server.resolved_context, "list") is None
    owner.publish(owner.server)
    config_manager.CONFIG_DIR.chmod(0o777)
    assert discovery.try_gateway_read(owner.server.resolved_context, "list") is None
    owner.publish(owner.server)
    assert owner.record is None


def test_foreign_owned_state_is_not_trusted(owner, monkeypatch):
    real_fstat = os.fstat

    def foreign(fd):
        fields = list(real_fstat(fd))
        fields[4] = os.getuid() + 1
        return os.stat_result(fields)

    monkeypatch.setattr(os, "fstat", foreign)
    network = MagicMock(side_effect=AssertionError("Foreign state reached network"))
    monkeypatch.setattr(discovery.http.client, "HTTPConnection", network)
    assert discovery.try_gateway_read(owner.server.resolved_context, "list") is None


@pytest.mark.parametrize("kind", ["proof", "nonce", "instance", "unsigned_auth_failure"])
def test_reused_live_pid_port_or_tampered_reply_is_not_trusted(owner, monkeypatch, kind):
    def tamper(response):
        if kind == "unsigned_auth_failure":
            return {"status": "auth_failed"}
        response[kind] = "0" * (64 if kind == "proof" else 32)
        return response

    install_transport(monkeypatch, owner, tamper)
    assert discovery.try_gateway_read(owner.server.resolved_context, "list") is None


def test_unreachable_matching_owner_falls_back(owner, monkeypatch):
    connection = MagicMock()
    connection.connect.side_effect = TimeoutError()
    monkeypatch.setattr(discovery.http.client, "HTTPConnection", lambda *args, **kwargs: connection)
    assert discovery.try_gateway_read(owner.server.resolved_context, "list") is None


@pytest.mark.parametrize("phase", ["headers", "body"])
def test_unverified_drip_response_has_an_absolute_deadline(owner, monkeypatch, phase):
    stop, finished = threading.Event(), threading.Event()
    requests_seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            requests_seen.append(self.rfile.read(int(self.headers["Content-Length"])))
            header = b"HTTP/1.1 200 OK\r\nContent-Length: 200\r\n\r\n"
            try:
                if phase == "body":
                    self.wfile.write(header)
                    data = b" " * 200
                else:
                    data = header
                # Each byte arrives inside an inactivity timeout. The whole
                # exchange would take several seconds without the watchdog.
                for byte in data:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    if stop.wait(0.02):
                        break
            except OSError:
                pass  # Expected when the client shuts down its owned socket.
            finally:
                finished.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    owner.record["port"] = server.server_port
    discovery._store_record(owner.record)
    monkeypatch.setattr(discovery, "_READ_TIMEOUT", 0.15)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02))
    worker.start()
    try:
        started = monotonic()
        assert discovery.try_gateway_read(owner.server.resolved_context, "list") is None
        assert monotonic() - started < 1.0
        assert requests_seen and b"fixture-api-key" not in requests_seen[0]
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        worker.join(2)
    assert finished.is_set() and not worker.is_alive()


def test_live_auth_failure_is_signed_and_does_not_read_database(owner, monkeypatch):
    response, status = owner.read(owner.server, request_for(owner, api_key="wrong"))
    assert status == 401 and response["status"] == "auth_failed"
    owner.server.code_finder.list_indexed_repositories.assert_not_called()
    owner.server.db_manager.get_driver.assert_not_called()
    install_transport(monkeypatch, owner, lambda _: response)
    monkeypatch.setattr(discovery.secrets, "token_hex", lambda _: "a" * 32)
    with pytest.raises(discovery.GatewayReadError, match="authentication"):
        discovery.try_gateway_read(owner.server.resolved_context, "list")


@pytest.mark.parametrize("change", ["backend", "path", "context", "runtime_path"])
def test_different_effective_context_never_uses_record(owner, monkeypatch, change):
    ctx = owner.server.resolved_context
    if change == "backend":
        monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "kuzudb")
    elif change == "path":
        ctx.db_path += "-other"
    elif change == "context":
        ctx.mode, ctx.context_name = "named", "other"
    else:
        monkeypatch.setenv("CGC_RUNTIME_DB_PATH", ctx.db_path + "-override")
    network = MagicMock(side_effect=AssertionError("Wrong context used network"))
    monkeypatch.setattr(discovery.http.client, "HTTPConnection", network)
    assert discovery.try_gateway_read(ctx, "list") is None


def test_old_owner_cleanup_cannot_remove_successor(owner):
    old = owner.record.copy()
    replacement = discovery.GatewayOwner(("127.0.0.1", 23456))
    replacement.publish(owner.server)
    discovery._remove_record(old)
    assert json.loads(owner.path.read_text())["instance"] == replacement.instance
    replacement.invalidate()
    assert not owner.path.exists()


def test_generation_checked_again_under_read_lease(owner):
    request = request_for(owner)
    owner.invalidate()
    owner.publish(owner.server)
    response, status = owner.read(owner.server, request)
    assert status == 409 and response["status"] == "context_changed"
    owner.server.code_finder.list_indexed_repositories.assert_not_called()


def test_read_lease_prevents_switch_teardown_until_collection_finishes(owner):
    entered, release, switched = threading.Event(), threading.Event(), threading.Event()

    def collect():
        entered.set()
        assert release.wait(2)
        assert not switched.is_set()
        return []

    owner.server.code_finder.list_indexed_repositories.side_effect = collect
    owner.server._switch_context_locked = lambda **args: switched.set()
    result = []
    reader = threading.Thread(target=lambda: result.append(owner.read(owner.server, request_for(owner))))
    switcher = threading.Thread(target=lambda: owner.server.switch_context_tool(context_path="global"))
    reader.start()
    try:
        assert entered.wait(2)
        switcher.start()
        assert not switched.wait(0.05)
    finally:
        release.set()
        reader.join(2)
        if switcher.ident is not None:
            switcher.join(2)
    assert not reader.is_alive() and not switcher.is_alive()
    assert switched.is_set() and result[0][1] == 200


def test_failed_switch_invalidates_record_before_teardown(owner, monkeypatch):
    import codegraphcontext.server as server_module

    owner.server.job_manager = SimpleNamespace(list_active_jobs=lambda: [])
    owner.server._stop_current_watcher = lambda: False
    old_request = request_for(owner)

    def teardown(manager):
        assert owner.record is None
        assert not owner.path.exists()

    monkeypatch.setattr(server_module, "_teardown_db_manager", teardown)
    monkeypatch.setattr(server_module, "get_database_manager", MagicMock(side_effect=RuntimeError("fixture failure")))
    result = owner.server.switch_context_tool(context_path="global")
    assert "error" in result and owner.record is None
    response, status = owner.read(owner.server, old_request)
    assert status == 409 and response["status"] == "context_changed"


def test_successful_switch_publishes_new_identity_and_generation(owner, monkeypatch, tmp_path):
    import codegraphcontext.server as server_module

    old_request = request_for(owner)
    owner.server.job_manager = SimpleNamespace(list_active_jobs=lambda: [])
    owner.server._stop_current_watcher = lambda: False
    owner.server._start_watcher_if = lambda _: None
    owner.server.loop = None
    manager = MagicMock()
    manager.get_backend_type.return_value = "ladybugdb"
    manager.db_path = str(tmp_path / "other-graph")
    monkeypatch.setattr(server_module, "_default_global_db_path", lambda _: manager.db_path)
    monkeypatch.setattr(server_module, "_teardown_db_manager", lambda _: None)
    monkeypatch.setattr(server_module, "get_database_manager", lambda **_: manager)
    for name in ("GraphBuilder", "CodeFinder", "CodeWatcher"):
        monkeypatch.setattr(server_module, name, MagicMock())
    result = owner.server.switch_context_tool(context_path="global")
    assert result["status"] == "ok"
    assert not owner.path.exists()
    assert owner.record["identity"] != old_request["identity"]
    assert owner.generation > old_request["generation"]
    assert owner.read(owner.server, old_request)[1] == 409
    manager.get_driver.assert_called_once()


def test_health_does_not_publish_and_lifespan_cleans_initialized_owner(owner, monkeypatch):
    from fastapi.testclient import TestClient
    from codegraphcontext.api import router
    from codegraphcontext.api.app import create_app

    owner.invalidate()
    owner.server._gateway_owner = None
    constructor = MagicMock(return_value=owner.server)
    monkeypatch.setattr(router, "MCPServer", constructor)
    monkeypatch.setattr(router, "_server_instance", None)
    monkeypatch.setattr(router, "_gateway_owner", None)
    app = create_app(gateway_endpoint=("127.0.0.1", 12345))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        constructor.assert_not_called()
        assert not owner.path.exists()
        headers = {"X-API-Key": "fixture-api-key"}
        assert client.get("/api/v1/status", headers=headers).status_code == 200
        constructor.assert_called_once()
        current = router._gateway_owner
        assert owner.server._gateway_owner is current
        assert owner.path.exists()
        assert client.post("/api/v1/cli/read", json={}).status_code == 404
        request = request_for(current)
        assert client.post("/api/v1/cli/read", json=request).status_code == 200
        assert client.post("/api/v1/cli/read", json=request_for(current, api_key="wrong")).status_code == 401
        assert client.post("/api/v1/cli/read", content=b" " * 65537).status_code == 413
    assert not owner.path.exists()
    assert router._gateway_owner is None
    assert owner.server._gateway_owner is None
    # Discovery cleanup does not take over the separate indexing-job lifecycle.
    owner.server.db_manager.close_driver.assert_not_called()


def test_failed_server_initialization_does_not_publish(owner, monkeypatch):
    from fastapi.testclient import TestClient
    from codegraphcontext.api import router
    from codegraphcontext.api.app import create_app

    owner.invalidate()
    monkeypatch.setattr(router, "_server_instance", None)
    monkeypatch.setattr(router, "_gateway_owner", None)
    monkeypatch.setattr(router, "MCPServer", MagicMock(side_effect=ValueError("fixture failure")))
    with TestClient(create_app(gateway_endpoint=("127.0.0.1", 12345))) as client:
        with pytest.raises(ValueError, match="fixture failure"):
            client.get("/api/v1/status", headers={"X-API-Key": "fixture-api-key"})
        assert not owner.path.exists()


def test_only_supported_read_operations_are_accepted(owner):
    request = request_for(owner, operation="delete")
    assert owner.read(owner.server, request) is None
    owner.server.db_manager.get_driver.assert_not_called()


@pytest.mark.parametrize("helper", ["list", "stats", "scoped"])
def test_cli_delegates_before_any_local_database_initialization(owner, monkeypatch, capsys, helper):
    monkeypatch.setattr(cli_helpers, "ensure_first_run_bootstrap", lambda: None)
    monkeypatch.setattr(cli_helpers, "resolve_context", lambda _: owner.server.resolved_context)
    initialize = MagicMock(side_effect=AssertionError("Local DB must not open"))
    monkeypatch.setattr(cli_helpers, "_initialize_services", initialize)
    if helper == "list":
        data = {"repositories": []}
    else:
        data = {"found": True, "counts": {}}
    delegation = MagicMock(return_value=data)
    monkeypatch.setattr(cli_helpers, "try_gateway_read", delegation)
    if helper == "list":
        cli_helpers.list_repos_helper()
    else:
        cli_helpers.stats_helper("./relative-repo" if helper == "scoped" else None)
    initialize.assert_not_called()
    assert "Reading through local CGC Gateway" in capsys.readouterr().out
    if helper == "scoped":
        assert delegation.call_args.args[2] == Path("./relative-repo").resolve().as_posix()


@pytest.mark.parametrize("host,port,expected", [
    ("0.0.0.0", 9091, ("127.0.0.1", 9091)),
    ("::", 9091, ("::1", 9091)),
    ("localhost", 9091, ("127.0.0.1", 9091)),
    ("example.com", 9091, None), ("192.0.2.1", 9091, None),
    ("127.0.0.1", 0, None), ("127.0.0.1", True, None),
])
def test_bind_address_rules(host, port, expected):
    assert discovery.loopback_endpoint(host, port) == expected
