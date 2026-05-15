"""
Unit tests for `cgc registry` CLI command – issue #626.

Verifies that:
- `cgc registry` (no subcommand) exits with code 0 and prints help text.
- `cgc registry --help` exits with code 0 and prints help text.
- `cgc registry list` still works (delegates to list_bundles).
"""

from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from codegraphcontext.cli.main import app

runner = CliRunner()


def test_registry_no_subcommand_exits_zero():
    """Running `cgc registry` without a subcommand should exit with code 0."""
    result = runner.invoke(app, ["registry"])
    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}.\nOutput:\n{result.output}"
    )


def test_registry_no_subcommand_shows_help():
    """Running `cgc registry` without a subcommand should print help text."""
    result = runner.invoke(app, ["registry"])
    output = result.output
    # Help should mention the available subcommands
    assert "list" in output
    assert "search" in output
    assert "download" in output
    assert "request" in output


def test_registry_help_flag_exits_zero():
    """Running `cgc registry --help` should exit with code 0."""
    result = runner.invoke(app, ["registry", "--help"])
    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}.\nOutput:\n{result.output}"
    )


def test_registry_help_flag_shows_help():
    """Running `cgc registry --help` should print help text."""
    result = runner.invoke(app, ["registry", "--help"])
    output = result.output
    assert "list" in output
    assert "search" in output
    assert "download" in output
    assert "request" in output


def test_registry_list_still_works():
    """Running `cgc registry list` should still call list_bundles."""
    import sys
    from unittest.mock import MagicMock

    # registry_commands imports `requests` at module level; stub it out so this
    # unit test doesn't need the optional network dependency installed.
    fake_requests = MagicMock()
    with patch.dict(sys.modules, {"requests": fake_requests}):
        import importlib
        import codegraphcontext.cli.registry_commands as reg_cmds
        importlib.reload(reg_cmds)
        with patch.object(reg_cmds, "fetch_available_bundles", return_value=[]):
            result = runner.invoke(app, ["registry", "list"])
    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}.\nOutput:\n{result.output}"
    )


def test_registry_no_subcommand_no_error_message():
    """Running `cgc registry` should NOT produce an error about a missing command."""
    result = runner.invoke(app, ["registry"])
    assert "Missing command" not in result.output
    assert "Error" not in result.output
