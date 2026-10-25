"""Regression for silently narrowed integer identities in Ladybug batches."""

import importlib.util
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.database_embedded_kuzu import EmbeddedSessionWrapper


NATIVE_SCRIPT = r'''
import tempfile
from pathlib import Path

import ladybug
from codegraphcontext.core import ladybugdb_unavailable_reason
from codegraphcontext.core.database_embedded_kuzu import EmbeddedSessionWrapper

reason = ladybugdb_unavailable_reason()
if reason:
    print(reason)
    raise SystemExit(77)

with tempfile.TemporaryDirectory() as root:
    db = ladybug.Database(str(Path(root) / "db"), buffer_pool_size=256 * 1024 * 1024)
    conn = ladybug.Connection(db)
    session = EmbeddedSessionWrapper(conn, backend_id="ladybugdb")
    session.run("CREATE NODE TABLE NumericProbe(uid STRING, line_number INT64, PRIMARY KEY(uid))")
    query = "UNWIND $batch AS row RETURN row.line_number AS line"
    store = "UNWIND $batch AS row MERGE (n:NumericProbe {uid: row.uid}) SET n.line_number = row.line_number"
    try:
        # The first row keeps the same type signature while later rows cross
        # signed/unsigned 8/16/32-bit boundaries. The old cache returns -70
        # instead of 186 after the 538 execution on ladybug 0.19.1.
        values = [65, 538, 186, 128, 65536, 2**31 + 17, 255]
        for index, value in enumerate(values):
            rows = [{"line_number": 64}, {"line_number": value}]
            actual = [r["line"] for r in session.run(query, batch=rows).data()]
            assert actual == [64, value], (value, actual)
            session.run(store, batch=[
                {"uid": f"{index}-a", "line_number": 64},
                {"uid": f"{index}-b", "line_number": value},
            ])
        actual = {r["uid"]: r["line"] for r in session.run(
            "MATCH (n:NumericProbe) RETURN n.uid AS uid, n.line_number AS line"
        ).data()}
        assert actual == {
            f"{i}-{suffix}": value
            for i, number in enumerate(values)
            for suffix, value in (("a", 64), ("b", number))
        }, actual
        print("numeric batch reads and stored identities preserved")
    finally:
        conn.close()
        db.close()
'''


def test_native_ladybug_integer_widths_and_stored_identity():
    if importlib.util.find_spec("ladybug") is None:
        pytest.skip("ladybug is not installed")
    # Kuzu and Ladybug native extensions can collide when imported in one
    # process. Run the native regression separately from the Kuzu unit suite.
    result = subprocess.run(
        [sys.executable, "-c", NATIVE_SCRIPT], capture_output=True, text=True, timeout=60,
    )
    if result.returncode == 77:
        pytest.skip(result.stdout.strip())
    assert result.returncode == 0, result.stdout + result.stderr
    assert "stored identities preserved" in result.stdout


def test_fresh_statement_is_closed_even_when_execution_fails():
    conn = MagicMock()
    conn.execute.side_effect = ValueError("query failed")
    session = EmbeddedSessionWrapper(conn, backend_id="ladybugdb")
    with pytest.raises(ValueError, match="query failed"):
        session._execute_bound("query", {"batch": [{"line_number": 64}, {"line_number": 538}]})
    conn.prepare.return_value.close.assert_called_once_with()


@pytest.mark.parametrize("backend,params", [
    ("kuzudb", {"batch": [{"line_number": 538}]}),
    ("ladybugdb", {"line_number": 538}),
    ("ladybugdb", {"batch": [{"line_number": 538}]}),
    ("ladybugdb", {"batch": [{"enabled": True, "name": "value"}]}),
])
def test_other_backends_and_scalar_or_noninteger_parameters_keep_normal_execution(backend, params):
    conn = MagicMock()
    session = EmbeddedSessionWrapper(conn, backend_id=backend)
    session._execute_bound("query", params)
    conn.prepare.assert_not_called()
    conn.execute.assert_called_once_with("query", params)
