"""Regression tests for destructive-delete confirmation and no-op watch commands."""
import ast
import inspect
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from codegraphcontext.cli import cli_helpers, main as cli_main
from codegraphcontext.cli.main import app

runner = CliRunner()


def _allow_deletion():
    return patch.object(cli_main.config_manager, "is_db_deletion_allowed", return_value=True)


def test_single_delete_requires_confirmation():
    """`--all` demanded a typer.confirm *and* typing 'delete all', while a
    single delete went straight through — irreversibly dropping a repository's
    entire graph on a typo, with no prompt and no undo."""
    with _allow_deletion(), \
         patch.object(cli_main, "delete_helper") as helper, \
         patch.object(cli_main, "_load_credentials"):
        result = runner.invoke(app, ["delete", "/some/repo"], input="n\n")

    assert result.exit_code == 1
    helper.assert_not_called()


def test_single_delete_proceeds_when_confirmed():
    with _allow_deletion(), \
         patch.object(cli_main, "delete_helper") as helper, \
         patch.object(cli_main, "_load_credentials"):
        result = runner.invoke(app, ["delete", "/some/repo"], input="y\n")

    assert result.exit_code == 0
    helper.assert_called_once()


def test_single_delete_aborts_when_stdin_is_closed():
    """Non-interactive callers must not have the delete silently succeed."""
    with _allow_deletion(), \
         patch.object(cli_main, "delete_helper") as helper, \
         patch.object(cli_main, "_load_credentials"):
        result = runner.invoke(app, ["delete", "/some/repo"], input="")

    assert result.exit_code != 0
    helper.assert_not_called()


def test_yes_flag_skips_the_prompt():
    with _allow_deletion(), \
         patch.object(cli_main, "delete_helper") as helper, \
         patch.object(cli_main, "_load_credentials"):
        result = runner.invoke(app, ["delete", "/some/repo", "--yes"], input="")

    assert result.exit_code == 0
    helper.assert_called_once()


def test_rm_shortcut_forwards_the_yes_flag():
    """Omitted, `yes` keeps its truthy OptionInfo sentinel and would skip the
    confirmation — the same delegation bug fixed in #1415."""
    source = inspect.getsource(cli_main.delete_abbrev)
    assert "yes=yes" in source


def test_delete_all_still_requires_its_double_confirmation():
    source = inspect.getsource(cli_main.delete)
    assert "delete all" in source
    assert "typer.confirm" in source


@pytest.mark.parametrize("helper", ["unwatch_helper", "list_watching_helper"])
def test_watch_commands_do_not_report_success(helper):
    """Both bodies were console.print only — no watcher state was touched —
    yet they exited 0. `cgc unwatch` even echoed a nonexistent path back as
    'Path specified:', which reads like confirmation."""
    with pytest.raises(typer.Exit) as exc_info:
        if helper == "unwatch_helper":
            getattr(cli_helpers, helper)("/never/watched/path")
        else:
            getattr(cli_helpers, helper)()

    assert exc_info.value.exit_code == 1


def test_unwatch_does_not_echo_the_path_as_confirmation():
    """Check the executable body, not the docstring (which describes the bug)."""
    tree = ast.parse(inspect.getsource(cli_helpers.unwatch_helper).lstrip())
    func = tree.body[0]
    body = func.body[1:] if ast.get_docstring(func) else func.body
    emitted = [
        node.value
        for stmt in body
        for node in ast.walk(stmt)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]

    assert not any("Path specified" in text for text in emitted)
