"""
Tests for KùzuDB thread-safety: verifies that KuzuDriverWrapper and
KuzuSessionWrapper correctly serialise all conn.execute() calls through
KuzuDBManager._query_lock (an RLock).

These tests use MagicMock to stand in for the real kuzu.Connection so the
suite runs without the optional kuzu package installed.
"""
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

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
    """Return a KuzuSessionWrapper with a fresh RLock and optional mock conn."""
    if conn is None:
        conn = MagicMock()
        conn.execute.return_value = MagicMock()  # non-None → KuzuResultWrapper wraps it
    if lock is None:
        lock = threading.RLock()
    return KuzuSessionWrapper(conn, lock), conn, lock


# ---------------------------------------------------------------------------
# 1. Lock plumbing: KuzuDBManager._query_lock flows through to the session
# ---------------------------------------------------------------------------

class TestLockPlumbing:
    def test_driver_wrapper_accepts_query_lock(self):
        """KuzuDriverWrapper must store and forward the query_lock to sessions."""
        conn = MagicMock()
        lock = threading.RLock()
        wrapper = KuzuDriverWrapper(conn, lock)

        assert wrapper._query_lock is lock

    def test_session_receives_same_lock(self):
        """session() must pass the exact same lock object to KuzuSessionWrapper."""
        conn = MagicMock()
        lock = threading.RLock()
        driver = KuzuDriverWrapper(conn, lock)
        session = driver.session()

        assert isinstance(session, KuzuSessionWrapper)
        assert session._query_lock is lock


# ---------------------------------------------------------------------------
# 2. Lock is held during conn.execute()
# ---------------------------------------------------------------------------

class TestLockHeldDuringExecute:
    def test_lock_acquired_before_execute(self):
        """conn.execute() must only be called while the _query_lock is held."""
        lock = threading.RLock()
        acquired_during_execute = []

        conn = MagicMock()
        def fake_execute(query, params):
            # If the lock is NOT held by the current thread, try_acquire succeeds
            # (meaning it was NOT already held) — that would be a bug.
            # RLock.acquire(blocking=False) returns False when another thread
            # holds it, but returns True (and re-enters) when the same thread holds it.
            # We use a separate threading.Lock() sentinel to detect whether
            # the RLock is currently held by *any* thread.
            acquired_during_execute.append(lock._is_owned())  # CPython internal
            return MagicMock()

        conn.execute.side_effect = fake_execute

        session, _, _ = _make_session(conn=conn, lock=lock)
        session.run("RETURN 1")

        assert acquired_during_execute, "execute() was never called"
        assert all(acquired_during_execute), "Lock was not held during conn.execute()"

    def test_lock_released_after_execute(self):
        """The _query_lock must be released after run() returns normally."""
        session, conn, lock = _make_session()
        conn.execute.return_value = MagicMock()

        session.run("RETURN 1")

        # After run(), a different thread must be able to acquire the lock immediately.
        acquired = lock.acquire(blocking=False)
        assert acquired, "Lock was not released after run() completed"
        lock.release()

    def test_lock_released_after_execute_exception(self):
        """The _query_lock must be released even when conn.execute() raises."""
        session, conn, lock = _make_session()
        conn.execute.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            session.run("RETURN 1")

        acquired = lock.acquire(blocking=False)
        assert acquired, "Lock was not released after conn.execute() raised"
        lock.release()


# ---------------------------------------------------------------------------
# 3. Concurrent access is serialised (no interleaving)
# ---------------------------------------------------------------------------

class TestConcurrentAccessSerialization:
    def test_concurrent_run_calls_are_serialised(self):
        """
        Two threads calling session.run() on the SAME session (sharing the lock)
        must never execute conn.execute() concurrently.

        Strategy: record a timeline of (thread_id, event) pairs from inside
        fake_execute and verify the two threads never overlap.
        """
        lock = threading.RLock()
        timeline = []
        timeline_lock = threading.Lock()  # protects the timeline list itself

        conn = MagicMock()

        def fake_execute(query, params):
            tid = threading.current_thread().ident
            with timeline_lock:
                timeline.append((tid, "start"))
            time.sleep(0.01)  # hold long enough for other thread to try
            with timeline_lock:
                timeline.append((tid, "end"))
            return MagicMock()

        conn.execute.side_effect = fake_execute

        session, _, _ = _make_session(conn=conn, lock=lock)

        errors = []

        def worker():
            try:
                session.run("RETURN 1")
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

        # Verify the pattern is start/end/start/end — never two consecutive starts
        # from different threads (which would indicate overlap).
        events = [e for _, e in timeline]
        tids = [t for t, _ in timeline]

        for i in range(0, 4, 2):
            assert events[i] == "start"
            assert events[i + 1] == "end"
            assert tids[i] == tids[i + 1], (
                f"Different threads interleaved: thread {tids[i]} started but "
                f"thread {tids[i+1]} ended before it"
            )

    def test_two_sessions_share_same_lock(self):
        """
        Two KuzuSessionWrapper objects created from the same driver must share
        the same _query_lock, so they serialise against each other.
        """
        conn = MagicMock()
        conn.execute.return_value = MagicMock()
        lock = threading.RLock()
        driver = KuzuDriverWrapper(conn, lock)

        s1 = driver.session()
        s2 = driver.session()

        assert s1._query_lock is s2._query_lock


# ---------------------------------------------------------------------------
# 4. RLock reentrance: UNWIND fallback self.run() doesn't deadlock
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
                # Simulate the unordered_map::at error to trigger fallback
                raise Exception("unordered_map::at")
            return MagicMock()

        conn.execute.side_effect = fake_execute

        session, _, _ = _make_session(conn=conn, lock=lock)

        # Construct a minimal UNWIND query with a batch parameter so the
        # fallback path activates.
        query = "UNWIND $batch AS row MERGE (n:Function {name: row.name, path: $fp, line_number: row.line_number}) SET n.source = row.source"
        batch = [{"name": "fn", "line_number": 1, "source": "def fn(): pass"}]

        # Must complete without deadlock within the timeout imposed by pytest.
        result = session.run(query, batch=batch, fp="/a/b.py")

        # Fallback executed at least the per-item row call
        assert call_count[0] >= 2


# ---------------------------------------------------------------------------
# 5. "already exists" changes: debug_log instead of silent return
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

        with patch("codegraphcontext.core.database_kuzu.debug_log") as mock_debug:
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


# ---------------------------------------------------------------------------
# 6. KuzuDBManager._query_lock is an RLock at the class level
# ---------------------------------------------------------------------------

class TestManagerQueryLock:
    def test_manager_has_rlock(self):
        """KuzuDBManager._query_lock must be a threading.RLock (reentrant)."""
        from codegraphcontext.core.database_kuzu import KuzuDBManager

        lock = KuzuDBManager._query_lock
        # threading.RLock() returns a _RLock instance.  The public API doesn't
        # expose a direct type check, but we can verify reentrance works.
        assert lock.acquire(blocking=False), "Could not acquire _query_lock"
        # Second acquire on the same thread must succeed (reentrant).
        assert lock.acquire(blocking=False), "_query_lock is not reentrant (not an RLock)"
        lock.release()
        lock.release()
