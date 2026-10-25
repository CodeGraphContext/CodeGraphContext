"""With scip-dotnet `(+N)` overloads recognised, one C# file holds two `M` function
nodes. scip-dotnet leaves `display_name` empty, so both SCIP nodes arrive with
`args == []`; the Tree-sitter call resolver then cannot tell the overloads apart
and resolves neither call, leaving only the SCIP file-level edges.

The SCIP side is faked with exactly what ScipIndexParser yields for this source
(scip-dotnet main); the Tree-sitter parser and the call resolver are the real ones.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.graph_builder import TreeSitterParser
from codegraphcontext.tools.indexing.scip_pipeline import run_scip_index_async

SOURCE = """namespace Kinds
{
    public class OverloadUser
    {
        public void M() { }
        public void M(int x) { }

        public void Caller()
        {
            M();
            M(1);
        }
    }
}
"""


class _FakeScipIndexer:
    def run(self, _project_path: Path, _lang: str, output_dir: Path) -> Path:
        scip_file = output_dir / "index.scip"
        scip_file.write_bytes(b"fake")
        return scip_file


class _FakeScipIndexParser:
    files_data: dict = {}

    def parse(self, _index_scip_path: Path, _project_path: Path) -> dict:
        return {"files": self.files_data}


def _scip_function(name: str, line: int) -> dict:
    return {"name": name, "line_number": line, "end_line": line, "docstring": None, "lang": "csharp",
            "is_dependency": False, "return_type": None, "args": [], "cyclomatic_complexity": 1,
            "decorators": [], "context": None, "class_context": None}


@pytest.mark.asyncio
async def test_calls_to_dotnet_overloads_resolve_to_the_matching_overload(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "Calls.cs"
    source.write_text(SOURCE, encoding="utf-8")
    path = str(source.resolve())
    _FakeScipIndexParser.files_data = {
        path: {"functions": [_scip_function("M", 5), _scip_function("M", 6), _scip_function("Caller", 8)],
               "classes": [{"name": "OverloadUser", "line_number": 3, "end_line": 3, "bases": [], "context": None}],
               "variables": [], "imports": [], "function_calls_scip": [], "module_level_calls_scip": [],
               "path": path, "lang": "csharp", "is_dependency": False},
    }
    writer = MagicMock()
    ts_parser = TreeSitterParser("c_sharp")

    await run_scip_index_async(
        repo, False, None, "csharp", writer, MagicMock(), [".cs"],
        lambda ext: ts_parser if ext == ".cs" else None,
        SimpleNamespace(ScipIndexer=_FakeScipIndexer, ScipIndexParser=_FakeScipIndexParser),
    )

    fn_to_fn = writer.write_function_call_groups.call_args.args[0]
    assert sorted((c["caller_name"], c["line_number"], c["called_name"], c["called_line_number"]) for c in fn_to_fn) == [
        ("Caller", 10, "M", 5),
        ("Caller", 11, "M", 6),
    ]
