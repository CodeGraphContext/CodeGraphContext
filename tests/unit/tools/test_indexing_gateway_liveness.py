"""The real gateway health route must run during blocking indexing phases."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from codegraphcontext.api.app import create_app
from codegraphcontext.core.jobs import JobManager, JobStatus
from codegraphcontext.tools.graph_builder import GraphBuilder
from codegraphcontext.tools.indexing import pipeline, scip_pipeline
from codegraphcontext.utils import tree_sitter_manager as manager


class BlockingPhase:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.timed_out = False

    def run(self, *args, **kwargs):
        self.entered.set()
        self.timed_out = not self.release.wait(timeout=5)
        self.finished.set()


async def wait_for_phase(phase):
    while not phase.entered.is_set():
        await asyncio.sleep(0.005)


async def assert_health_during(task, phase):
    try:
        await asyncio.wait_for(wait_for_phase(phase), timeout=3)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert not phase.finished.is_set(), "health ran only after indexing unblocked"
    finally:
        phase.release.set()
        await task
    assert not phase.timed_out


@pytest.fixture(autouse=True)
def disable_optional_indexing(monkeypatch):
    monkeypatch.setattr("codegraphcontext.cli.config_manager.get_config_value", lambda key: "false")


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["repository", "discovery", "prescan", "resolution", "write"])
async def test_tree_sitter_health_during_blocking_phase(tmp_path, monkeypatch, stage):
    source = tmp_path / "app.py"
    source.write_text("def main(): pass\n")
    phase = BlockingPhase()
    writer = MagicMock()
    writer.repair_missing_contains_links.return_value = 0
    monkeypatch.setattr(pipeline, "pre_scan_for_imports", lambda *args: {})
    if stage == "repository":
        writer.add_repository_to_graph.side_effect = phase.run
    elif stage == "discovery":
        def discover(*args, **kwargs):
            phase.run()
            return [source], tmp_path
        monkeypatch.setattr(pipeline, "discover_files_to_index", discover)
    elif stage == "prescan":
        def prescan(*args):
            phase.run()
            return {}
        monkeypatch.setattr(pipeline, "pre_scan_for_imports", prescan)
    elif stage == "resolution":
        original = pipeline.build_function_call_groups
        def resolve(*args, **kwargs):
            phase.run()
            return original(*args, **kwargs)
        monkeypatch.setattr(pipeline, "build_function_call_groups", resolve)
    else:
        writer.write_function_call_groups.side_effect = phase.run

    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    summary = {}
    task = asyncio.create_task(pipeline.run_tree_sitter_index_async(
        tmp_path, True, job_id, None, writer, jobs, {".py": "python"},
        lambda extension: None,
        lambda *args: {"path": str(source), "functions": [], "classes": []},
        writer.add_minimal_file_node, index_summary=summary,
    ))
    await assert_health_during(task, phase)
    assert jobs.get_job(job_id).status == JobStatus.COMPLETED
    assert summary["total_scanned_files"] == 1
    writer.add_file_to_graph.assert_called_once()


def fake_scip_module(source, phase=None):
    class Indexer:
        def run(self, path, lang, output):
            if phase:
                phase.run()
            result = output / "index.scip"
            result.write_bytes(b"test")
            return result

    class Parser:
        def parse(self, index, path):
            return {"files": {str(source): {"path": str(source), "functions": [], "classes": []}}}

    return SimpleNamespace(ScipIndexer=Indexer, ScipIndexParser=Parser)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["indexer", "prescan", "supplement", "write", "postprocess"])
async def test_scip_health_during_blocking_phase(tmp_path, monkeypatch, stage):
    source = (tmp_path / "app.py").resolve()
    source.write_text("def main(): pass\n")
    phase = BlockingPhase()
    writer = MagicMock()
    monkeypatch.setattr(scip_pipeline, "pre_scan_for_imports", lambda *args: {})
    parser = MagicMock()
    parser.parse.return_value = {"functions": [], "classes": []}
    if stage == "prescan":
        def prescan(*args):
            phase.run()
            return {}
        monkeypatch.setattr(scip_pipeline, "pre_scan_for_imports", prescan)
    elif stage == "supplement":
        def parse(*args, **kwargs):
            phase.run()
            return {"functions": [], "classes": []}
        parser.parse.side_effect = parse
    elif stage == "write":
        writer.add_file_to_graph.side_effect = phase.run
    elif stage == "postprocess":
        writer.write_scip_call_edges.side_effect = phase.run
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    task = asyncio.create_task(scip_pipeline.run_scip_index_async(
        tmp_path, True, job_id, "python", writer, jobs, {".py"},
        lambda suffix: parser, fake_scip_module(source, phase if stage == "indexer" else None),
    ))
    await assert_health_during(task, phase)
    assert jobs.get_job(job_id).status == JobStatus.COMPLETED
    writer.write_scip_call_edges.assert_called_once()


@pytest.mark.asyncio
async def test_cancelled_scip_worker_does_not_start_graph_writes(tmp_path, monkeypatch):
    source = (tmp_path / "app.py").resolve()
    source.write_text("pass\n")
    phase = BlockingPhase()
    stopped = threading.Event()
    writer = MagicMock()
    original = scip_pipeline._run_scip_index

    def worker(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        finally:
            stopped.set()

    monkeypatch.setattr(scip_pipeline, "_run_scip_index", worker)
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    task = asyncio.create_task(scip_pipeline.run_scip_index_async(
        tmp_path, True, job_id, "python", writer, jobs, {".py"},
        lambda suffix: None, fake_scip_module(source, phase),
    ))
    try:
        await asyncio.wait_for(wait_for_phase(phase), timeout=3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        phase.release.set()
    assert await asyncio.to_thread(stopped.wait, 3)
    writer.add_file_to_graph.assert_not_called()
    writer.write_scip_call_edges.assert_not_called()
    assert jobs.get_job(job_id).status != JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_failed_cold_grammar_keeps_health_live_and_fails_once(tmp_path, monkeypatch):
    import tree_sitter_language_pack

    for name in ("_Language", "_Parser", "_get_language", "_manager_instance"):
        monkeypatch.setattr(manager, name, None)
    phase = BlockingPhase()

    def fail_prefetch(languages):
        assert languages == ["python"]
        phase.run()
        raise PermissionError("grammar cache is read-only")

    prefetch = MagicMock(side_effect=fail_prefetch)
    loader = MagicMock()
    monkeypatch.setattr(tree_sitter_language_pack, "prefetch", prefetch)
    monkeypatch.setattr(tree_sitter_language_pack, "get_language", loader)
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text("pass\n")
    builder = GraphBuilder.__new__(GraphBuilder)
    builder.parsers = {".py": "python"}
    builder._parsed_cache = threading.local()
    builder._writer = MagicMock()
    builder.job_manager = JobManager()
    job_id = builder.job_manager.create_job(str(tmp_path))
    task = asyncio.create_task(builder.build_graph_from_path_async(tmp_path, job_id=job_id))
    await assert_health_during(task, phase)
    assert builder.job_manager.get_job(job_id).status == JobStatus.FAILED
    assert "grammar cache is read-only" in builder.job_manager.get_job(job_id).errors[0]
    prefetch.assert_called_once_with(["python"])
    loader.assert_not_called()
    builder._writer.add_file_to_graph.assert_not_called()


def test_prefetch_uses_pack_alias_and_cached_language_is_not_downloaded_again(monkeypatch):
    import tree_sitter_language_pack

    for name in ("_Language", "_Parser", "_get_language"):
        monkeypatch.setattr(manager, name, None)
    calls = []
    expected = object()
    monkeypatch.setattr(tree_sitter_language_pack, "prefetch", lambda languages: calls.append(("prefetch", languages)))

    def load(name):
        calls.append(("get_language", name))
        return expected

    monkeypatch.setattr(tree_sitter_language_pack, "get_language", load)
    registry = manager.TreeSitterManager()
    assert registry.get_language_safe("c#") is expected
    assert registry.get_language_safe("c_sharp") is expected
    assert calls == [("prefetch", ["csharp"]), ("get_language", "csharp")]
