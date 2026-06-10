from codegraphcontext.core import watcher


class NativeObserver:
    pass


class PollingObserver:
    pass


def test_code_watcher_uses_native_observer_by_default(monkeypatch):
    monkeypatch.delenv(watcher.POLLING_ENV_VAR, raising=False)
    monkeypatch.setattr(watcher, "Observer", NativeObserver)
    monkeypatch.setattr(watcher, "PollingObserver", PollingObserver)

    code_watcher = watcher.CodeWatcher(graph_builder=object())

    assert isinstance(code_watcher.observer, NativeObserver)


def test_code_watcher_uses_polling_observer_when_requested(monkeypatch):
    monkeypatch.delenv(watcher.POLLING_ENV_VAR, raising=False)
    monkeypatch.setattr(watcher, "Observer", NativeObserver)
    monkeypatch.setattr(watcher, "PollingObserver", PollingObserver)

    code_watcher = watcher.CodeWatcher(graph_builder=object(), use_polling=True)

    assert isinstance(code_watcher.observer, PollingObserver)


def test_code_watcher_uses_polling_observer_from_env(monkeypatch):
    monkeypatch.setenv(watcher.POLLING_ENV_VAR, "true")
    monkeypatch.setattr(watcher, "Observer", NativeObserver)
    monkeypatch.setattr(watcher, "PollingObserver", PollingObserver)

    code_watcher = watcher.CodeWatcher(graph_builder=object())

    assert isinstance(code_watcher.observer, PollingObserver)


def test_explicit_native_observer_overrides_polling_env(monkeypatch):
    monkeypatch.setenv(watcher.POLLING_ENV_VAR, "1")
    monkeypatch.setattr(watcher, "Observer", NativeObserver)
    monkeypatch.setattr(watcher, "PollingObserver", PollingObserver)

    code_watcher = watcher.CodeWatcher(graph_builder=object(), use_polling=False)

    assert isinstance(code_watcher.observer, NativeObserver)
