"""#1094: SSL parameters reach the drivers with verification-on defaults."""
import ssl as ssl_mod
import sys
from unittest.mock import MagicMock, patch

import pytest


def test_mysql_connect_builds_verified_ssl_kwargs():
    from codegraphcontext.tools.datasources.mysql_ingester import _connect
    fake_pymysql = MagicMock()
    fake_pymysql.cursors.DictCursor = object
    with patch.dict(sys.modules, {"pymysql": fake_pymysql}):
        _connect("h", 3306, "u", "p", "db", ssl_verify=True, ssl_ca_certs="/ca.pem")
    kwargs = fake_pymysql.connect.call_args.kwargs
    assert kwargs["ssl"]["ca"] == "/ca.pem"
    assert kwargs["ssl"]["check_hostname"] is True
    assert kwargs["ssl"]["verify_mode"] == "REQUIRED"


def test_mysql_connect_omits_ssl_by_default():
    from codegraphcontext.tools.datasources.mysql_ingester import _connect
    fake_pymysql = MagicMock()
    fake_pymysql.cursors.DictCursor = object
    with patch.dict(sys.modules, {"pymysql": fake_pymysql}):
        _connect("h", 3306, "u", "p", "db")
    assert "ssl" not in fake_pymysql.connect.call_args.kwargs


def test_cassandra_ssl_context_requires_verification(tmp_path):
    pytest.importorskip("cassandra")
    from codegraphcontext.tools.datasources import cassandra_ingester
    captured = {}

    class _FakeCluster:
        def __init__(self, *a, **k):
            captured.update(k)
            raise RuntimeError("stop before connecting")

    ca = tmp_path / "ca.pem"
    # a syntactically valid (if useless) PEM so create_default_context accepts it
    ca.write_text("")
    with patch.object(cassandra_ingester, "Cluster", _FakeCluster, create=True):
        with pytest.raises(Exception):
            cassandra_ingester.ingest(hosts=["h"], port=9042, keyspace="k",
                                      ssl_verify=True, ssl_ca_certs=None)
    ctx = captured.get("ssl_context")
    assert ctx is not None
    assert ctx.verify_mode == ssl_mod.CERT_REQUIRED
    assert ctx.check_hostname is True
