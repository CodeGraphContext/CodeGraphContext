"""Regression tests for watcher rename handling and concurrent updates."""
import inspect
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from codegraphcontext.core import watcher as watcher_mod
from codegraphcontext.core.watcher import RepositoryEventHandler


def _handler(tmp_path):
    handler = RepositoryEventHandler.__new__(RepositoryEventHandler)
    handler.graph_builder = MagicMock()
    handler.repo_path = Path(tmp_path)
    handler.debounce_interval = 0.01
    handler.timers = {}
    handler._timers_lock = threading.Lock()
    handler._update_lock = threading.RLock()
    handler.imports_map = {}
    handler.all_file_data = []
    handler.ignore_spec = None
    handler.ignore_root = Path(tmp_path)
    return handler


def test_on_moved_handles_both_endpoints(tmp_path):
    """Only dest_path was processed, so the node for the *old* path and all of
    its symbols stayed in the graph forever. Every rename duplicated every
    symbol in the file; a refactoring session or a `git checkout` between
    branches accumulated them indefinitely."""
    handler = _handler(tmp_path)
    seen = []
    handler._debounce = lambda path, action: seen.append(path)

    handler.on_moved(SimpleNamespace(
        is_directory=False,
        src_path=str(tmp_path / "oldname.py"),
        dest_path=str(tmp_path / "newname.py"),
    ))

    assert str(tmp_path / "oldname.py") in seen, "source path must be processed"
    assert str(tmp_path / "newname.py") in seen, "destination path must be processed"


def test_on_moved_ignores_directories(tmp_path):
    handler = _handler(tmp_path)
    seen = []
    handler._debounce = lambda path, action: seen.append(path)

    handler.on_moved(SimpleNamespace(
        is_directory=True, src_path=str(tmp_path / "a"), dest_path=str(tmp_path / "b")
    ))

    assert seen == []


def test_handle_removal_deletes_the_stale_node(tmp_path):
    handler = _handler(tmp_path)
    old = tmp_path / "oldname.py"

    handler._handle_removal(str(old))

    handler.graph_builder.delete_file_from_graph.assert_called_once()
    assert "oldname.py" in handler.graph_builder.delete_file_from_graph.call_args[0][0]


def test_handle_removal_survives_a_failing_delete(tmp_path):
    handler = _handler(tmp_path)
    handler.graph_builder.delete_file_from_graph.side_effect = RuntimeError("boom")

    handler._handle_removal(str(tmp_path / "x.py"))   # must not raise


def test_fired_timers_are_removed_from_the_registry(tmp_path):
    """Timers were never removed after firing, so self.timers grew without
    bound for the life of the watcher."""
    handler = _handler(tmp_path)
    fired = threading.Event()
    handler._debounce("a.py", fired.set)

    assert fired.wait(timeout=5), "debounced action did not run"
    for _ in range(100):
        if not handler.timers:
            break
        time.sleep(0.01)

    assert handler.timers == {}, "fired timer left behind in self.timers"


def test_debounce_replaces_a_pending_timer(tmp_path):
    handler = _handler(tmp_path)
    calls = []
    handler._debounce("a.py", lambda: calls.append(1))
    handler._debounce("a.py", lambda: calls.append(2))
    time.sleep(0.3)

    assert calls == [2], "the superseded timer should have been cancelled"


def test_modification_handler_is_serialised(tmp_path):
    """Debounce is keyed per path, so N files changed inside the window fire N
    handler threads. They did read-modify-write on the shared imports_map and
    interleaved delete/add for overlapping caller sets, so one could delete
    edges another had just created."""
    handler = _handler(tmp_path)
    concurrent = []
    active = []
    lock = threading.Lock()

    def _slow(_path):
        with lock:
            active.append(1)
            concurrent.append(len(active))
        time.sleep(0.05)
        with lock:
            active.pop()

    handler._handle_modification_locked = _slow
    threads = [
        threading.Thread(target=handler._handle_modification, args=(f"f{i}.py",))
        for i in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max(concurrent) == 1, f"handlers ran concurrently (max {max(concurrent)})"


def test_cancel_timers_is_lock_guarded():
    source = inspect.getsource(watcher_mod.RepositoryEventHandler.cancel_timers)
    assert "_timers_lock" in source
