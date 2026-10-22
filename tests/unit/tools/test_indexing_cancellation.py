"""Cancellation must keep indexing resources active until their workers finish."""

import asyncio
from datetime import datetime, timedelta
import subprocess
import sys
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.jobs import JobManager, JobStatus
from codegraphcontext.tools.indexing import pipeline, scip_pipeline


class BlockedWrite:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def __call__(self, *args, **kwargs):
        self.entered.set()
        try:
            assert self.release.wait(10), "test did not release its owned worker"
        finally:
            self.finished.set()


async def entered(block):
    async def wait():
        while not block.entered.is_set():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), 5)


def make_pipeline(
    tmp_path, monkeypatch, kind, writer, jobs, job_id, *, parse_file=None, scip_mod=None, get_parser=None
):
    source = tmp_path / "app.py"
    source.write_text("def main(): pass\n")
    monkeypatch.setattr("codegraphcontext.cli.config_manager.get_config_value", lambda key: "false")
    monkeypatch.setattr(pipeline, "pre_scan_for_imports", lambda *args: {})
    monkeypatch.setattr(scip_pipeline, "pre_scan_for_imports", lambda *args: {})
    writer.repair_missing_contains_links.return_value = 0
    if kind == "tree_sitter":
        return pipeline.run_tree_sitter_index_async(
            tmp_path,
            True,
            job_id,
            None,
            writer,
            jobs,
            {".py": "python"},
            get_parser or (lambda suffix: None),
            parse_file or (lambda *args: {"path": str(source), "functions": [], "classes": []}),
            writer.add_minimal_file_node,
        )

    class Indexer:
        def run(self, path, lang, output):
            result = output / "index.scip"
            result.write_bytes(b"test")
            return result

    class Parser:
        def parse(self, index, path):
            return {"files": {str(source): {"path": str(source), "functions": [], "classes": []}}}

    return scip_pipeline.run_scip_index_async(
        tmp_path,
        True,
        job_id,
        "python",
        writer,
        jobs,
        {".py"},
        get_parser or (lambda suffix: None),
        scip_mod or SimpleNamespace(ScipIndexer=Indexer, ScipIndexParser=Parser),
    )


def test_terminal_cancellation_cannot_be_overwritten():
    jobs = JobManager()
    job_id = jobs.create_job("/owned-test-repository")
    jobs.update_job(job_id, status=JobStatus.CANCELLED)
    jobs.update_job(job_id, status=JobStatus.COMPLETED, processed_files=99)
    assert jobs.get_job(job_id).status == JobStatus.CANCELLED
    assert jobs.get_job(job_id).processed_files == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["tree_sitter", "scip"])
async def test_request_at_final_completion_boundary_cannot_be_overwritten(tmp_path, monkeypatch, kind):
    class CancelAtCompletion(JobManager):
        def finish_job(self, job_id):
            assert self.get_job(job_id).status == JobStatus.RUNNING
            assert self.get_job(job_id).end_time is None
            assert self.cancel_job(job_id)
            return super().finish_job(job_id)

    jobs = CancelAtCompletion()
    job_id = jobs.create_job(str(tmp_path))
    writer = MagicMock()
    with pytest.raises(asyncio.CancelledError):
        await make_pipeline(tmp_path, monkeypatch, kind, writer, jobs, job_id)
    assert jobs.get_job(job_id).status == JobStatus.CANCELLED
    assert jobs.get_job(job_id).end_time is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["tree_sitter", "scip"])
async def test_failure_racing_cancellation_keeps_diagnostics_and_stops_write_retry(tmp_path, monkeypatch, kind):
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    writer = MagicMock()
    block = BlockedWrite()

    def write(*args, **kwargs):
        block()
        raise OSError("write failed during cancellation")

    writer.add_file_to_graph.side_effect = write
    task = asyncio.create_task(make_pipeline(tmp_path, monkeypatch, kind, writer, jobs, job_id))
    try:
        await entered(block)
        assert jobs.cancel_job(job_id)
    finally:
        block.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    job = jobs.get_job(job_id)
    assert job.status == JobStatus.CANCELLED
    assert job.error_type == "OSError"
    assert job.errors == ["write failed during cancellation"]
    writer.add_file_to_graph.assert_called_once()
    writer.add_minimal_file_node.assert_not_called()
    writer.write_function_call_groups.assert_not_called()


