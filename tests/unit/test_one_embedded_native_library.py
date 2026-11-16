"""The suite-wide guard against two embedded native libraries in one pytest process.

tests/conftest.py's autouse ``_one_embedded_native_library_per_process`` fails the
test that loads the second of kuzu / ladybug. Exercised here with stand-in module
objects so no native library is loaded.
"""

from __future__ import annotations

import sys
import types

import pytest

from tests import conftest as root_conftest


def _run_guard(monkeypatch, before, loaded_by_test):
    for name in ("kuzu", "ladybug"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    for name in before:
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    gen = root_conftest._one_embedded_native_library_per_process.__wrapped__()
    next(gen)
    for name in loaded_by_test:
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    with pytest.raises(StopIteration):
        next(gen)


def test_loading_the_second_library_fails_that_test(monkeypatch):
    with pytest.raises(pytest.fail.Exception, match=r"loaded \['ladybug'\].*held \['kuzu'\]"):
        _run_guard(monkeypatch, before=["kuzu"], loaded_by_test=["ladybug"])


def test_one_library_is_fine(monkeypatch):
    _run_guard(monkeypatch, before=[], loaded_by_test=["kuzu"])
    _run_guard(monkeypatch, before=["ladybug"], loaded_by_test=[])


def test_only_the_test_that_loads_it_is_blamed(monkeypatch):
    # both already present before this test: an earlier test was blamed, not this one
    _run_guard(monkeypatch, before=["kuzu", "ladybug"], loaded_by_test=[])
