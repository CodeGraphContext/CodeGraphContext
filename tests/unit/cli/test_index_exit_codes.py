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
