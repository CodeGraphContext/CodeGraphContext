"""Tests for issue #946: cgc analyze complexity <file_path> support."""

import os
import sys
import types
from unittest.mock import MagicMock, patch, call

import pytest
from typer.testing import CliRunner

import codegraphcontext.cli.main as cli_main
from codegraphcontext.cli.main import app

runner = CliRunner()

class _FakeDBManager:
    def get_driver(self):
        return MagicMock()

    def close_driver(self):
        pass


class _FakeGraphBuilder:
    pass


class _FakeCodeFinder:
    """Tracks which methods are called so we can assert routing."""

    def __init__(self):
        self.calls = []

    def get_cyclomatic_complexity(self, *args, **kwargs):
        self.calls.append(("get_cyclomatic_complexity", args, kwargs))
        return {"complexity": 5, "path": "repo/utils.py", "line_number": 10}

    def find_most_complex_functions(self, *args, **kwargs):
        self.calls.append(("find_most_complex_functions", args, kwargs))
        return [{"function_name": "big_func", "complexity": 15, "path": "repo/main.py", "line_number": 1}]

    def find_most_complex_functions_in_file(self, *args, **kwargs):
        self.calls.append(("find_most_complex_functions_in_file", args, kwargs))
        return [{"function_name": "handler", "complexity": 8, "path": "repo/main.py", "line_number": 42}]


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    """Set up minimal CLI stubs for complexity command testing."""
    monkeypatch.setattr(cli_main.config_manager, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cli_main.config_manager, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(cli_main, "_load_credentials", lambda *a, **kw: None)

    code_finder = _FakeCodeFinder()
    monkeypatch.setattr(
        cli_main,
        "_initialize_services",
        lambda *a, **kw: (_FakeDBManager(), _FakeGraphBuilder(), code_finder, MagicMock()),
    )
    return code_finder

class TestIsFilePathDetection:
    """Verify that the file-path heuristic correctly distinguishes
    file paths from function names."""

    def _is_file_path(self, value: str) -> bool:
        """Mirror the logic in analyze_complexity."""
        _FILE_EXTENSIONS = (
            '.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.rb',
            '.java', '.cpp', '.c', '.cs', '.swift', '.kt', '.scala',
            '.php', '.lua', '.zig', '.ex', '.exs', '.r', '.m', '.sh',
        )
        if '/' in value or '\\' in value:
            return True
        return any(value.endswith(ext) for ext in _FILE_EXTENSIONS)

    # Paths with separators
    def test_path_with_slash(self):
        assert self._is_file_path("src/main.py") is True

    def test_path_with_backslash(self):
        assert self._is_file_path("src\\main.py") is True

    def test_deep_path(self):
        assert self._is_file_path("src/codegraphcontext/tools/code_finder.py") is True

    # Bare filenames with extensions
    def test_bare_python_file(self):
        assert self._is_file_path("main.py") is True

    def test_bare_js_file(self):
        assert self._is_file_path("index.js") is True

    def test_bare_go_file(self):
        assert self._is_file_path("server.go") is True

    def test_bare_ts_file(self):
        assert self._is_file_path("app.ts") is True

    def test_bare_rust_file(self):
        assert self._is_file_path("lib.rs") is True

    #  Function names (should NOT be treated as file paths) 
    def test_simple_function_name(self):
        assert self._is_file_path("my_function") is False

    def test_class_method_name(self):
        assert self._is_file_path("process_data") is False

    def test_snake_case_function(self):
        assert self._is_file_path("calculate_total") is False

    def test_camel_case_function(self):
        assert self._is_file_path("processData") is False


# CLI routing tests

class TestComplexityCommandRouting:
    """Verify that the CLI routes to the correct CodeFinder method
    based on the positional argument."""

    def test_no_args_calls_global(self, cli_env):
        """cgc analyze complexity → find_most_complex_functions"""
        result = runner.invoke(app, ["analyze", "complexity"])
        assert result.exit_code == 0, result.output
        assert cli_env.calls[0][0] == "find_most_complex_functions"

    def test_function_name_calls_get_complexity(self, cli_env):
        """cgc analyze complexity my_function → get_cyclomatic_complexity"""
        result = runner.invoke(app, ["analyze", "complexity", "my_function"])
        assert result.exit_code == 0, result.output
        assert cli_env.calls[0][0] == "get_cyclomatic_complexity"

    def test_file_path_with_slash_calls_file_method(self, cli_env):
        """cgc analyze complexity src/main.py → find_most_complex_functions_in_file"""
        result = runner.invoke(app, ["analyze", "complexity", "src/main.py"])
        assert result.exit_code == 0, result.output
        assert cli_env.calls[0][0] == "find_most_complex_functions_in_file"

    def test_bare_filename_calls_file_method(self, cli_env):
        """cgc analyze complexity main.py → find_most_complex_functions_in_file"""
        result = runner.invoke(app, ["analyze", "complexity", "main.py"])
        assert result.exit_code == 0, result.output
        assert cli_env.calls[0][0] == "find_most_complex_functions_in_file"

    def test_file_option_without_positional_calls_file_method(self, cli_env):
        """cgc analyze complexity --file src/main.py → find_most_complex_functions_in_file"""
        result = runner.invoke(app, ["analyze", "complexity", "--file", "src/main.py"])
        assert result.exit_code == 0, result.output
        assert cli_env.calls[0][0] == "find_most_complex_functions_in_file"

    def test_function_name_with_file_option_calls_get_complexity(self, cli_env):
        """cgc analyze complexity my_func -f main.py → get_cyclomatic_complexity"""
        result = runner.invoke(app, ["analyze", "complexity", "my_func", "-f", "main.py"])
        assert result.exit_code == 0, result.output
        assert cli_env.calls[0][0] == "get_cyclomatic_complexity"


# Output content tests

class TestComplexityCommandOutput:
    """Verify that the CLI output contains expected content."""

    def test_file_path_shows_table_with_file_title(self, cli_env):
        result = runner.invoke(app, ["analyze", "complexity", "src/main.py"])
        assert result.exit_code == 0
        assert "src/main.py" in result.output
        assert "handler" in result.output

    def test_global_shows_threshold_info(self, cli_env):
        result = runner.invoke(app, ["analyze", "complexity"])
        assert result.exit_code == 0
        assert "threshold" in result.output.lower()

    def test_function_name_shows_single_result(self, cli_env):
        result = runner.invoke(app, ["analyze", "complexity", "my_func"])
        assert result.exit_code == 0
        assert "Complexity for" in result.output

    def test_empty_file_results_shows_message(self, cli_env):
        """When no functions found in file, show appropriate message."""
        cli_env.find_most_complex_functions_in_file = lambda *a, **kw: (
            cli_env.calls.append(("find_most_complex_functions_in_file", a, kw)) or []
        )
        result = runner.invoke(app, ["analyze", "complexity", "empty.py"])
        assert result.exit_code == 0
        assert "No complexity data" in result.output
