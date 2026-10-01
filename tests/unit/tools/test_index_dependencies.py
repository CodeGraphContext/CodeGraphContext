"""Test index_dependencies feature for add_code_to_graph."""
import ast
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from codegraphcontext.tools.handlers.indexing_handlers import (
    _collect_python_imports,
    _filter_and_resolve_dependencies,
    add_code_to_graph,
)
from codegraphcontext.tool_definitions import TOOLS


class TestIndexDependenciesToolSchema:
    """Verify the tool schema exposes index_dependencies."""

    def test_schema_has_index_dependencies(self):
        props = TOOLS["add_code_to_graph"]["inputSchema"]["properties"]
        assert "index_dependencies" in props
        assert props["index_dependencies"]["type"] == "boolean"
        assert props["index_dependencies"]["default"] is False


class TestCollectPythonImports:
    """Tests for _collect_python_imports."""

    def test_collects_top_level_imports(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("import math\nimport os\nfrom collections import defaultdict\nfrom typing import List\n")
        result = _collect_python_imports(tmp_path)
        assert "math" in result
        assert "os" in result
        assert "collections" in result
        assert "typing" in result

    def test_filters_local_modules(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("import math\nimport module_b\nfrom module_a import foo\n")
        result = _collect_python_imports(tmp_path)
        assert "math" in result
        assert "module_b" in result
        assert "module_a" in result

    def test_handles_syntax_errors(self, tmp_path: Path):
        """Syntax errors in files should be skipped gracefully."""
        test_file = tmp_path / "bad.py"
        test_file.write_text("import math\nsyntax error here\n")
        result = _collect_python_imports(tmp_path)
        assert isinstance(result, set)


class TestFilterAndResolveDependencies:
    """Tests for _filter_and_resolve_dependencies."""

    def test_filters_stdlib(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("import math\nimport os\n")
        import_names = {"math", "os"}
        result = _filter_and_resolve_dependencies(import_names, tmp_path)
        assert len(result) == 0

    def test_filters_local_modules(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("import mymodule\n")
        import_names = {"mymodule"}
        result = _filter_and_resolve_dependencies(import_names, tmp_path)
        assert len(result) == 0

    def test_resolves_external_packages(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("import requests\nimport math\n")
        import_names = {"requests", "math"}
        result = _filter_and_resolve_dependencies(import_names, tmp_path)
        assert len(result) == 1
        assert result[0]["package_name"] == "requests"


class TestAddCodeToGraphIndexDependencies:
    """Tests for add_code_to_graph with index_dependencies."""

    def test_index_dependencies_false_returns_no_dependency_jobs(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        gb = MagicMock()
        gb.db_manager.get_backend_type.return_value = "kuzudb"
        gb.estimate_processing_time.return_value = (3, 1.0)
        gb.build_graph_from_path_async.return_value = MagicMock()
        job_manager = MagicMock()
        job_manager.create_job.return_value = "job-1"

        with patch("codegraphcontext.tools.handlers.indexing_handlers.asyncio"):
            result = add_code_to_graph(
                gb, job_manager, MagicMock(), lambda: {"repositories": []},
                path=str(tmp_path), index_dependencies=False,
            )

        assert result.get("success") is True
        assert "dependency_job_ids" not in result

    def test_index_dependencies_true_queues_dependency_jobs(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        gb = MagicMock()
        gb.db_manager.get_backend_type.return_value = "kuzudb"
        gb.estimate_processing_time.return_value = (3, 1.0)
        gb.build_graph_from_path_async.return_value = MagicMock()
        job_manager = MagicMock()
        job_manager.create_job.return_value = "dep-job-1"

        with patch("codegraphcontext.tools.handlers.indexing_handlers.asyncio"), \
             patch("codegraphcontext.tools.handlers.indexing_handlers._collect_python_imports", return_value={"requests"}), \
             patch("codegraphcontext.tools.handlers.indexing_handlers._filter_and_resolve_dependencies", return_value=[{"package_name": "requests", "package_path": str(tmp_path / "requests"), "is_dependency": True}]):
            result = add_code_to_graph(
                gb, job_manager, MagicMock(), lambda: {"repositories": []},
                path=str(tmp_path), index_dependencies=True,
            )

        assert result.get("success") is True
        assert "dependency_job_ids" in result
        assert result["dependency_job_ids"] == ["dep-job-1"]
