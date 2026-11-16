"""Private local discovery for read-only CLI delegation.

No port scanning, database opening, or PID-only trust. A private state record
contains an instance key; requests and responses prove possession of it. The
configured API key is additionally required, as a request-bound HMAC, so a stale
port can never receive the API key itself. This protocol is internal to the CLI.

POSIX ownership/mode checks are intentional. Other platforms keep direct CLI
access until equivalent private-state checks are implemented.
"""

from contextlib import contextmanager
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import stat
import socket
import threading


_VERSION = 1
_RECORD_LIMIT = 4096
_RESPONSE_LIMIT = 4 * 1024 * 1024
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_SHORT_HEX = re.compile(r"[0-9a-f]{32}\Z")
_SUPPORTED = {"ladybugdb", "kuzudb"}
_CONNECT_TIMEOUT = 0.3
_READ_TIMEOUT = 5.0


class GatewayReadError(RuntimeError):
    """A verified live gateway rejected the read; do not silently bypass it."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _signature(key, value):
    return hmac.new(key.encode(), _canonical(value), hashlib.sha256).hexdigest()


def context_identity(ctx, backend, db_path):
    """Include the effective backend/path and resolved context, not its label alone."""
    backend = (backend or "").lower()
    if backend not in _SUPPORTED or not db_path:
        return None
    return hashlib.sha256(_canonical({
        "backend": backend,
        "db_path": str(Path(db_path).expanduser().resolve()),
        "mode": ctx.mode,
        "name": ctx.context_name,
        "root": str(Path(ctx.cgcignore_path).expanduser().resolve().parent),
    })).hexdigest()


def loopback_endpoint(host, port):
    """Discover only known local binds; never resolve an arbitrary hostname."""
    host = {"0.0.0.0": "127.0.0.1", "localhost": "127.0.0.1", "::": "::1"}.get(host, host)
    if host not in {"127.0.0.1", "::1"} or type(port) is not int or not 1 <= port <= 65535:
        return None
    return host, port


def _private_file(info):
    return stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600


@contextmanager
def _state_dir(create=False):
    """Use a directory descriptor so record opens never follow symlinks."""
    from .cli.config_manager import CONFIG_DIR

    if os.name != "posix":
        raise OSError("Private gateway discovery is unavailable on this platform")
    parent = CONFIG_DIR.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o022:
        raise OSError("Unsafe gateway state parent")
    directory = CONFIG_DIR / "gateways"
    if create:
        directory.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise OSError("Unsafe gateway state directory")
        yield fd
    finally:
        os.close(fd)


def _read_record(fd, identity):
    file_fd = os.open(identity + ".json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        info = os.fstat(file_fd)
        if not _private_file(info) or info.st_size > _RECORD_LIMIT:
            raise ValueError("Unsafe or oversized gateway record")
        raw = os.read(file_fd, _RECORD_LIMIT + 1)
        if len(raw) > _RECORD_LIMIT:
            raise ValueError("Oversized gateway record")
        record = json.loads(raw)
    finally:
        os.close(file_fd)
    if not isinstance(record, dict) or set(record) != {
        "version", "identity", "instance", "generation", "pid", "host", "port", "secret"
    }:
        raise ValueError("Invalid gateway record")
    if (type(record["version"]) is not int or record["version"] != _VERSION
            or record["identity"] != identity
            or not isinstance(record["instance"], str) or not _SHORT_HEX.fullmatch(record["instance"])
            or not isinstance(record["secret"], str) or not _HEX.fullmatch(record["secret"])
            or type(record["pid"]) is not int or record["pid"] <= 0
            or type(record["generation"]) is not int or record["generation"] < 1
            or not isinstance(record["host"], str)
            or record["host"] not in {"127.0.0.1", "::1"}
            or loopback_endpoint(record["host"], record["port"]) is None):
        raise ValueError("Invalid gateway identity or endpoint")
    return record


@contextmanager
def _record_lock(fd, identity):
    import fcntl

    lock_fd = os.open(identity + ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
    try:
        if not _private_file(os.fstat(lock_fd)):
            raise OSError("Unsafe gateway record lock")
        # A crashed process releases flock. Never block CLI startup on it.
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(lock_fd)


def _store_record(record):
    with _state_dir(create=True) as fd, _record_lock(fd, record["identity"]):
        name = ".tmp-" + secrets.token_hex(16)
        file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        try:
            with os.fdopen(file_fd, "wb") as stream:
                stream.write(_canonical(record))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, record["identity"] + ".json", src_dir_fd=fd, dst_dir_fd=fd)
        finally:
            try:
                os.unlink(name, dir_fd=fd)
            except FileNotFoundError:
                pass


def _remove_record(record):
    try:
        with _state_dir() as fd, _record_lock(fd, record["identity"]):
            current = _read_record(fd, record["identity"])
            if (current["instance"], current["generation"]) == (record["instance"], record["generation"]):
                os.unlink(record["identity"] + ".json", dir_fd=fd)
    except (OSError, ValueError, RecursionError):
        pass


def _valid_request(request):
    if not isinstance(request, dict) or set(request) != {
        "version", "instance", "identity", "generation", "nonce", "operation", "path", "proof", "auth"
    }:
        return False
    return (
        type(request["version"]) is int and request["version"] == _VERSION
        and isinstance(request["instance"], str) and bool(_SHORT_HEX.fullmatch(request["instance"]))
        and isinstance(request["identity"], str) and bool(_HEX.fullmatch(request["identity"]))
        and isinstance(request["nonce"], str) and bool(_SHORT_HEX.fullmatch(request["nonce"]))
        and type(request["generation"]) is int and request["generation"] > 0
        and isinstance(request["operation"], str) and request["operation"] in {"list", "stats"}
        and (request["path"] is None or isinstance(request["path"], str) and len(request["path"]) <= 32768)
        and (request["operation"] != "list" or request["path"] is None)
        and isinstance(request["proof"], str) and bool(_HEX.fullmatch(request["proof"]))
        and isinstance(request["auth"], str) and bool(_HEX.fullmatch(request["auth"]))
    )


class GatewayOwner:
    """Identity of the authoritative server; all methods use its context lock."""

    def __init__(self, endpoint):
        self.host, self.port = endpoint
        self.instance = secrets.token_hex(16)
        self.secret = secrets.token_hex(32)
        self.generation = 0
        self.record = None

    def publish(self, server):
        self.invalidate()
        identity = context_identity(
            server.resolved_context, server.db_manager.get_backend_type(),
            getattr(server.db_manager, "db_path", None),
        )
        if identity is None:
            return
        record = {
            "version": _VERSION, "identity": identity, "instance": self.instance,
            "generation": self.generation, "pid": os.getpid(),
            "host": self.host, "port": self.port, "secret": self.secret,
        }
        try:
            _store_record(record)
        except (OSError, ValueError):
            return  # Discovery is optional; never break normal gateway startup.
        self.record = record

    def invalidate(self):
        old_record, self.record = self.record, None
        self.generation += 1
        if old_record is not None:
            _remove_record(old_record)

    def read(self, server, request):
        """Authenticate and collect under one lease, including during switches."""
        from .api.auth import get_configured_api_key
        from .core.repository_stats import repository_stats

        if not _valid_request(request) or request["instance"] != self.instance:
            return None
        payload = {key: value for key, value in request.items() if key not in {"proof", "auth"}}
        if not hmac.compare_digest(request["proof"], _signature(self.secret, payload)):
            return None
        with server._context_lock:
            response = {
                "version": _VERSION, "instance": self.instance,
                "generation": self.generation,
                "identity": self.record["identity"] if self.record else None,
                "nonce": request["nonce"], "status": "ok", "data": None,
            }
            status_code = 200
            if (self.record is None or request["identity"] != self.record["identity"]
                    or request["generation"] != self.generation):
                response["status"], status_code = "context_changed", 409
            else:
                api_key = get_configured_api_key()
                expected_auth = _signature(api_key or "", {**payload, "proof": request["proof"]})
                if api_key and not hmac.compare_digest(request["auth"], expected_auth):
                    response["status"], status_code = "auth_failed", 401
                else:
                    try:
                        if request["operation"] == "list":
                            response["data"] = {"repositories": server.code_finder.list_indexed_repositories()}
                        else:
                            response["data"] = repository_stats(server.db_manager, request["path"])
                    except Exception:
                        # Do not expose driver messages, paths or credentials.
                        response["status"], status_code = "read_error", 503
            response["proof"] = _signature(self.secret, response)
            return response, status_code


def try_gateway_read(ctx, operation, path=None):
    """Return verified data, or None when no usable matching owner is found."""
    from .api.auth import get_configured_api_key

    identity = context_identity(
        ctx, os.getenv("CGC_RUNTIME_DB_TYPE") or os.getenv("DEFAULT_DATABASE") or ctx.database,
        os.getenv("CGC_RUNTIME_DB_PATH") or ctx.db_path,
    )
    if identity is None:
        return None
    try:
        with _state_dir() as fd:
            record = _read_record(fd, identity)
        # Cheap stale-PID check only. The signed response establishes ownership.
        os.kill(record["pid"], 0)
    except (OSError, ValueError, TypeError, RecursionError):
        return None
    payload = {
        "version": _VERSION, "instance": record["instance"], "identity": identity,
        "generation": record["generation"], "nonce": secrets.token_hex(16),
        "operation": operation, "path": path,
    }
    payload["proof"] = _signature(record["secret"], payload)
    payload["auth"] = _signature(get_configured_api_key() or "", payload)
    # HTTPConnection does not use proxies/netrc or follow redirects. A socket
    # watchdog bounds the entire exchange, including slow-drip headers/body;
    # an ordinary read timeout only bounds inactivity between received bytes.
    connection = http.client.HTTPConnection(record["host"], record["port"], timeout=_CONNECT_TIMEOUT)
    deadline = None
    result = None
    try:
        connection.connect()
        sock = connection.sock
        sock.settimeout(_READ_TIMEOUT)

        def abort_read():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        deadline = threading.Timer(_READ_TIMEOUT, abort_read)
        deadline.daemon = True
        deadline.start()
        connection.request("POST", "/api/v1/cli/read", body=_canonical(payload), headers={"Content-Type": "application/json"})
        result = connection.getresponse()
        if result.status not in {200, 401, 409, 503}:
            return None
        raw = result.read(_RESPONSE_LIMIT + 1)
        if len(raw) > _RESPONSE_LIMIT:
            return None
        response = json.loads(raw)
    except (OSError, http.client.HTTPException, ValueError, RecursionError):
        return None
    finally:
        if deadline is not None:
            deadline.cancel()
        if result is not None:
            result.close()
        connection.close()
    if not isinstance(response, dict):
        return None
    proof = response.pop("proof", None)
    if (not isinstance(proof, str) or not _HEX.fullmatch(proof)
            or not hmac.compare_digest(proof, _signature(record["secret"], response))
            or response.get("version") != _VERSION
            or response.get("instance") != record["instance"]
            or response.get("nonce") != payload["nonce"]):
        return None
    status = response.get("status")
    if status == "auth_failed":
        raise GatewayReadError("The local gateway rejected authentication. Check CGC_API_KEY for this CLI and gateway.")
    if (status == "context_changed" or response.get("identity") != identity
            or response.get("generation") != record["generation"]):
        raise GatewayReadError("The local gateway changed context during this read. Retry the command for the intended context.")
    if status != "ok" or not isinstance(response.get("data"), dict):
        raise GatewayReadError("The local gateway could not complete this read. Check the gateway and retry.")
    return response["data"]
