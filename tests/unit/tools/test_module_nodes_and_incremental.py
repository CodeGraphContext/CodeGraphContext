"""Regression tests for <module> pseudo-nodes, incremental CALLS and Kùzu schema."""
import inspect
from pathlib import Path

from codegraphcontext.core import watcher as watcher_mod
from codegraphcontext.tools import code_finder as code_finder_mod
from codegraphcontext.tools.indexing import schema as schema_mod
from codegraphcontext.tools.indexing.pipeline import build_index_summary


def test_dead_code_excludes_the_module_pseudo_node():
    """`<module>` is the synthetic frame module-level calls are attributed to,
    not a function anyone wrote. It was the *first row* of `cgc analyze
    dead-code`, i.e. the report's headline entry was an artifact."""
    source = inspect.getsource(code_finder_mod.CodeFinder.find_dead_code)
    assert "func.name <> '<module>'" in source


def test_index_summary_excludes_synthetic_module_frames():
    """One `<module>` node is created per Python file, so every reported
    function total was inflated by one per file."""
    all_file_data = [
        {
            "path": "/repo/a.py",
            "functions": [
                {"name": "real_one"},
                {"name": "<module>", "is_synthetic": True},
            ],
        },
        {
            "path": "/repo/b.py",
            "functions": [{"name": "<module>", "is_synthetic": True}],
        },
    ]

    summary = build_index_summary(
        files=[Path("/repo/a.py"), Path("/repo/b.py")],
        parsers={".py": "python"},
        all_file_data=all_file_data,
        resolved_call_groups=(),
        serialization_seconds=0.0,
    )

    assert summary["function_nodes"] == 1


def test_index_summary_excludes_module_frames_without_the_marker():
    """Graphs indexed before `is_synthetic` existed must still be counted
    correctly, so the name check is a fallback."""
    all_file_data = [
        {"path": "/repo/a.py", "functions": [{"name": "real"}, {"name": "<module>"}]}
    ]

    summary = build_index_summary(
        files=[Path("/repo/a.py")],
        parsers={".py": "python"},
        all_file_data=all_file_data,
        resolved_call_groups=(),
        serialization_seconds=0.0,
    )

    assert summary["function_nodes"] == 1


def test_python_parser_marks_the_module_frame_as_synthetic():
    from codegraphcontext.tools.languages import python as python_lang

    source = inspect.getsource(python_lang)
    assert '"is_synthetic": True' in source


def test_incremental_update_clears_calls_for_every_reparsed_file():
    """All of affected_paths get re-parsed and fed back to link_function_calls,
    but only caller_paths had their outgoing CALLS cleared. On Neo4j/Nornic the
    writer uses CREATE, not MERGE, so the inheritance-only neighbours
    accumulated duplicate CALLS on every save."""
    source = inspect.getsource(watcher_mod)
    assert "affected_paths - {changed_path_str}" in source, (
        "outgoing CALLS must be cleared for every re-parsed file, not just callers"
    )


def test_kuzu_declares_the_heuristic_calls_table():
    """writer.py emits HEURISTIC_CALLS for resolution tier >= 8, but the table
    was never declared in the Kùzu schema — so those edges could not be written
    and any query matching [:CALLS|HEURISTIC_CALLS] failed with
    'Binder exception: Table HEURISTIC_CALLS does not exist'. That broke
    `cgc analyze dead-code` completely on KùzuDB, which is the Windows default
    and the universal fallback backend."""
    from codegraphcontext.core import database_embedded_kuzu as kuzu_mod

    source = inspect.getsource(kuzu_mod)
    assert '("HEURISTIC_CALLS", """' in source


def test_schema_comment_does_not_claim_indexes_enforce_uniqueness():
    """Indexes do not enforce uniqueness; `CALL db.constraints()` returns [] on
    FalkorDB. The old comment claimed the indexes were 'sufficient for MERGE to
    perform correct deduplication'."""
    source = inspect.getsource(schema_mod)
    assert "sufficient for MERGE to perform correct deduplication" not in source
    assert "NO uniqueness constraints" in source
