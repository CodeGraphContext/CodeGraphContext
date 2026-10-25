from unittest.mock import MagicMock, patch

import pytest

from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager


@pytest.mark.parametrize("failure_at", ["select", "query"])
def test_failed_first_connection_can_be_retried(monkeypatch, failure_at):
    monkeypatch.setattr(FalkorDBRemoteManager, "_instance", None)
    monkeypatch.setattr(FalkorDBRemoteManager, "_driver", None)
    monkeypatch.setattr(FalkorDBRemoteManager, "_graphs", {})
    manager = FalkorDBRemoteManager()
    failed, healthy = MagicMock(), MagicMock()
    if failure_at == "select":
        failed.select_graph.side_effect = ConnectionError("unavailable")
    else:
        failed.select_graph.return_value.query.side_effect = ConnectionError("unavailable")

    try:
        with patch("falkordb.FalkorDB", side_effect=[failed, healthy]) as client:
            with pytest.raises(ConnectionError, match="unavailable"):
                manager.get_driver()
            assert manager._driver is None
            assert manager._graphs == {}

            manager.get_driver("other")
            assert client.call_count == 2
            assert manager._driver is healthy
            healthy.select_graph.return_value.query.assert_called_once_with("RETURN 1")
            assert set(manager._graphs) == {manager.graph_name, "other"}

            manager.get_driver("other")
            assert client.call_count == 2
    finally:
        manager.close_driver()
