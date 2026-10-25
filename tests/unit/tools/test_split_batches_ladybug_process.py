"""Exercise Ladybug's conservative writer path outside the Kuzu process."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_ladybug_keeps_combined_parameter_import_and_inheritance_queries():
    source = Path(__file__).with_name("test_split_node_rel_batches.py")
    env = {**os.environ, "CGC_SPLIT_TEST_BACKEND": "ladybugdb"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(source), "-q"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    if "3 skipped" in result.stdout:
        pytest.skip("Ladybug native engine is unavailable in the subprocess")
    assert "3 passed" in result.stdout, output
