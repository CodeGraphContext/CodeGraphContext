"""Regression tests: one bad file must not abort an entire index run."""
import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing import pipeline
from codegraphcontext.tools.indexing.persistence import writer as writer_mod
from codegraphcontext.core.jobs import JobManager, JobStatus


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


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_write", ["file", "minimal"])
async def test_pipeline_write_loop_catches_per_file_failures(tmp_path, monkeypatch, failed_write):
    """Defence in depth: there is no transaction around the write loop, so an
    exception escaping it leaves a partially written graph with no rollback."""
    first, second = tmp_path / "a.py", tmp_path / "b.py"
    first.write_text("pass\n")
    second.write_text("pass\n")
    monkeypatch.setattr(pipeline, "discover_files_to_index", lambda *args, **kwargs: ([first, second], tmp_path))
    monkeypatch.setattr(pipeline, "pre_scan_for_imports", lambda *args: {})
    monkeypatch.setattr("codegraphcontext.cli.config_manager.get_config_value", lambda key: "false")
    writer = MagicMock()
    writer.repair_missing_contains_links.return_value = 0
    successful_writes = []

    def write_file(data, *args, **kwargs):
        if data["path"] == str(first):
            raise OSError("first file is unwritable")
        successful_writes.append(data["path"])

    writer.add_file_to_graph.side_effect = write_file
    writer.add_minimal_file_node.side_effect = OSError("minimal node is unwritable")

    def parse_file(repo, file, dependency):
        data = {"path": str(file), "functions": [], "classes": []}
        if file == first and failed_write == "minimal":
            data["error"] = "parse failed"
        return data

    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    summary = {}
    await pipeline.run_tree_sitter_index_async(
        tmp_path, True, job_id, None, writer, jobs, {".py": "python"},
        lambda suffix: None, parse_file, writer.add_minimal_file_node,
        index_summary=summary,
    )
    assert successful_writes == [str(second)], "a failed write must not drop subsequent files"
    assert summary["failed_files"] == 1
    assert summary["failed_file_details"][0]["path"] == str(first)
    assert jobs.get_job(job_id).status == JobStatus.COMPLETED
    if failed_write == "file":
        assert writer.add_file_to_graph.call_count == 3  # first attempt, retry, then second file
        writer.add_minimal_file_node.assert_not_called()
    else:
        writer.add_minimal_file_node.assert_called_once()
        writer.add_file_to_graph.assert_called_once()


def test_relative_to_raises_for_a_path_outside_the_root():
    """Documents the exact failure the guard exists for."""
    with pytest.raises(ValueError):
        Path("/tmp/outside/target.py").relative_to(Path("/tmp/repo"))
