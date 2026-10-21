import asyncio
from concurrent.futures import Future
from pathlib import Path
import threading
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.database_embedded_kuzu import EmbeddedConnectionPool
from codegraphcontext.core.jobs import JobManager
from codegraphcontext.core.watcher import RepositoryEventHandler
from codegraphcontext.server import MCPServer


def handler(tmp_path):
    return RepositoryEventHandler(MagicMock(), Path(tmp_path), debounce_interval=0.001, perform_initial_scan=False)


def test_unwatch_drains_callback_that_has_already_started(tmp_path):
    value = handler(tmp_path)
    started, finish, stopped = threading.Event(), threading.Event(), threading.Event()
    def action():
        started.set()
        assert finish.wait(5)
    value._debounce("a.py", action)
    assert started.wait(5)
    thread = threading.Thread(target=lambda: (value.cancel_timers(), stopped.set()))
    thread.start()
    assert not stopped.wait(0.05)
    finish.set()
    thread.join(5)
    assert stopped.is_set()
    late = threading.Event()
    value._debounce("b.py", late.set)
    assert not late.wait(0.05)
    assert not value.timers


def test_replaced_timer_cannot_run_a_stale_action(tmp_path, monkeypatch):
    value = handler(tmp_path)
    timers = []
    class ControlledTimer:
        def __init__(self, interval, callback):
            self.callback = callback
            timers.append(self)
        def cancel(self): pass
        def start(self): pass
    monkeypatch.setattr("codegraphcontext.core.watcher.threading.Timer", ControlledTimer)
    seen = []
    value._debounce("a.py", lambda: seen.append("old"))
    value._debounce("a.py", lambda: seen.append("new"))
    timers[0].callback()
    timers[1].callback()
    assert seen == ["new"]


def test_pool_rejects_new_sessions_and_waits_for_borrowed_connection():
    pool = EmbeddedConnectionPool()
    connection = object()
    pool.put(connection)
    assert pool.borrow() is connection
    with pytest.raises(RuntimeError, match="left open"):
        pool.quiesce(timeout=0)
    with pytest.raises(RuntimeError, match="closing"):
        pool.borrow(timeout=0)
    pool.release(connection)
    pool.quiesce(timeout=0)
    assert pool.get_nowait() is connection


def test_pool_failed_borrow_does_not_prevent_close():
    import queue
    pool = EmbeddedConnectionPool()
    with pytest.raises(queue.Empty): pool.borrow(timeout=0)
    pool.quiesce(timeout=0)


def test_async_shutdown_waits_for_indexing_before_teardown(monkeypatch):
    value = MCPServer.__new__(MCPServer)
    value.code_watcher = MagicMock()
    value.db_manager = object()
    value.job_manager = JobManager()
    future = Future()
    value.job_manager.track_future(future)
    closed = []
    monkeypatch.setattr("codegraphcontext.server._teardown_db_manager", lambda db: closed.append(db))
    with pytest.raises(RuntimeError, match="Indexing is still active"):
        value.shutdown()
    assert not closed
    async def run():
        task = asyncio.create_task(value.shutdown_async())
        await asyncio.sleep(0)
        assert not closed
        future.set_result(None)
        await task
    asyncio.run(run())
    assert closed == [value.db_manager]
    assert not value.job_manager.pending_futures()


def test_real_embedded_close_waits_for_session_then_reopens(tmp_path, monkeypatch):
    import os
    import time
    from codegraphcontext.core.database_kuzu import KuzuDBManager
    from codegraphcontext.core.database_ladybug import LadybugDBManager
    kind = LadybugDBManager if os.getenv("CGC_TEST_EMBEDDED_BACKEND") == "ladybugdb" else KuzuDBManager
    pytest.importorskip(kind.BACKEND_SPEC.python_module)
    monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "1024")
    manager = kind(str(tmp_path / "db"))
    driver = manager.get_driver()
    session = driver.session()
    closed = threading.Event()
    failures = []
    def close():
        try:
            manager.close_driver()
        except Exception as exc:
            failures.append(str(exc))
        finally:
            closed.set()
    thread = threading.Thread(target=close)
    thread.start()
    until = time.monotonic() + 5
    while not driver._pool._closing and time.monotonic() < until:
        time.sleep(0.001)
    try:
        assert driver._pool._closing and not closed.is_set()
        assert session.run("RETURN 1 AS n").data() == [{"n": 1}]
        with pytest.raises(RuntimeError, match="closing"):
            driver.session()
    finally:
        session.__exit__(None, None, None)
        thread.join(5)
    assert closed.is_set() and not failures
    try:
        with manager.get_driver().session() as reopened:
            assert reopened.run("RETURN 1 AS n").data() == [{"n": 1}]
    finally:
        manager.close_driver()
