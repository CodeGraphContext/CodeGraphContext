"""Regression tests: one bad file must not abort an entire index run."""
import ast
import inspect
from pathlib import Path

import pytest

from codegraphcontext.tools.indexing import pipeline
from codegraphcontext.tools.indexing.persistence import writer as writer_mod


def _relative_to_calls(source: str):
    """Yield (lineno, guarded) for every `X.relative_to(Y)` call in *source*."""
    tree = ast.parse(source)

    guarded_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            handles_value_error = any(
                (isinstance(h.type, ast.Name) and h.type.id == "ValueError")
                or (
                    isinstance(h.type, ast.Tuple)
                    and any(isinstance(e, ast.Name) and e.id == "ValueError" for e in h.type.elts)
                )
                or h.type is None
                for h in node.handlers
            )
            if handles_value_error:
                for child in ast.walk(node):
                    guarded_lines.add(getattr(child, "lineno", None))

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "relative_to"
        ):
            yield node.lineno, node.lineno in guarded_lines


def test_every_relative_to_in_the_writer_is_guarded():
    """`_normalize_path` calls `.resolve()`, which follows symlinks, so any
    symlink inside a repo pointing outside it makes `relative_to` raise.

    One call was bare while the one 17 lines above it and its sibling in
    `add_minimal_file_node` were both wrapped. The ValueError unwound out of
    the whole indexing run: every file after the symlink was silently never
    indexed, a partial File node was left outside the repo prefix (where
    `delete_repository_from_graph` cannot reach it), and the CLI exited 0.
    """
    unguarded = [
        line for line, guarded in _relative_to_calls(inspect.getsource(writer_mod))
        if not guarded
    ]
    assert not unguarded, (
        "unguarded Path.relative_to in writer.py at line(s) "
        f"{unguarded} — a symlinked file will abort the whole index run"
    )


def test_pipeline_write_loop_catches_per_file_failures():
    """Defence in depth: there is no transaction around the write loop, so an
    exception escaping it leaves a partially written graph with no rollback."""
    source = inspect.getsource(pipeline.run_tree_sitter_index_async)

    assert "write_failures" in source, "per-file write failures must be collected"
    # The add_file_to_graph / add_minimal_file_node dispatch must sit inside a try.
    tree = ast.parse(source.lstrip())
    protected = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for child in ast.walk(node):
                protected.add(getattr(child, "lineno", None))

    calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in {"add_minimal_file_node"}
    ]
    assert calls, "expected the minimal-file-node call to be present"
    assert all(line in protected for line in calls), (
        "the per-file graph writes must be wrapped so one failure cannot "
        "abort the remaining files"
    )


def test_relative_to_raises_for_a_path_outside_the_root():
    """Documents the exact failure the guard exists for."""
    with pytest.raises(ValueError):
        Path("/tmp/outside/target.py").relative_to(Path("/tmp/repo"))
