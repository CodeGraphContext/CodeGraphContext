"""LadybugDB availability must mean "runnable", not merely "installed" (#1731).

Some ladybug wheels (Windows) ship neither the pybind extension nor the lbug
C-API shared library; the package imports fine and the first Database() dies.
"""
import sys
import types

import pytest

import codegraphcontext.core as core


@pytest.fixture(autouse=True)
def _fresh_probe():
    core.ladybugdb_unavailable_reason.cache_clear()
    yield
    core.ladybugdb_unavailable_reason.cache_clear()


def _fake_ladybug(monkeypatch, *, pybind, capi_error=None):
    pkg = types.ModuleType("ladybug")
    pkg.__path__ = []
    backend = types.ModuleType("ladybug._backend")
    backend.get_pybind_module = lambda: pybind

    def get_capi_module():
        if capi_error is not None:
            raise capi_error
        return object()

    backend.get_capi_module = get_capi_module
    monkeypatch.setitem(sys.modules, "ladybug", pkg)
    monkeypatch.setitem(sys.modules, "ladybug._backend", backend)
    monkeypatch.setattr(core.importlib.util, "find_spec", lambda name: object())


def test_missing_native_engine_is_unavailable(monkeypatch):
    _fake_ladybug(
        monkeypatch,
        pybind=None,
        capi_error=RuntimeError("Could not find lbug C API shared library."),
    )
    reason = core.ladybugdb_unavailable_reason()
    assert reason is not None and "native engine" in reason
    assert "Could not find lbug C API shared library" in reason
    assert core._is_ladybugdb_available() is False


def test_pybind_extension_is_enough(monkeypatch):
    _fake_ladybug(monkeypatch, pybind=object(), capi_error=RuntimeError("unused"))
    assert core.ladybugdb_unavailable_reason() is None
    assert core._is_ladybugdb_available() is True


def test_capi_library_is_enough(monkeypatch):
    _fake_ladybug(monkeypatch, pybind=None)
    assert core._is_ladybugdb_available() is True


def test_not_installed(monkeypatch):
    monkeypatch.setattr(core.importlib.util, "find_spec", lambda name: None)
    assert core.ladybugdb_unavailable_reason() == "LadybugDB is not installed"


def test_explicit_selection_names_the_real_reason(monkeypatch):
    _fake_ladybug(
        monkeypatch,
        pybind=None,
        capi_error=OSError("lbug_shared.dll not found"),
    )
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "ladybugdb")
    with pytest.raises(ValueError) as exc:
        core.get_database_manager()
    msg = str(exc.value)
    assert "native engine could not be loaded" in msg
    assert "lbug_shared.dll not found" in msg
