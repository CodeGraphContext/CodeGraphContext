from pathlib import Path

import codegraphcontext.tools.languages.typescript as ts_lang_module
import codegraphcontext.tools.languages.typescriptjsx as tsx_lang_module

from codegraphcontext.tools.indexing import pre_scan as pre_scan_module
from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports


def test_graph_builder_registry_lists_typescript_module_extensions():
    graph_builder_source = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "codegraphcontext"
        / "tools"
        / "graph_builder.py"
    )
    source_text = graph_builder_source.read_text(encoding="utf-8")

    assert '".ts": "typescript"' in source_text
    assert '".tsx": "tsx"' in source_text
    assert '".d.ts": "typescript"' in source_text
    assert '".mts": "typescript"' in source_text
    assert '".cts": "typescript"' in source_text


def test_pre_scan_dispatches_typescript_module_extensions(monkeypatch):
    calls = []

    def fake_pre_scan_typescript(files, parser):
        calls.append((tuple(".d.ts" if path.name.endswith(".d.ts") else path.suffix for path in files), parser))
        return {}

    monkeypatch.setattr(pre_scan_module, "_PRESCAN_REGISTRY", None)
    monkeypatch.setattr(ts_lang_module, "pre_scan_typescript", fake_pre_scan_typescript)
    monkeypatch.setattr(tsx_lang_module, "pre_scan_typescript", fake_pre_scan_typescript)

    files = [
        Path("/tmp/example.ts"),
        Path("/tmp/example.tsx"),
        Path("/tmp/example.d.ts"),
        Path("/tmp/example.mts"),
        Path("/tmp/example.cts"),
        Path("/tmp/example.py"),
    ]

    pre_scan_for_imports(
        files,
        {".ts", ".tsx", ".d.ts", ".mts", ".cts"},
        lambda ext: f"parser:{ext}",
    )

    assert [suffixes for suffixes, _ in calls] == [
        (".ts",),
        (".tsx",),
        (".d.ts",),
        (".mts",),
        (".cts",),
    ]
    assert [parser for _, parser in calls] == [
        "parser:.ts",
        "parser:.tsx",
        "parser:.d.ts",
        "parser:.mts",
        "parser:.cts",
    ]