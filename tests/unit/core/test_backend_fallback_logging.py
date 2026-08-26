"""
Regression tests for #1331 — a backend fallback must name the backend it landed on.

The bug these pin down: when an explicitly requested backend was unavailable,
`get_database_manager` returned a *different* backend without logging which one.
The user's only signal was the banner naming the backend they *asked* for, so an
interpreter where FalkorDB Lite cannot load was indistinguishable from one where
it loaded fine — while queries silently ran against a different, often empty, DB.
"""
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
    monkeypatch.setattr(
        core,
        "_is_ladybugdb_available",
        lambda: available == "ladybugdb",
    )
    monkeypatch.setattr(core, "_is_neo4j_configured", lambda: available == "neo4j")
    monkeypatch.setattr(core, "_is_nornic_configured", lambda: available == "nornic")


def test_explicit_falkordb_does_not_fallback_to_ladybug(monkeypatch, fallback_log):
    """An unavailable explicitly selected FalkorDB must fail without switching stores."""
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "falkordb")
    monkeypatch.setattr(core, "is_falkordb_usable", lambda: False)
    _only_backend(monkeypatch, "ladybugdb")

    with pytest.raises(ValueError, match="strict and will not fall back"):
        core.get_database_manager()

    assert fallback_log == []


def test_no_backend_available_still_raises(monkeypatch, fallback_log):
    """Funnelling through the helper must not swallow the 'nothing installed' error."""
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "falkordb")
    monkeypatch.setattr(core, "is_falkordb_usable", lambda: False)
    _only_backend(monkeypatch, "none-of-them")

    with pytest.raises(ValueError, match="FalkorDB Lite"):
        core.get_database_manager()
