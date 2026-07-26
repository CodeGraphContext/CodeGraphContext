"""
Tests for KùzuDB thread-safety: verifies that KuzuDriverWrapper and
KuzuSessionWrapper correctly serialise write conn.execute() calls through
_write_lock and support concurrent pool-based reads.

These tests use MagicMock to stand in for the real kuzu.Connection so the
suite runs without the optional kuzu package installed.
"""
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import queue

# ---------------------------------------------------------------------------
# Import the wrappers directly (no kuzu needed for these classes).
# ---------------------------------------------------------------------------
from codegraphcontext.core.database_kuzu import (
    KuzuDriverWrapper,
    KuzuResultWrapper,
    KuzuSessionWrapper,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(conn=None, lock=None):
    """Return a KuzuSessionWrapper with a fresh Lock/RLock and optional mock conn."""
    if conn is None:
        conn = MagicMock()
        conn.execute.return_value = MagicMock()  # non-None → KuzuResultWrapper wraps it
    if lock is None:
        lock = threading.RLock()
    return KuzuSessionWrapper(conn, lock), conn, lock


# ---------------------------------------------------------------------------
# 1. Lock plumbing: _write_lock flows through to the session
# ---------------------------------------------------------------------------

class TestLockPlumbing:
    def test_driver_wrapper_accepts_write_lock_compat(self):
        """KuzuDriverWrapper must accept a single lock for backward compatibility."""
        conn = MagicMock()
        lock = threading.RLock()
        wrapper = KuzuDriverWrapper(conn, lock)

        assert wrapper._write_lock is lock
        assert wrapper._pool is None

    def test_driver_wrapper_accepts_pool_and_lock(self):
        """KuzuDriverWrapper must store pool and write_lock and forward them to sessions."""
        db = MagicMock()
        pool = queue.Queue()
        conn = MagicMock()
        pool.put(conn)
        lock = threading.RLock()
        driver = KuzuDriverWrapper(db, pool, lock)

        assert driver._pool is pool
        assert driver._write_lock is lock

        session = driver.session()
        assert isinstance(session, KuzuSessionWrapper)
        assert session._write_lock is lock
        assert session.conn is conn


# ---------------------------------------------------------------------------
# 2. Lock is held during write conn.execute(), but not read conn.execute()
# ---------------------------------------------------------------------------

class TestLockHeldDuringExecute:
    def test_lock_acquired_before_write_execute(self):
        """conn.execute() must only be called while the _write_lock is held for writes."""
        lock = threading.RLock()
        acquired_during_execute = []

        conn = MagicMock()
        def fake_execute(query, params):
            acquired_during_execute.append(lock._is_owned())  # CPython internal
            return MagicMock()

        conn.execute.side_effect = fake_execute

        session, _, _ = _make_session(conn=conn, lock=lock)
        session.run("MERGE (n:Class {uid: '1'})")

        assert acquired_during_execute, "execute() was never called"
        assert all(acquired_during_execute), "Lock was not held during write conn.execute()"

    def test_lock_acquired_during_read_execute(self):
        """conn.execute() must hold _write_lock for reads too — kuzu.Connection is not thread-safe."""
        lock = threading.RLock()
        acquired_during_execute = []

        conn = MagicMock()
        def fake_execute(query, params):
            acquired_during_execute.append(lock._is_owned())
            return MagicMock()

        conn.execute.side_effect = fake_execute

        session, _, _ = _make_session(conn=conn, lock=lock)
        session.run("MATCH (n:Class) RETURN n")

        assert acquired_during_execute, "execute() was never called"
        assert all(acquired_during_execute), "Lock was not held during read conn.execute()"

    def test_lock_released_after_write_execute(self):
        """The _write_lock must be released after run() on a write query returns normally."""
        session, conn, lock = _make_session()
        conn.execute.return_value = MagicMock()

        session.run("MERGE (n:Class {uid: '1'})")

        acquired = lock.acquire(blocking=False)
        assert acquired, "Lock was not released after run() completed"
        lock.release()

    def test_lock_released_after_write_exception(self):
        """The _write_lock must be released even when write execution raises an exception."""
        session, conn, lock = _make_session()
        conn.execute.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            session.run("MERGE (n:Class {uid: '1'})")

        acquired = lock.acquire(blocking=False)
        assert acquired, "Lock was not released after conn.execute() raised"
        lock.release()


# ---------------------------------------------------------------------------
# 3. Pooled connections are returned on exit
# ---------------------------------------------------------------------------

class TestPoolReturnOnExit:
    def test_session_wrapper_returns_connection_to_pool(self):
        """KuzuSessionWrapper must return the connection to the pool on __exit__."""
        pool = queue.Queue()
        conn = MagicMock()
        pool.put(conn)
        lock = threading.Lock()

        assert pool.qsize() == 1

        with KuzuSessionWrapper(pool, lock) as session:
            assert session.conn is conn
            assert pool.qsize() == 0

        assert pool.qsize() == 1


# ---------------------------------------------------------------------------
# 4. Concurrent access is serialised for writes, parallel for reads
# ---------------------------------------------------------------------------

class TestConcurrentAccessSerialization:
    def test_concurrent_write_calls_are_serialised(self):
        """
        Two threads calling session.run() with a write query must never execute
        conn.execute() concurrently.
        """
        lock = threading.RLock()
        timeline = []
        timeline_lock = threading.Lock()

        conn = MagicMock()

        def fake_execute(query, params):
            tid = threading.current_thread().ident
            with timeline_lock:
                timeline.append((tid, "start"))
            time.sleep(0.01)
            with timeline_lock:
                timeline.append((tid, "end"))
            return MagicMock()

        conn.execute.side_effect = fake_execute

        session, _, _ = _make_session(conn=conn, lock=lock)

        errors = []

        def worker():
            try:
                session.run("MERGE (n:Class {uid: '1'})")
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=worker, daemon=True)
        t2 = threading.Thread(target=worker, daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Threads raised: {errors}"
        assert len(timeline) == 4, f"Unexpected timeline: {timeline}"

        events = [e for _, e in timeline]
        tids = [t for t, _ in timeline]

        for i in range(0, 4, 2):
            assert events[i] == "start"
            assert events[i + 1] == "end"
            assert tids[i] == tids[i + 1]


# ---------------------------------------------------------------------------
# 5. RLock reentrance: UNWIND fallback self.run() doesn't deadlock
# ---------------------------------------------------------------------------

class TestRLockReentrance:
    def test_recursive_run_does_not_deadlock(self):
        """
        The UNWIND fallback calls self.run() recursively from the same thread.
        A plain Lock would deadlock here; RLock must not.
        """
        lock = threading.RLock()
        call_count = [0]

        conn = MagicMock()

        def fake_execute(query, params):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("unordered_map::at")
            return MagicMock()

        conn.execute.side_effect = fake_execute

        session, _, _ = _make_session(conn=conn, lock=lock)

        query = "UNWIND $batch AS row MERGE (n:Function {name: row.name, path: $fp, line_number: row.line_number}) SET n.source = row.source"
        batch = [{"name": "fn", "line_number": 1, "source": "def fn(): pass"}]

        result = session.run(query, batch=batch, fp="/a/b.py")

        assert call_count[0] >= 2


# ---------------------------------------------------------------------------
# 6. "already exists" changes: debug_log instead of silent return
# ---------------------------------------------------------------------------

class TestAlreadyExistsLogging:
    def test_already_exists_returns_empty_result(self):
        """'already exists' errors must still return an empty KuzuResultWrapper."""
        session, conn, _ = _make_session()
        conn.execute.side_effect = Exception("Table foo already exists")

        result = session.run("CREATE NODE TABLE foo(id STRING, PRIMARY KEY(id))")

        assert isinstance(result, KuzuResultWrapper)

    def test_already_exists_calls_debug_log(self):
        """'already exists' errors must emit a debug_log message, not be silently dropped."""
        session, conn, _ = _make_session()
        conn.execute.side_effect = Exception("Table foo already exists")

        with patch("codegraphcontext.core.database_embedded_kuzu.debug_log") as mock_debug:
            session.run("CREATE NODE TABLE foo(id STRING, PRIMARY KEY(id))")

        assert mock_debug.called, "debug_log was not called for 'already exists' collision"
        logged_msg = mock_debug.call_args[0][0]
        assert "already exists" in logged_msg.lower() or "idempotent" in logged_msg.lower()

    def test_other_errors_still_propagate(self):
        """Errors that are not 'already exists' must still raise."""
        session, conn, _ = _make_session()
        conn.execute.side_effect = Exception("Syntax error near BLAH")

        with pytest.raises(Exception, match="Syntax error"):
            session.run("MATCH BLAH")
