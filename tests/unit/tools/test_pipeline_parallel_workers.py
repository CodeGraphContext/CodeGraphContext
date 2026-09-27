"""Tests that the PARALLEL_WORKERS config drives indexing concurrency (#1340, #1732)."""
from unittest import mock

import pytest

from codegraphcontext.tools.indexing import pipeline


@pytest.mark.parametrize(
    "config_value,expected",
    [
        ("32", 32),
        ("1", 1),
        ("4", 4),
        ("40", pipeline.MAX_PARALLEL_WORKERS),
        ("5000", pipeline.MAX_PARALLEL_WORKERS),
        (None, pipeline.DEFAULT_PARALLEL_WORKERS),
        ("", pipeline.DEFAULT_PARALLEL_WORKERS),
        ("not-a-number", pipeline.DEFAULT_PARALLEL_WORKERS),
        ("0", pipeline.DEFAULT_PARALLEL_WORKERS),
        ("-5", pipeline.DEFAULT_PARALLEL_WORKERS),
    ],
)
def test_get_parallel_workers(config_value, expected):
    with mock.patch(
        "codegraphcontext.cli.config_manager.get_config_value",
        return_value=config_value,
    ):
        assert pipeline.get_parallel_workers() == expected


@pytest.mark.parametrize(
    "config_value,expected",
    [
        ("7", 7),
        ("32", 32),
        ("5000", pipeline.MAX_PARALLEL_WORKERS),
        (None, pipeline.WATCHER_DEFAULT_PARALLEL_WORKERS),
        ("", pipeline.WATCHER_DEFAULT_PARALLEL_WORKERS),
        ("not-a-number", pipeline.WATCHER_DEFAULT_PARALLEL_WORKERS),
        ("0", pipeline.WATCHER_DEFAULT_PARALLEL_WORKERS),
        ("-5", pipeline.WATCHER_DEFAULT_PARALLEL_WORKERS),
    ],
)
def test_get_parallel_workers_with_watcher_default(config_value, expected):
    """A positive value is shared. Only an empty or invalid value uses default=4."""
    with mock.patch(
        "codegraphcontext.cli.config_manager.get_config_value",
        return_value=config_value,
    ):
        assert (
            pipeline.get_parallel_workers(default=pipeline.WATCHER_DEFAULT_PARALLEL_WORKERS)
            == expected
        )


@pytest.mark.parametrize("config_value", ["not-a-number", "0", "-5"])
def test_invalid_parallel_workers_warns(config_value):
    with mock.patch(
        "codegraphcontext.cli.config_manager.get_config_value",
        return_value=config_value,
    ), mock.patch(
        "codegraphcontext.tools.indexing.pipeline.warning_logger"
    ) as warn:
        assert pipeline.get_parallel_workers() == pipeline.DEFAULT_PARALLEL_WORKERS
    warn.assert_called_once()
    assert config_value in warn.call_args.args[0]


def test_empty_parallel_workers_does_not_warn():
    with mock.patch(
        "codegraphcontext.cli.config_manager.get_config_value",
        return_value=None,
    ), mock.patch(
        "codegraphcontext.tools.indexing.pipeline.warning_logger"
    ) as warn:
        assert pipeline.get_parallel_workers() == pipeline.DEFAULT_PARALLEL_WORKERS
    warn.assert_not_called()


def test_parallel_workers_above_cap_warns_and_clamps():
    with mock.patch(
        "codegraphcontext.cli.config_manager.get_config_value",
        return_value="5000",
    ), mock.patch(
        "codegraphcontext.tools.indexing.pipeline.warning_logger"
    ) as warn:
        assert pipeline.get_parallel_workers() == pipeline.MAX_PARALLEL_WORKERS
    warn.assert_called_once()
