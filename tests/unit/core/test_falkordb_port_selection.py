from codegraphcontext.core.falkor_worker import get_falkordb_port
from codegraphcontext.core.database_falkordb import FalkorDBManager
from codegraphcontext.cli.config_manager import DEFAULT_CONFIG


def test_falkordb_port_is_stable_and_distinct_for_each_socket(monkeypatch):
    monkeypatch.delenv("FALKORDB_PORT", raising=False)

    first = get_falkordb_port("/tmp/one/falkordb.sock")
    second = get_falkordb_port("/tmp/two/falkordb.sock")

    assert 20_000 <= first < 40_000
    assert first == get_falkordb_port("/tmp/one/falkordb.sock")
    assert first != second


def test_falkordb_port_honors_explicit_override(monkeypatch):
    monkeypatch.setenv("FALKORDB_PORT", "16379")

    assert get_falkordb_port("/tmp/one/falkordb.sock") == 16_379


def test_manager_forwards_its_socket_specific_port_to_worker(monkeypatch):
    monkeypatch.delenv("FALKORDB_PORT", raising=False)
    manager = object.__new__(FalkorDBManager)
    manager.db_path = "/tmp/one/falkordb"
    manager.socket_path = "/tmp/one/falkordb.sock"

    worker_env = manager._build_worker_environment()

    assert worker_env["FALKORDB_PATH"] == manager.db_path
    assert worker_env["FALKORDB_SOCKET_PATH"] == manager.socket_path
    assert worker_env["FALKORDB_PORT"] == str(get_falkordb_port(manager.socket_path))


def test_falkordb_port_is_an_exposed_optional_configuration():
    assert DEFAULT_CONFIG["FALKORDB_PORT"] == ""
