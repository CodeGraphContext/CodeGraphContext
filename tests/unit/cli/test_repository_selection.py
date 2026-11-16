"""Interactive deletion must preserve the chosen graph identity and safeguards."""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from codegraphcontext.cli import cli_helpers, main, repository_selection

runner = CliRunner()


@pytest.mark.parametrize("command", ["delete", "rm"])
def test_terminal_delete_uses_selected_key_and_context(command):
    services = (MagicMock(), MagicMock(), MagicMock(), SimpleNamespace())
    key = "/moved project/repo"
    services[2].list_indexed_repositories.return_value = [{"name": "repo", "path": key}]
    with ExitStack() as stack:
        stack.enter_context(patch.object(main, "_load_credentials"))
        stack.enter_context(patch.object(main.config_manager, "is_db_deletion_allowed", return_value=True))
        stack.enter_context(patch.object(main, "sys", SimpleNamespace(
            stdin=SimpleNamespace(isatty=lambda: True), stdout=SimpleNamespace(isatty=lambda: True))))
        init = stack.enter_context(patch.object(cli_helpers, "_initialize_services", return_value=services))
        stack.enter_context(patch.object(cli_helpers, "select_repository", return_value=key))
        stack.enter_context(patch("typer.confirm", return_value=True))
        result = runner.invoke(main.app, [command, "--context", "project"])
    assert result.exit_code == 0, result.output
    init.assert_called_once_with("project")
    services[1].delete_indexed_repository_from_graph.assert_called_once_with(key)
    services[1].delete_repository_from_graph.assert_not_called()
    services[0].close_driver.assert_called_once()


@pytest.mark.parametrize(
    "args,stdin_tty,stdout_tty,allowed",
    [([], False, True, True), ([], True, False, True),
     (["--yes"], True, True, True), ([], True, True, False)],
)
def test_missing_target_never_prompts_or_queries_in_scripts_or_when_disabled(args, stdin_tty, stdout_tty, allowed):
    with (
        patch.object(main, "_load_credentials"),
        patch.object(main.config_manager, "is_db_deletion_allowed", return_value=allowed),
        patch.object(main, "sys", SimpleNamespace(
            stdin=SimpleNamespace(isatty=lambda: stdin_tty), stdout=SimpleNamespace(isatty=lambda: stdout_tty))),
        patch.object(main, "delete_selected_repository_helper") as helper,
        patch.object(main, "delete_helper") as explicit,
    ):
        result = runner.invoke(main.app, ["delete", *args])
    assert result.exit_code == 1
    helper.assert_not_called()
    explicit.assert_not_called()


@pytest.mark.parametrize("failure", ["empty", "cancel", "decline", "eof", "interrupt", "query", "missing", "write"])
def test_selection_failure_never_deletes_another_key_and_closes_database(failure):
    services = (MagicMock(), MagicMock(), MagicMock(), SimpleNamespace())
    key = "/stored/repo"
    services[2].list_indexed_repositories.return_value = [] if failure == "empty" else [{"path": key}]
    if failure == "query":
        services[2].list_indexed_repositories.side_effect = RuntimeError("query failed")
    if failure == "missing":
        services[1].delete_indexed_repository_from_graph.return_value = False
    if failure == "write":
        services[1].delete_indexed_repository_from_graph.side_effect = RuntimeError("write failed")
    with (
        patch.object(cli_helpers, "_initialize_services", return_value=services),
        patch.object(cli_helpers, "select_repository", return_value=None if failure == "cancel" else key) as selector,
        patch("typer.confirm", return_value=failure != "decline") as confirm,
        pytest.raises(Exception) as exc,
    ):
        if failure == "eof":
            confirm.side_effect = EOFError
        elif failure == "interrupt":
            confirm.side_effect = KeyboardInterrupt
        cli_helpers.delete_selected_repository_helper()
    assert getattr(exc.value, "exit_code", None) == 1
    if failure in ("missing", "write"):
        services[1].delete_indexed_repository_from_graph.assert_called_once_with(key)
    else:
        services[1].delete_indexed_repository_from_graph.assert_not_called()
    if failure in ("empty", "query"):
        selector.assert_not_called()
    services[1].delete_repository_from_graph.assert_not_called()
    services[0].close_driver.assert_called_once()


def test_selector_disambiguates_names_and_preserves_exact_paths():
    records = [
        {"name": "same", "path": "/moved/with spaces/same"},
        {"name": "same", "path": r"C:\\Work\\same", "is_dependency": True},
        {"name": "same", "path": "/other/same"},
        {"name": "same", "path": "/other/same"},
    ]
    selected = records[1]["path"]
    with patch.object(repository_selection.inquirer, "fuzzy") as prompt:
        prompt.return_value.execute.return_value = selected
        assert repository_selection.select_repository(records) == selected
        choices = prompt.call_args.kwargs["choices"]
    assert len(choices) == 3
    assert {c["value"] for c in choices} == {r["path"] for r in records}
    assert len({c["name"] for c in choices}) == 3
    assert all(c["value"] in c["name"] for c in choices)


@pytest.mark.parametrize("error", [KeyboardInterrupt, EOFError])
def test_selector_handles_terminal_cancellation(error):
    with patch.object(repository_selection.inquirer, "fuzzy") as prompt:
        prompt.return_value.execute.side_effect = error
        assert repository_selection.select_repository([{"path": "/repo"}]) is None


def test_empty_selector_does_not_open_a_prompt():
    with patch.object(repository_selection.inquirer, "fuzzy") as prompt:
        assert repository_selection.select_repository([]) is None
    prompt.assert_not_called()
