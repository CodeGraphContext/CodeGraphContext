"""config_manager must stay importable in minimal envs (see issue #1251).

`rich` is a declared dependency, so these tests simulate its absence rather
than relying on an environment that lacks it — otherwise the fallback path
would never be exercised in CI and could rot unnoticed.

The module is loaded as a *separate* module object under its own name instead
of being evicted from `sys.modules`. Evicting it pollutes the rest of the
session: other modules did `from .config_manager import ...` and keep a
reference to the original object, so a later re-import yields a second,
different module and patches applied to one are invisible to the other.
config_manager has no relative imports, which is what makes standalone
loading safe here.
"""

import builtins
import importlib.util
import sys
from pathlib import Path

import pytest

CONFIG_MANAGER_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "codegraphcontext"
    / "cli"
    / "config_manager.py"
)


def _load_without_rich(monkeypatch):
    """Load config_manager as a standalone module with `rich` unimportable."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "rich" or name.startswith("rich."):
            raise ImportError("No module named 'rich' (simulated)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    spec = importlib.util.spec_from_file_location(
        "codegraphcontext_config_manager_norich", CONFIG_MANAGER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def norich_module(monkeypatch):
    return _load_without_rich(monkeypatch)


def test_config_manager_imports_without_rich(norich_module):
    assert norich_module.console is not None
    assert type(norich_module.console).__name__ == "_ConsoleFallback"


def test_fallback_table_renders_rows_without_rich(norich_module):
    """The fallback must actually print a table, not just import cleanly."""
    table = norich_module.Table(show_header=True)
    table.add_column("Key")
    table.add_column("Value")
    table.add_row("DEFAULT_DATABASE", "falkordb")

    rendered = str(table)
    assert "Key" in rendered and "Value" in rendered
    assert "DEFAULT_DATABASE" in rendered and "falkordb" in rendered


def test_fallback_console_print_accepts_a_table(norich_module, capsys):
    table = norich_module.Table()
    table.add_column("Key")
    table.add_row("INDEX_VARIABLES")
    norich_module.console.print(table)

    assert "INDEX_VARIABLES" in capsys.readouterr().out


def test_defaults_are_still_reachable_without_rich(norich_module):
    """Import must not be the only thing that works — config data too."""
    assert "DEFAULT_DATABASE" in norich_module.DEFAULT_CONFIG


def test_rich_is_used_when_available():
    """The fallback must not shadow rich in a normal install."""
    pytest.importorskip("rich")
    from codegraphcontext.cli import config_manager

    assert type(config_manager.console).__name__ == "Console"


def test_loading_the_fallback_leaves_the_real_module_untouched(monkeypatch):
    """Regression guard for this file itself: the isolation must not leak."""
    pytest.importorskip("rich")
    from codegraphcontext.cli import config_manager

    before = sys.modules["codegraphcontext.cli.config_manager"]
    _load_without_rich(monkeypatch)

    assert sys.modules["codegraphcontext.cli.config_manager"] is before
    assert type(config_manager.console).__name__ == "Console"
