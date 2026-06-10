"""Tests for .cgcignore handling in the SCIP indexing pipeline."""

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
            "functions": [],
            "classes": [],
            "imports": [],
            "variables": [],
            "function_calls_scip": [],
            "module_level_calls_scip": [],
        }


@pytest.mark.asyncio
async def test_scip_pipeline_respects_root_directory_cgcignore_pattern(tmp_path: Path):
    repo = tmp_path / "repo"
    src_dir = repo / "src"
    ignored_dir = repo / "Binaries"
    src_dir.mkdir(parents=True)
    ignored_dir.mkdir()

    tracked_file = src_dir / "app.py"
    ignored_file = ignored_dir / "generated.py"
    tracked_file.write_text("print('tracked')\n", encoding="utf-8")
    ignored_file.write_text("print('ignored')\n", encoding="utf-8")
    (repo / ".cgcignore").write_text("Binaries/\n", encoding="utf-8")

    fake_parser_mod = SimpleNamespace(
        ScipIndexer=_FakeScipIndexer,
        ScipIndexParser=_FakeScipIndexParser,
    )
    _FakeScipIndexParser.files_data = {
        str(tracked_file.resolve()): {
            "path": str(tracked_file.resolve()),
            "functions": [],
            "classes": [],
            "imports": [],
            "function_calls_scip": [],
            "module_level_calls_scip": [],
        },
        str(ignored_file.resolve()): {
            "path": str(ignored_file.resolve()),
            "functions": [],
            "classes": [],
            "imports": [],
            "function_calls_scip": [],
            "module_level_calls_scip": [],
        },
    }

    writer = MagicMock()
    job_manager = MagicMock()

    with patch(
        "codegraphcontext.tools.indexing.scip_pipeline.pre_scan_for_imports",
        return_value={},
    ):
        await run_scip_index_async(
            repo,
            is_dependency=False,
            job_id=None,
            lang="python",
            writer=writer,
            job_manager=job_manager,
            parsers_keys={".py"},
            get_parser=lambda _suffix: _FakeParser(),
            scip_indexer_mod=fake_parser_mod,
        )

    indexed_paths = [
        call.args[0]["path"]
        for call in writer.add_file_to_graph.call_args_list
    ]
    assert str(tracked_file.resolve()) in indexed_paths
    assert str(ignored_file.resolve()) not in indexed_paths
