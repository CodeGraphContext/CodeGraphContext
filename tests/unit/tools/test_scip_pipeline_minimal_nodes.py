"""Non-code files must reach the graph on the SCIP path too.

`discover_files_to_index` returns supported extensions *plus* a generic set
(`.md`, `.json`, `.yaml`, `Dockerfile`, `.gitignore`, …). The Tree-sitter
pipeline gives those a minimal `File` node so the graph accounts for every
discovered file; the SCIP pipeline used to skip them outright.

`cgc index` compares the graph's File count against the discovery count, so
the shortfall made it report "Repository '.' has only N of M files indexed.
Continuing." on every run — a state no amount of re-indexing could clear.
"""

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
    files_data: dict[str, dict] = {}

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


async def _run(repo: Path, writer: MagicMock, supported: set[str]) -> None:
    fake_mod = SimpleNamespace(
        ScipIndexer=_FakeScipIndexer,
        ScipIndexParser=_FakeScipIndexParser,
    )
    _FakeScipIndexParser.files_data = {}

    with patch(
        "codegraphcontext.tools.indexing.scip_pipeline.pre_scan_for_imports",
        return_value={},
    ):
        await run_scip_index_async(
            repo,
            is_dependency=False,
            job_id=None,
            lang="c_sharp",
            writer=writer,
            job_manager=MagicMock(),
            parsers_keys=supported,
            get_parser=lambda suffix: _FakeParser() if suffix in supported else None,
            scip_indexer_mod=fake_mod,
        )


@pytest.mark.asyncio
async def test_generic_files_get_minimal_nodes(tmp_path: Path):
    """A C#-plus-config project must account for every discovered file."""
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "Program.cs").write_text("public class P {}\n", encoding="utf-8")
    generic = ["README.md", "appsettings.json", "Dockerfile", ".gitignore", "build.sh"]
    for name in generic:
        (repo / name).write_text("x\n", encoding="utf-8")

    writer = MagicMock()
    await _run(repo, writer, supported={".cs"})

    parsed = {
        Path(call.args[0]["path"]).name
        for call in writer.add_file_to_graph.call_args_list
    }
    minimal = {
        Path(call.args[0]).name
        for call in writer.add_minimal_file_node.call_args_list
    }

    assert "Program.cs" in parsed
    # Every non-code file is still represented, so the graph File count can
    # reach the number of files discovered on disk.
    assert set(generic) <= minimal, f"missing minimal nodes for {set(generic) - minimal}"


@pytest.mark.asyncio
async def test_graph_file_count_matches_discovery(tmp_path: Path):
    """The count `cgc index` checks against must be reachable.

    Reproduces the reported shape: 32 source files, 14 non-code files, and a
    'only 32 of 46' warning that never cleared.
    """
    from codegraphcontext.tools.indexing.discovery import discover_files_to_index

    repo = tmp_path / "proj"
    repo.mkdir()
    for i in range(32):
        (repo / f"Class{i}.cs").write_text("public class A {}\n", encoding="utf-8")
    for name in [
        "README.md", "LICENSE.txt", "appsettings.json", "Dockerfile", ".gitignore",
        "build.sh", "config.yaml", "pyproject.toml", "setup.cfg", "notes.txt",
        "deploy.ps1", "run.bat", "docker-compose.yml", "values.yaml",
    ]:
        (repo / name).write_text("x\n", encoding="utf-8")

    discovered, _ = discover_files_to_index(repo, supported_extensions={".cs"})
    assert len(discovered) == 46

    writer = MagicMock()
    await _run(repo, writer, supported={".cs"})

    written = (
        writer.add_file_to_graph.call_count + writer.add_minimal_file_node.call_count
    )
    assert written == len(discovered), (
        f"graph would hold {written} File nodes but discovery expects "
        f"{len(discovered)} — `cgc index` will warn on every run"
    )