@pytest.mark.asyncio
async def test_scip_request_after_cold_parser_load_does_not_start_parse(tmp_path, monkeypatch):
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    writer = MagicMock()
    block = BlockedWrite()
    parser = MagicMock()

    def get_parser(suffix):
        block()
        return parser

    task = asyncio.create_task(
        make_pipeline(
            tmp_path,
            monkeypatch,
            "scip",
            writer,
            jobs,
            job_id,
            get_parser=get_parser,
        )
    )
    try:
        await entered(block)
        assert jobs.cancel_job(job_id)
    finally:
        block.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    parser.parse.assert_not_called()
    writer.add_file_to_graph.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["no_output", "runtime_error"])
async def test_cancelled_scip_does_not_fall_back_to_tree_sitter(tmp_path, monkeypatch, failure):
    from codegraphcontext.tools import graph_builder, scip_indexer

    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    block = BlockedWrite()

    class Indexer:
        def run(self, *args):
            block()
            if failure == "runtime_error":
                raise RuntimeError("SCIP process failed during cancellation")
            return None

    builder = graph_builder.GraphBuilder.__new__(graph_builder.GraphBuilder)
    builder.job_manager = jobs
    builder._writer = MagicMock()
    builder.parsers = {".py": "python"}
    builder.get_parser = MagicMock()
    builder.parse_file = MagicMock()
    builder.add_minimal_file_node = MagicMock()
    monkeypatch.setattr(graph_builder, "get_config_value", lambda key: "true" if key == "SCIP_INDEXER" else "python")
    monkeypatch.setattr(scip_indexer, "detect_project_lang", lambda *args: "python")
    monkeypatch.setattr(scip_indexer, "is_scip_available", lambda lang: True)
    monkeypatch.setattr(scip_indexer, "ScipIndexer", Indexer)
    task = asyncio.create_task(builder.build_graph_from_path_async(tmp_path, job_id=job_id))
    try:
        await entered(block)
        assert jobs.cancel_job(job_id)
    finally:
        block.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    builder.parse_file.assert_not_called()
    builder.get_parser.assert_not_called()
    builder._writer.add_repository_to_graph.assert_called_once()
    builder._writer.add_file_to_graph.assert_not_called()
    assert jobs.get_job(job_id).status == JobStatus.CANCELLED
    if failure == "runtime_error":
        assert jobs.get_job(job_id).errors == ["SCIP process failed during cancellation"]
    assert jobs.get_job(job_id).processed_files == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["tree_sitter", "scip"])
async def test_task_cancellation_waits_for_the_actual_blocking_worker(tmp_path, monkeypatch, kind):
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    writer = MagicMock()
    block = BlockedWrite()
    writer.add_repository_to_graph.side_effect = block
    task = asyncio.create_task(make_pipeline(tmp_path, monkeypatch, kind, writer, jobs, job_id))
    try:
        await entered(block)
        task.cancel()
        # The worker cannot finish until this test releases it. Returning a
        # cancelled task here falsely reports that its native resources drained.
        done, _ = await asyncio.wait({task}, timeout=0.05)
        assert not done, "indexing task finished while its worker still owned the database"
        assert not block.finished.is_set()
        assert jobs.get_job(job_id).status == JobStatus.RUNNING
        assert jobs.find_active_job_by_path(str(tmp_path)).job_id == job_id
        task.cancel()
        done, _ = await asyncio.wait({task}, timeout=0.01)
        assert not done, "a repeated cancellation must also wait for the owned worker"
    finally:
        block.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(block.finished.wait, 5)
    assert task.cancelled()
    assert jobs.get_job(job_id).status == JobStatus.CANCELLED
    writer.add_file_to_graph.assert_not_called()
    writer.write_function_call_groups.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["tree_sitter", "scip"])
