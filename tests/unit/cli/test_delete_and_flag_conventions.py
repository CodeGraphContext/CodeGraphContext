import re
"""Regression tests for CLI exit codes and short-flag conventions."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from codegraphcontext.cli import cli_helpers
from codegraphcontext.cli.main import app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain(text: str) -> str:
    """Strip ANSI escapes and collapse whitespace.

    Rich emits colour codes (and soft-wraps) whenever it thinks the terminal
    supports them — which it does in CI but not always locally. Asserting on
    raw `result.output` therefore passes on a dev machine and fails in CI with
    the expected text plainly visible, just interleaved with \x1b[1;36m codes.
    """
    return " ".join(_ANSI_RE.sub("", text).split())



def _services():
    db_manager = MagicMock()
    graph_builder = MagicMock()
    ctx = SimpleNamespace(cgcignore_path=None, mode="global")
    return db_manager, graph_builder, MagicMock(), ctx


def test_delete_helper_exits_nonzero_when_repository_not_found():
    """`cgc delete <not-indexed>` reported failure but exited 0, so scripts
    chaining on it treated a no-op as a successful delete."""
    services = _services()
    services[1].delete_repository_from_graph.return_value = False

    with (
        patch.object(cli_helpers, "_initialize_services", return_value=services),
        pytest.raises(typer.Exit) as exc_info,
    ):
        cli_helpers.delete_helper("/nonexistent/repo")

    assert exc_info.value.exit_code == 1
    services[0].close_driver.assert_called_once()


def test_delete_helper_exits_zero_on_success():
    services = _services()
    services[1].delete_repository_from_graph.return_value = True

    with patch.object(cli_helpers, "_initialize_services", return_value=services):
        cli_helpers.delete_helper("/some/repo")   # must not raise

    services[0].close_driver.assert_called_once()


def test_delete_helper_exits_nonzero_on_unexpected_error():
    services = _services()
    services[1].delete_repository_from_graph.side_effect = RuntimeError("boom")

    with (
        patch.object(cli_helpers, "_initialize_services", return_value=services),
        pytest.raises(typer.Exit) as exc_info,
    ):
        cli_helpers.delete_helper("/some/repo")

    assert exc_info.value.exit_code == 1
    services[0].close_driver.assert_called_once()


@pytest.mark.parametrize("command", ["visualize", "list", "stats", "index", "delete"])
def test_short_h_is_help_on_subcommands(command):
    """`-h` must mean --help everywhere. It previously bound to --host on
    `visualize`, so `cgc visualize -h` failed with 'requires an argument'."""
    result = runner.invoke(app, [command, "-h"])
    assert result.exit_code == 0
    assert "Usage:" in _plain(result.output)


def test_visualize_host_moved_to_capital_h():
    result = runner.invoke(app, ["visualize", "--help"])
    assert result.exit_code == 0
    normalised = _plain(result.output)
    assert "--host -H" in normalised


def test_index_command_registered_exactly_once():
    """`index` carried a duplicated @app.command() decorator."""
    names = [c.name or c.callback.__name__ for c in app.registered_commands]
    assert names.count("index") == 1
