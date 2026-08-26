"""#1510: resolved CALLS whose target scope lives in module_context must land.

The writer matched `called.context` only, but Rust functions carry their scope
exclusively in `module_context` — so correctly-resolved module-scoped Rust
calls were filtered out at write time (or binder-skipped the batch on Kùzu).
Verified against a real embedded database.
"""
from pathlib import Path

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.indexing.persistence.writer import (
    GraphWriter,
    _called_context_clause,
)

kuzu = pytest.importorskip("kuzu")


def test_clause_is_label_aware():
    fn = _called_context_clause("Function")
    assert "module_context" in fn and "class_context" in fn
    var = _called_context_clause("Variable")
    # Kùzu's Variable table has no class/module_context columns; referencing
    # them binder-errors the whole batch on typed backends.
    assert "module_context" not in var and "class_context" not in var
    assert "called.context" in var
    assert _called_context_clause("File") == ""


def test_module_context_scoped_call_lands_on_kuzu(tmp_path: Path):
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        w = GraphWriter(driver)
        repo = tmp_path / "repo"
        repo.mkdir()
        f = repo / "lib.rs"
        f.write_text("mod utils { pub fn helper() {} }\n", encoding="utf-8")
        w.add_repository_to_graph(repo)
        # A Rust-style function: scope in module_context, NO context key.
        w.add_file_to_graph(
            {
                "path": str(f), "repo_path": str(repo), "lang": "rust",
                "imports": [],
                "functions": [
                    {"name": "helper", "line_number": 1, "end_line": 1,
                     "args": [], "module_context": "utils"},
                    {"name": "caller", "line_number": 2, "end_line": 3,
                     "args": [], "module_context": "crate"},
                ],
                "classes": [], "variables": [],
            },
            repo.name, {}, repo_path_str=str(repo.resolve()),
        )
        # A resolved call whose called_context is the module scope.
        w.write_function_call_groups(
            [
                {
                    "type": "function",
                    "caller_name": "caller",
                    "caller_file_path": str(f),
                    "caller_line_number": 2,
                    "called_name": "helper",
                    "called_file_path": str(f),
                    "called_line_number": 1,
                    "called_context": "utils",
                    "line_number": 2,
                    "full_call_name": "utils::helper",
                    "args": [],
                    "args_key": "",
                    "resolution_tier": 5,
                    "confidence": 0.9,
                    "confidence_label": "RESOLVED",
                }
            ],
        )
        with driver.session() as s:
            rows = s.run(
                "MATCH (a:Function {name:'caller'})-[r:CALLS]->(b:Function {name:'helper'}) "
                "RETURN count(r) AS c"
            ).data()
        assert rows[0]["c"] == 1, "module_context-scoped CALLS edge was dropped"
    finally:
        manager.close_driver()
