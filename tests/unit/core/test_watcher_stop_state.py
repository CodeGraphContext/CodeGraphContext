"""#1519: CodeWatcher.stop() must clear watch state, not just handlers.

A stopped watchdog Observer cannot be restarted; a surviving watched_paths
entry makes watch_directory answer "Already watching" for a dead observer.
"""
from unittest.mock import MagicMock

from codegraphcontext.core.watcher import CodeWatcher


def _bare_watcher():
    w = CodeWatcher.__new__(CodeWatcher)
    w.graph_builder = MagicMock()
    w.observer = MagicMock()
    w.observer.is_alive.return_value = True
    w.watched_paths = {"/repo/a"}
    w.watches = {"/repo/a": object()}
    handler = MagicMock()
    w.handlers = {"/repo/a": handler}
    return w, handler


def test_stop_clears_all_watch_state():
    w, handler = _bare_watcher()
    w.stop()
    handler.cancel_timers.assert_called_once()
    assert w.handlers == {}
    assert w.watched_paths == set()
    assert w.watches == {}
    w.observer.stop.assert_called_once()
    w.observer.join.assert_called_once()
