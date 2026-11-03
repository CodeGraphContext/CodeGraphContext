"""Real CLI processes sharing a gateway-owned on-disk Ladybug database."""

import os
import re
import socket
import subprocess
import sys
import time

import pytest
import requests


# Patch only config-home discovery, before CGC imports, to isolate every child
# from the developer's configuration. Database, HTTP and CLI remain real.
_BOOTSTRAP = """
import os, pathlib, sys
from unittest.mock import patch
with patch.object(pathlib.Path, 'home', return_value=pathlib.Path(os.environ['CGC_TEST_CONFIG_HOME'])):
    if sys.argv[1] == 'seed':
        from codegraphcontext.core import get_database_manager
        manager = get_database_manager(db_path=os.environ['CGC_RUNTIME_DB_PATH'])
        with manager.get_driver().session() as session:
            session.run('CREATE (:Repository {path: $path, name: $name, is_dependency: false})',
                        path=os.environ['CGC_TEST_REPO'], name='gateway-fixture')
            session.run('CREATE (:File {path: $path})', path=os.environ['CGC_TEST_REPO'] + '/fixture.py')
            session.run('MATCH (r:Repository), (f:File) CREATE (r)-[:CONTAINS]->(f)')
            for label in ('Function', 'Class', 'Interface', 'Trait', 'Struct', 'Enum'):
                session.run('CREATE (n:' + label + ' {uid: $uid, name: $name})', uid=label, name=label)
                session.run('MATCH (f:File), (n:' + label + ') CREATE (f)-[:CONTAINS]->(n)')
            # A method reachable through two containment paths must count once.
            session.run('MATCH (c:Class), (f:Function) CREATE (c)-[:CONTAINS]->(f)')
            session.run('CREATE (:Module {name: $name})', name='fixture-module')
            session.run('MATCH (f:File), (m:Module) CREATE (f)-[:IMPORTS]->(m)')
        manager.close_driver()
    else:
        from codegraphcontext.cli.main import app
        sys.argv = ['cgc'] + sys.argv[1:]
        app()
"""


def _plain(output):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output)


@pytest.mark.skipif(os.name != "posix", reason="Gateway discovery uses POSIX owner-only state files")
@pytest.mark.parametrize("with_data", [True, False])
def test_cli_reads_while_real_gateway_owns_ladybug(tmp_path, with_data):
    pytest.importorskip("ladybug")
    config_home = tmp_path / "config-home"
    config_home.mkdir()
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    env = {
        **os.environ,
        "CGC_TEST_CONFIG_HOME": str(config_home),
        "CGC_TEST_REPO": repo.as_posix(),
        "CGC_RUNTIME_DB_PATH": str(tmp_path / "graph"),
        "CGC_RUNTIME_DB_TYPE": "ladybugdb",
        "CGC_EMBEDDED_BUFFER_POOL_MB": "2048",
        "CGC_API_KEY": "disposable-gateway-test-key",
        "NO_COLOR": "1",
        "COLUMNS": "200",
    }

    def cli(*args, **overrides):
        return subprocess.run(
            [sys.executable, "-c", _BOOTSTRAP, *args],
            cwd=repo, env={**env, **overrides}, capture_output=True, text=True,
            timeout=35,
        )

    if with_data:
        seeded = cli("seed")
        assert seeded.returncode == 0, seeded.stdout + seeded.stderr
    commands = [("list",), ("stats",), ("stats", str(repo)), ("stats", str(repo / "missing"))]
    direct = {}
    for command in commands:
        result = cli(*command)
        assert result.returncode == 0, result.stdout + result.stderr
        direct[command] = _plain(result.stdout)
    if with_data:
        assert "gateway-fixture" in direct[("list",)]
        for metric in ("Repositories", "Functions", "Interfaces", "Traits", "Structs", "Enums", "Modules"):
            assert re.search(rf"{metric}\s+│\s+1", direct[("stats",)])
        assert re.search(r"Functions\s+│\s+1", direct[("stats", str(repo))])
    else:
        assert "No repositories indexed yet" in direct[("list",)]
        assert "No data indexed yet" in direct[("stats",)]

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    session = requests.Session()
    session.trust_env = False
    session.headers["X-API-Key"] = env["CGC_API_KEY"]
    with (tmp_path / "gateway.log").open("w+") as log:
        gateway = subprocess.Popen(
            [sys.executable, "-c", _BOOTSTRAP, "api", "start", "--host", "127.0.0.1", "--port", str(port)],
            cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 35
            while True:
                try:
                    response = session.get(base + "/api/v1/status", timeout=2)
                    if response.status_code == 200:
                        break
                except requests.RequestException:
                    pass
                if gateway.poll() is not None or time.monotonic() >= deadline:
                    log.seek(0)
                    pytest.fail("Gateway did not initialize: " + log.read())
                time.sleep(0.05)
            for command in commands:
                result = cli(*command)
                assert result.returncode == 0, result.stdout + result.stderr
                # Ignore setup progress lines; the rendered command result is
                # identical to the direct path, including empty/missing cases.
                output = _plain(result.stdout)
                rendered = direct[command].split("Services initialized.\n", 1)[-1]
                assert rendered in output, output
                assert "Reading through local CGC Gateway" in output
                assert "already has this embedded database open" not in output
            rejected = cli("list", CGC_API_KEY="incorrect-test-key")
            assert rejected.returncode == 1
            assert "rejected authentication" in rejected.stdout
            assert "Initializing services" not in rejected.stdout
            # Writes keep the existing single-owner diagnostic and do not
            # silently route through the new internal read-only endpoint.
            update = cli("update", str(repo))
            assert update.returncode == 1
            assert "already has this embedded database open" in update.stdout
            assert session.get(base + "/api/v1/status", timeout=2).status_code == 200
            # A crashed owner leaves stale metadata. The next CLI process must
            # recover direct ownership instead of trusting a reused PID/port.
            gateway.kill()
            gateway.wait(timeout=10)
            recovered = cli("list")
            assert recovered.returncode == 0, recovered.stdout + recovered.stderr
            expected = "gateway-fixture" if with_data else "No repositories indexed yet"
            assert expected in recovered.stdout
        finally:
            if gateway.poll() is None:
                gateway.terminate()
                try:
                    gateway.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    gateway.kill()
                    gateway.wait(timeout=10)
            session.close()
