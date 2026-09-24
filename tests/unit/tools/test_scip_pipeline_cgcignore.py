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


def _file_entry(path: Path) -> dict:
    return {
        "path": str(path),
        "functions": [],
        "classes": [],
        "imports": [],
        "function_calls_scip": [],
        "module_level_calls_scip": [],
    }


@pytest.mark.asyncio
async def test_scip_pipeline_skips_documents_outside_project_root(tmp_path: Path):
    """SCIP indexes (e.g. scip-go with cgo) can reference files outside the
    project root, such as Go build cache artifacts. These must be filtered
    out instead of crashing the ingest with ValueError in relative_to()."""
    repo = tmp_path / "repo"
    src_dir = repo / "src"
    src_dir.mkdir(parents=True)

    tracked_file = src_dir / "app.py"
    tracked_file.write_text("print('tracked')\n", encoding="utf-8")

    # Simulates a cgo artifact in the Go build cache, outside the repo.
    build_cache_dir = tmp_path / "go-build" / "6a"
    build_cache_dir.mkdir(parents=True)
    out_of_root_file = build_cache_dir / "6a390ec986-d"
    out_of_root_file.write_text("// cgo generated\n", encoding="utf-8")

    fake_parser_mod = SimpleNamespace(
        ScipIndexer=_FakeScipIndexer,
        ScipIndexParser=_FakeScipIndexParser,
    )
    _FakeScipIndexParser.files_data = {
        str(tracked_file.resolve()): _file_entry(tracked_file.resolve()),
        str(out_of_root_file.resolve()): _file_entry(out_of_root_file.resolve()),
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
    assert str(out_of_root_file.resolve()) not in indexed_paths


@pytest.mark.asyncio
async def test_scip_pipeline_skips_out_of_root_documents_without_ignore_spec(tmp_path: Path):
    """The out-of-root filter must apply even when no ignore spec could be
    built (build_ignore_spec failed with OSError)."""
    repo = tmp_path / "repo"
    src_dir = repo / "src"
    src_dir.mkdir(parents=True)

    tracked_file = src_dir / "app.py"
    tracked_file.write_text("print('tracked')\n", encoding="utf-8")

    build_cache_dir = tmp_path / "go-build" / "5c"
    build_cache_dir.mkdir(parents=True)
    out_of_root_file = build_cache_dir / "5c1f2e3d4b-d"
    out_of_root_file.write_text("// cgo generated\n", encoding="utf-8")

    fake_parser_mod = SimpleNamespace(
        ScipIndexer=_FakeScipIndexer,
        ScipIndexParser=_FakeScipIndexParser,
    )
    _FakeScipIndexParser.files_data = {
        str(tracked_file.resolve()): _file_entry(tracked_file.resolve()),
        str(out_of_root_file.resolve()): _file_entry(out_of_root_file.resolve()),
    }

    writer = MagicMock()
    job_manager = MagicMock()

    with patch(
        "codegraphcontext.tools.indexing.scip_pipeline.pre_scan_for_imports",
        return_value={},
    ), patch(
        "codegraphcontext.tools.indexing.scip_pipeline.build_ignore_spec",
        side_effect=OSError("cannot create .cgcignore"),
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
    assert str(out_of_root_file.resolve()) not in indexed_paths
