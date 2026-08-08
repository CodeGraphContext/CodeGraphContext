"""Tests for SCIP pipeline post-processing (CALLS resolution pass)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from codegraphcontext.tools.indexing.scip_pipeline import run_scip_index_async


class _FakeScipIndexer:
    def run(self, _project_path: Path, _lang: str, output_dir: Path) -> Path:
        scip_file = output_dir / "index.scip"
        scip_file.write_bytes(b"fake")
        return scip_file


class _FakeScipIndexParser:
    files_data: dict[str, dict]

    def parse(self, _index_scip_path: Path, _project_path: Path) -> dict:
        return {"files": self.files_data}


class _FakeParser:
    def parse(self, path: Path, _is_dependency: bool, index_source: bool = False) -> dict:
        return {
            "path": str(path),
            "functions": [{"name": "main", "line_number": 1}],
            "classes": [],
            "imports": [],
            "variables": [],
            "function_calls": [
                {
                    "caller_name": "main",
                    "caller_line_number": 1,
                    "called_name": "helper",
                    "line_number": 2,
                    "full_name": "helper",
                    "args": [],
                }
            ],
            "function_calls_scip": [],
            "module_level_calls_scip": [],
        }


@pytest.mark.asyncio
async def test_scip_pipeline_runs_build_function_call_groups(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked_file = repo / "app.py"
    tracked_file.write_text("def main():\n    helper()\n", encoding="utf-8")

    fake_parser_mod = SimpleNamespace(
        ScipIndexer=_FakeScipIndexer,
        ScipIndexParser=_FakeScipIndexParser,
    )
    _FakeScipIndexParser.files_data = {
        str(tracked_file.resolve()): {
            "path": str(tracked_file.resolve()),
            "functions": [{"name": "main", "line_number": 1}],
            "classes": [],
            "imports": [],
            "function_calls_scip": [],
            "module_level_calls_scip": [],
        },
    }

    writer = MagicMock()
    job_manager = MagicMock()
    fake_groups = ([{"caller_name": "main"}], [], [], [], [], [], [], [], [], [])

    with patch(
        "codegraphcontext.tools.indexing.scip_pipeline.pre_scan_for_imports",
        return_value={},
    ), patch(
        "codegraphcontext.tools.indexing.scip_pipeline.build_function_call_groups",
        return_value=fake_groups,
    ) as mock_build_calls:
        await run_scip_index_async(
            repo,
            is_dependency=False,
            job_id="job-1",
            lang="python",
            writer=writer,
            job_manager=job_manager,
            parsers_keys={".py"},
            get_parser=lambda _suffix: _FakeParser(),
            scip_indexer_mod=fake_parser_mod,
        )

    mock_build_calls.assert_called_once()
    all_file_data, imports_map, file_class_lookup = mock_build_calls.call_args[0]
    assert file_class_lookup is None
    assert imports_map == {}
    assert len(all_file_data) == 1
    assert all_file_data[0].get("function_calls")

    writer.write_function_call_groups.assert_called_once_with(*fake_groups)
    writer.write_scip_call_edges.assert_called_once()
    job_manager.update_job.assert_any_call(
        "job-1", status_message="Resolving function CALLS edges..."
    )
