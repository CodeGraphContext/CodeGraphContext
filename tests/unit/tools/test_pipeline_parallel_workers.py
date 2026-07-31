"""Tests that the PARALLEL_WORKERS config drives indexing concurrency (#1340)."""
from unittest import mock

import pytest

from codegraphcontext.tools.indexing import pipeline


@pytest.mark.parametrize(
    "config_value,expected",
    [
        ("32", 32),
        ("1", 1),
        ("4", 4),
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
