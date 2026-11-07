"""Watch attachment must prepare repository state before scanning or events."""

from unittest.mock import MagicMock, call, patch

import pytest

from codegraphcontext.core.watcher import CodeWatcher, RepositoryEventHandler


@pytest.mark.parametrize(
    ("perform_initial_scan", "sync_on_start", "scan"),
    [(False, False, None), (False, True, "sync"), (True, False, "initial")],
)
def test_repository_is_ready_before_scan_and_observer_schedule(tmp_path, perform_initial_scan, sync_on_start, scan):
    builder = MagicMock()
    ordered = MagicMock()
    ordered.attach_mock(builder.add_repository_to_graph, "repository")
    with (
        patch("codegraphcontext.core.watcher.Observer") as observer_cls,
        patch.object(RepositoryEventHandler, "_initial_scan") as initial,
        patch.object(RepositoryEventHandler, "synchronize_with_disk") as sync,
    ):
        ordered.attach_mock(initial, "initial")
        ordered.attach_mock(sync, "sync")
        ordered.attach_mock(observer_cls.return_value.schedule, "schedule")
        watcher = CodeWatcher(builder, use_polling=False)
        watcher.watch_directory(
            str(tmp_path),
            perform_initial_scan=perform_initial_scan,
            sync_on_start=sync_on_start,
        )

    handler = watcher.handlers[str(tmp_path.resolve())]
    expected = [
        call.repository(
            tmp_path.resolve(),
            is_dependency=False,
            preserve_existing=sync_on_start or not perform_initial_scan,
        )
    ]
    if scan:
        expected.append(getattr(call, scan)())
    expected.append(call.schedule(handler, str(tmp_path.resolve()), recursive=True))
    assert ordered.mock_calls == expected


def test_failed_repository_initialization_does_not_attach_watcher(tmp_path):
    builder = MagicMock()
    builder.add_repository_to_graph.side_effect = RuntimeError("database unavailable")
    with patch("codegraphcontext.core.watcher.Observer"):
        watcher = CodeWatcher(builder, use_polling=False)
        with pytest.raises(RuntimeError, match="database unavailable"):
            watcher.watch_directory(str(tmp_path), perform_initial_scan=False)

    watcher.observer.schedule.assert_not_called()
    assert watcher.watched_paths == set()
    assert watcher.watches == {}
    assert watcher.handlers == {}
