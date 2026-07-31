from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import typer

from codegraphcontext.cli import cli_helpers


async def _failing_index(*_args, **_kwargs):
    raise RuntimeError("boom")


def _services(tmp_path):
    db_manager = MagicMock()
    code_finder = MagicMock()
    code_finder.list_indexed_repositories.return_value = []
    ctx = SimpleNamespace(cgcignore_path=None, mode="global")
    return db_manager, MagicMock(), code_finder, ctx


def test_index_helper_exits_nonzero_on_indexing_failure(tmp_path):
    services = _services(tmp_path)
    services[1].estimate_processing_time.return_value = (2, 0.1)
    with (
        patch.object(cli_helpers, "_initialize_services", return_value=services),
        patch.object(cli_helpers, "_run_index_with_progress", side_effect=_failing_index),
        pytest.raises(typer.Exit) as exc_info,
    ):
        cli_helpers.index_helper(str(tmp_path))

    assert exc_info.value.exit_code == 1
    services[0].close_driver.assert_called_once()


def test_reindex_helper_exits_nonzero_on_indexing_failure(tmp_path):
    services = _services(tmp_path)
    with (
        patch.object(cli_helpers, "_initialize_services", return_value=services),
        patch.object(cli_helpers, "_run_index_with_progress", side_effect=_failing_index),
        pytest.raises(typer.Exit) as exc_info,
    ):
        cli_helpers.reindex_helper(str(tmp_path))

    assert exc_info.value.exit_code == 1
    services[0].close_driver.assert_called_once()


def test_index_helper_does_not_skip_directory_with_partial_index(tmp_path):
    """A prior one-file scan must not mark its parent directory complete."""
    (tmp_path / "indexed.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "missing.py").write_text("pass\n", encoding="utf-8")
    services = _services(tmp_path)
    services[1].estimate_processing_time.return_value = (2, 0.1)
    services[2].list_indexed_repositories.return_value = [{"path": str(tmp_path)}]

    session = MagicMock()
    session.run.return_value.single.return_value = {"file_count": 1}
    services[0].get_driver.return_value.session.return_value.__enter__.return_value = session

    with (
        patch.object(cli_helpers, "_initialize_services", return_value=services),
        patch.object(cli_helpers, "_run_index_with_progress") as run_index,
        patch.object(cli_helpers, "_print_index_execution_summary"),
    ):
        cli_helpers.index_helper(str(tmp_path))

    run_index.assert_called_once()