async def test_pending_cancellation_never_admits_a_pipeline(tmp_path, monkeypatch, kind):
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    writer = MagicMock()
    assert jobs.cancel_job(job_id)
    with pytest.raises(asyncio.CancelledError):
        await make_pipeline(tmp_path, monkeypatch, kind, writer, jobs, job_id)
    writer.add_repository_to_graph.assert_not_called()
    assert jobs.get_job(job_id).status == JobStatus.CANCELLED


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["tree_sitter", "scip"])
async def test_request_keeps_cleanup_and_both_context_switch_guards_active(tmp_path, monkeypatch, kind):
    from codegraphcontext.server import MCPServer

    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    writer = MagicMock()
    block = BlockedWrite()
    writer.add_repository_to_graph.side_effect = block
    server = MCPServer.__new__(MCPServer)
    server.job_manager = jobs
    server._stop_current_watcher = MagicMock()
    server.db_manager = MagicMock()
    target = tmp_path / "other-context"
    (target / ".codegraphcontext").mkdir(parents=True)
    monkeypatch.setattr("codegraphcontext.utils.path_sandbox.is_path_allowed", lambda path: True)
    task = asyncio.create_task(make_pipeline(tmp_path, monkeypatch, kind, writer, jobs, job_id))
    try:
        await entered(block)
        assert jobs.cancel_job(job_id)
        assert jobs.cancel_job(job_id) is False
        job = jobs.get_job(job_id)
        job.start_time = datetime.now() - timedelta(hours=48)
        job.last_update_time = datetime.now() - timedelta(hours=30)
        jobs.cleanup_old_jobs()
        assert jobs.get_job(job_id) is job
        assert job.cancel_requested and job.status == JobStatus.RUNNING
        assert job.end_time is None
        from codegraphcontext.tools.handlers.management_handlers import check_job_status, list_jobs

        status = check_job_status(jobs, job_id=job_id)["job"]
        assert status["status"] == "running" and status["cancel_requested"] is True
        assert status["end_time"] is None
        assert list_jobs(jobs)["jobs"][0]["cancel_requested"] is True
        for destination in ("global", str(target)):
            result = server.switch_context_tool(context_path=destination, save=False)
            assert "still active" in result["error"]
            assert result["active_jobs"][0]["job_id"] == job_id
        server._stop_current_watcher.assert_not_called()
        server.db_manager.close.assert_not_called()
    finally:
        block.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    assert jobs.get_job(job_id).status == JobStatus.CANCELLED
    assert jobs.list_active_jobs() == []
    assert jobs.find_active_job_by_path(str(tmp_path)) is None
    assert server._active_jobs_block_context_switch() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["discovery", "prescan", "parse", "write", "inheritance", "calls", "embedding"])
async def test_tree_sitter_request_stops_later_phases(tmp_path, monkeypatch, stage):
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    writer = MagicMock()
    block = BlockedWrite()
    source = tmp_path / "app.py"

    def parsed(*args):
        block()
        return {"path": str(source), "functions": [], "classes": []}

    work = make_pipeline(
        tmp_path,
        monkeypatch,
        "tree_sitter",
        writer,
        jobs,
        job_id,
        parse_file=parsed if stage == "parse" else None,
    )
    if stage == "discovery":

        def discover(*args, **kwargs):
            block()
            return [source], tmp_path

        monkeypatch.setattr(pipeline, "discover_files_to_index", discover)
    elif stage == "prescan":

        def prescan(*args):
            block()
            return {}

        monkeypatch.setattr(pipeline, "pre_scan_for_imports", prescan)
    elif stage in ("write", "inheritance", "calls"):
        names = {
            "write": "add_file_to_graph",
            "inheritance": "write_inheritance_links",
            "calls": "write_function_call_groups",
        }
        getattr(writer, names[stage]).side_effect = block
    elif stage == "embedding":
        from codegraphcontext.tools.indexing import embeddings

        monkeypatch.setattr(
            "codegraphcontext.cli.config_manager.get_config_value",
            lambda key: "true" if key == "ENABLE_VECTOR_RESOLVE" else "false",
        )
        monkeypatch.setattr(embeddings, "probe_embedding_backend", lambda: (True, "test backend"))
        monkeypatch.setattr(embeddings.EmbeddingPipeline, "run", block)
    task = asyncio.create_task(work)
    try:
        await entered(block)
        assert jobs.cancel_job(job_id)
        assert not task.done()
    finally:
        block.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    assert jobs.get_job(job_id).status == JobStatus.CANCELLED
    if stage in ("discovery", "prescan", "parse"):
        writer.add_file_to_graph.assert_not_called()
    if stage in ("discovery", "prescan", "parse", "write", "inheritance"):
        writer.write_function_call_groups.assert_not_called()
    if stage != "embedding":
        writer.write_cpp_class_function_links.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
