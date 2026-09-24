from unittest.mock import MagicMock

import pytest

from codegraphcontext.core import falkor_worker
from codegraphcontext.core.database_falkordb import FalkorDBManager


def test_worker_signal_saves_embedded_database_before_exiting(monkeypatch):
    database = MagicMock()
    monkeypatch.setattr(falkor_worker, "db_instance", database)

    with pytest.raises(SystemExit) as exc_info:
        falkor_worker.handle_signal(15, None)

    assert exc_info.value.code == 0
    database.shutdown.assert_called_once_with(save=True)


def test_manager_shutdown_saves_server_before_terminating_worker(monkeypatch):
    import redis

    manager = object.__new__(FalkorDBManager)
    manager.socket_path = "/tmp/falkordb.sock"
    manager._process = MagicMock()
    manager._process.poll.return_value = None
    redis_client = MagicMock()
    redis_client.shutdown.side_effect = redis.ConnectionError("server closed connection")
    monkeypatch.setattr(redis, "Redis", MagicMock(return_value=redis_client))

    manager.shutdown()

    redis.Redis.assert_called_once_with(unix_socket_path="/tmp/falkordb.sock")
    redis_client.shutdown.assert_called_once_with(save=True)
    manager._process.terminate.assert_called_once()
