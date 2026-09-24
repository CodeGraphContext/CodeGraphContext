"""
Regression tests for #1331 — a backend fallback must name the backend it landed on.

The bug these pin down: when an explicitly requested backend was unavailable,
`get_database_manager` returned a *different* backend without logging which one.
The user's only signal was the banner naming the backend they *asked* for, so an
interpreter where FalkorDB Lite cannot load was indistinguishable from one where
it loaded fine — while queries silently ran against a different, often empty, DB.
"""
import sys

import pytest

import codegraphcontext.core as core


@pytest.fixture
def fallback_log(monkeypatch):
    """Capture warning_logger output emitted during backend selection."""
    messages = []

    import codegraphcontext.utils.debug_log as debug_log

    monkeypatch.setattr(debug_log, "warning_logger", messages.append)
    monkeypatch.setattr(debug_log, "info_logger", lambda *_a, **_k: None)
    return messages


def _only_backend(monkeypatch, available):
    """Make exactly one backend look available, and none of the others."""
    for name, flag in (
        ("_is_kuzudb_available", "kuzudb"),
        ("_is_ladybugdb_available", "ladybugdb"),
    ):
        monkeypatch.setattr(core, name, lambda f=flag: f == available)
    monkeypatch.setattr(core, "_is_neo4j_configured", lambda: available == "neo4j")
    monkeypatch.setattr(core, "_is_nornic_configured", lambda: available == "nornic")


def test_falkordb_to_kuzu_fallback_names_kuzu(monkeypatch, fallback_log):
    """The Failure Mode 1 from #1331: FalkorDB unusable, Kùzu takes over silently."""
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "falkordb")
    monkeypatch.setattr(core, "is_falkordb_usable", lambda: False)
    _only_backend(monkeypatch, "kuzudb")

    sentinel = object()
    fake = type(sys)("codegraphcontext.core.database_kuzu")
    fake.KuzuDBManager = lambda db_path=None: sentinel
    monkeypatch.setitem(sys.modules, "codegraphcontext.core.database_kuzu", fake)

    assert core.get_database_manager() is sentinel

    joined = " ".join(fallback_log)
    assert "fallback" in joined.lower(), f"no fallback logged: {fallback_log!r}"
    assert "Kùzu" in joined, f"fallback did not name the backend it landed on: {fallback_log!r}"


def test_kuzu_missing_fallback_names_the_replacement(monkeypatch, fallback_log):
    """Explicit kuzudb with Kùzu absent must still say what it fell back to."""
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "kuzudb")
    _only_backend(monkeypatch, "ladybugdb")

    sentinel = object()
    fake = type(sys)("codegraphcontext.core.database_ladybug")
    fake.LadybugDBManager = lambda db_path=None: sentinel
    monkeypatch.setitem(sys.modules, "codegraphcontext.core.database_ladybug", fake)

    assert core.get_database_manager() is sentinel
    assert any("LadybugDB" in m for m in fallback_log), fallback_log


def test_no_backend_available_still_raises(monkeypatch, fallback_log):
    """Funnelling through the helper must not swallow the 'nothing installed' error."""
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "kuzudb")
    _only_backend(monkeypatch, "none-of-them")

    with pytest.raises(ValueError, match="Kùzu is not installed"):
        core.get_database_manager()