async def test_tree_sitter_drains_admitted_parses_without_starting_queued_files(tmp_path, monkeypatch, fails):
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    writer = MagicMock()
    block = BlockedWrite()
    second = tmp_path / "queued.py"
    second.write_text("pass\n")
    calls = []

    def parse(repo, file, dependency):
        calls.append(file)
        block()
        if fails:
            raise OSError("parse failed during cancellation")
        return {"path": str(file), "functions": [], "classes": []}

    work = make_pipeline(tmp_path, monkeypatch, "tree_sitter", writer, jobs, job_id, parse_file=parse)
    monkeypatch.setattr(pipeline, "get_parallel_workers", lambda: 1)
    monkeypatch.setattr(
        pipeline, "discover_files_to_index", lambda *args, **kwargs: ([tmp_path / "app.py", second], tmp_path)
    )
    task = asyncio.create_task(work)
    try:
        await entered(block)
        assert len(calls) == 1
        assert jobs.cancel_job(job_id)
    finally:
        block.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    assert len(calls) == 1
    writer.add_file_to_graph.assert_not_called()
    job = jobs.get_job(job_id)
    assert job.status == JobStatus.CANCELLED
    if fails:
        assert job.error_type == "OSError"
        assert job.errors == ["parse failed during cancellation"]


@pytest.mark.asyncio
async def test_scip_cancellation_drains_real_subprocess_before_temp_cleanup(tmp_path, monkeypatch):
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    writer = MagicMock()
    release = tmp_path / "release-child"
    started = threading.Event()
    child = None
    output_dir = None
    parser = MagicMock()

    class Indexer:
        def run(self, path, lang, output):
            nonlocal child, output_dir
            output_dir = output
            script = (
                "import pathlib,sys,time\n"
                "release=pathlib.Path(sys.argv[1])\n"
                "deadline=time.monotonic()+10\n"
                "while not release.exists():\n"
                "    if time.monotonic()>deadline: sys.exit(23)\n"
                "    time.sleep(0.01)\n"
                "pathlib.Path(sys.argv[2]).write_bytes(b'owned subprocess output')\n"
            )
            child = subprocess.Popen([sys.executable, "-c", script, str(release), str(output / "index.scip")])
            started.set()
            assert child.wait(timeout=15) == 0
            return output / "index.scip"

    task = asyncio.create_task(
        make_pipeline(
            tmp_path,
            monkeypatch,
            "scip",
            writer,
            jobs,
            job_id,
            scip_mod=SimpleNamespace(ScipIndexer=Indexer, ScipIndexParser=parser),
        )
    )
    try:
        assert await asyncio.to_thread(started.wait, 5), "the owned subprocess did not start"
        assert child.poll() is None
        assert output_dir.is_dir()
        task.cancel()
        done, _ = await asyncio.wait({task}, timeout=0.05)
        assert not done
        assert child.poll() is None
        assert output_dir.is_dir()
        assert jobs.get_job(job_id).status == JobStatus.RUNNING
    finally:
        release.write_text("finish naturally")
        await asyncio.gather(task, return_exceptions=True)
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
    assert task.cancelled()
    assert child.returncode == 0
    assert not output_dir.exists()
    parser.assert_not_called()
    writer.add_file_to_graph.assert_not_called()
    assert jobs.get_job(job_id).status == JobStatus.CANCELLED
