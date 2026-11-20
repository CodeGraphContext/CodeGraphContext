"""Per-phase index timings.

The index summary's only timing used to be ``serialization_seconds``: everything
after parsing (node + IMPORTS writes, inheritance, CALLS, framework passes, the
optional resolution passes), shown by the CLI as
"Serialization seconds"; the SCIP path always said 0.0 and MCP jobs exposed no
summary. Now every phase of a full index is timed (``PhaseTimings``), the summary
carries ``phase_seconds`` / ``total_seconds`` / ``post_parse_seconds`` (with
``serialization_seconds`` a deprecated alias of the old window), the CLI prints a
phase table, and an MCP job carries the summary in ``result.index_summary``.
"""
from __future__ import annotations

import ast
import asyncio
import io
import re
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.jobs import JobManager, JobStatus
from codegraphcontext.tools.indexing import pipeline
from codegraphcontext.tools.indexing.phase_timings import (
    INDEX_PHASES,
    PhaseTimings,
    active_phase,
    recording,
)

SLOW = 0.3
SRC = Path(pipeline.__file__).resolve().parent


def _no_optional_passes(key):
    """Config with every opt-in pass off (ENABLE_*, SCIP) and nothing else set."""
    return "false" if key.startswith("ENABLE_") or key == "SCIP_INDEXER" else None


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


# ── PhaseTimings ─────────────────────────────────────────────────────────────

def test_phases_accumulate_and_report_in_vocabulary_order():
    clock = _Clock()
    t = PhaseTimings(clock=clock)
    with t.phase("calls_write"):
        clock.now += 2.0
    with t.phase("discover"):
        clock.now += 0.5
    with t.phase("calls_write"):
        clock.now += 1.0
    t.add("parse", 0.25)
    assert t.as_dict() == {"discover": 0.5, "parse": 0.25, "calls_write": 3.0}
    assert list(t.as_dict()) == [p for p in INDEX_PHASES if p in t.as_dict()]
    assert t.seconds("calls_write", "discover", "embeddings") == pytest.approx(3.5)
    assert t.elapsed() == pytest.approx(3.5)


def test_a_nested_phase_is_subtracted_from_its_parent():
    """Every second is attributed to exactly one phase: the phases never add up
    to more than the run (IMPORTS writes nest inside the per-file write)."""
    clock = _Clock()
    t = PhaseTimings(clock=clock)
    with t.phase("write_nodes"):
        clock.now += 1.0
        with t.phase("write_imports"):
            clock.now += 0.75
        clock.now += 0.5
    assert t.as_dict() == {"write_nodes": 1.5, "write_imports": 0.75}
    assert sum(t.as_dict().values()) == pytest.approx(t.elapsed())


def test_a_phase_is_recorded_even_when_its_block_raises():
    clock = _Clock()
    t = PhaseTimings(clock=clock)
    with pytest.raises(RuntimeError):
        with t.phase("framework_links"):
            clock.now += 0.2
            raise RuntimeError("boom")
    assert t.as_dict() == {"framework_links": 0.2}
    with t.phase("discover"):  # the open-phase stack was unwound
        clock.now += 0.1
    assert t.as_dict()["discover"] == 0.1


@pytest.mark.parametrize("use", ["phase", "add", "seconds"])
def test_an_unknown_phase_name_is_rejected(use):
    t = PhaseTimings()
    with pytest.raises(ValueError, match="unknown index phase 'calls_wirte'"):
        if use == "phase":
            with t.phase("calls_wirte"):
                pass
        elif use == "add":
            t.add("calls_wirte", 1.0)
        else:
            t.seconds("calls_wirte")


def test_active_phase_is_a_no_op_outside_a_run_and_times_inside_one():
    with active_phase("write_imports"):
        pass  # no run in progress (watcher / incremental writes): nothing recorded, no error
    clock = _Clock()
    t = PhaseTimings(clock=clock)
    with recording(t):
        with active_phase("write_imports"):
            clock.now += 0.4
    with active_phase("write_imports"):
        clock.now += 9.0  # after the run: not attributed to it
    assert t.as_dict() == {"write_imports": 0.4}


def test_active_phase_reaches_worker_threads_and_keeps_runs_apart():
    """asyncio.to_thread copies the context: the writer, called in a worker thread,
    records into its own run's timings even when two runs share one writer."""
    def write(label):
        with active_phase("write_imports"):
            time.sleep(0.05 if label == "a" else 0.2)

    async def run(label):
        t = PhaseTimings()
        with recording(t):
            await asyncio.to_thread(write, label)
        return t.as_dict()["write_imports"]

    async def both():
        return await asyncio.gather(run("a"), run("b"))

    a, b = asyncio.run(both())
    assert 0.05 <= a < 0.15 and b >= 0.2


# ── the vocabulary is the code's (enforcement) ───────────────────────────────

def _phase_literals(source: str):
    """Every string constant in the name argument of ``timings.phase/add/seconds(...)``
    and ``active_phase(...)`` (a conditional name counts both branches)."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            owner = getattr(getattr(func, "value", None), "id", None)
            if fname == "active_phase" or (fname in ("phase", "add", "seconds") and owner == "timings"):
                names |= {c.value for c in ast.walk(node.args[0])
                          if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return names


def test_every_phase_the_pipelines_time_is_in_the_vocabulary_and_every_name_is_used():
    used = set()
    for rel in ("pipeline.py", "scip_pipeline.py", "persistence/writer.py"):
        used |= _phase_literals((SRC / rel).read_text(encoding="utf-8"))
    assert used, "no phase is timed at all"
    assert not used - set(INDEX_PHASES), f"phases outside INDEX_PHASES: {sorted(used - set(INDEX_PHASES))}"
    assert not set(INDEX_PHASES) - used, f"vocabulary entries no pipeline times: {sorted(set(INDEX_PHASES) - used)}"


def test_phase_timings_is_stdlib_only():
    """The timer is imported by the writer and both pipelines: it carries no
    graph or framework code, only the standard library."""
    import inspect

    from codegraphcontext.tools.indexing import phase_timings

    tree = ast.parse(inspect.getsource(phase_timings))
    imported = {(n.module if isinstance(n, ast.ImportFrom) else a.name).split(".")[0]
                for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in (n.names if isinstance(n, ast.Import) else [n])}
    assert imported <= {"__future__", "threading", "time", "contextlib", "contextvars", "typing"}, imported


# ── build_index_summary ──────────────────────────────────────────────────────

def _summary(**kwargs):
    return pipeline.build_index_summary(
        files=[Path("/repo/a.py")], parsers={".py": "python"},
        all_file_data=[{"path": "/repo/a.py", "functions": [{"name": "f"}]}],
        resolved_call_groups=(), **kwargs,
    )


def test_summary_reports_phases_total_and_the_post_parse_window():
    clock = _Clock()
    t = PhaseTimings(clock=clock)
    with t.phase("parse"):
        clock.now += 1.0
    with t.phase("calls_write"):
        clock.now += 2.5
    s = _summary(post_parse_seconds=2.5004, timings=t, total_seconds=3.6)
    assert s["phase_seconds"] == {"parse": 1.0, "calls_write": 2.5}
    assert s["total_seconds"] == 3.6
    assert s["post_parse_seconds"] == 2.5
    assert s["serialization_seconds"] == s["post_parse_seconds"]


def test_serialization_seconds_keyword_is_a_deprecated_alias():
    with pytest.warns(DeprecationWarning, match="post_parse_seconds"):
        s = _summary(serialization_seconds=0.75)
    assert s["post_parse_seconds"] == s["serialization_seconds"] == 0.75
    assert "phase_seconds" not in s


# ── Tree-sitter pipeline (recording writer) ──────────────────────────────────

def _run_tree_sitter(tmp_path, monkeypatch, *, slow=None, job=True, files=2):
    paths = []
    for i in range(files):
        p = tmp_path / f"m{i}.py"
        p.write_text("def f():\n    pass\n")
        paths.append(p)
    monkeypatch.setattr(pipeline, "discover_files_to_index", lambda *a, **k: (paths, tmp_path))
    monkeypatch.setattr(pipeline, "pre_scan_for_imports", lambda *a: {})
    monkeypatch.setattr("codegraphcontext.cli.config_manager.get_config_value", _no_optional_passes)
    logged = []
    monkeypatch.setattr(pipeline, "info_logger", lambda msg: logged.append(str(msg)))
    writer = MagicMock()
    writer.repair_missing_contains_links.return_value = 0

    def sleeper(*a, **k):
        time.sleep(SLOW)
    if slow:
        getattr(writer, slow).side_effect = sleeper
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path)) if job else None
    summary: dict = {}
    asyncio.run(pipeline.run_tree_sitter_index_async(
        tmp_path, False, job_id, None, writer, jobs, {".py": "python"}, lambda s: None,
        lambda repo, f, dep: {"path": str(f), "functions": [], "classes": []},
        writer.add_minimal_file_node, index_summary=summary,
    ))
    return summary, logged, jobs, job_id


def test_tree_sitter_summary_has_every_phase_in_order_within_the_total(tmp_path, monkeypatch):
    summary, _, _, _ = _run_tree_sitter(tmp_path, monkeypatch)
    phases = summary["phase_seconds"]
    for name in ("discover", "pre_scan", "parse", "write_nodes", "inheritance", "type_links",
                 "decorated_by", "calls_resolve", "calls_write", "framework_links"):
        assert name in phases, name
    assert list(phases) == [p for p in INDEX_PHASES if p in phases]
    assert all(v >= 0 for v in phases.values())
    # opt-in passes did not run (ENABLE_* false), the SCIP-only phases never run here
    assert not {"embeddings", "inherit_reresolve", "scip_index", "supplement", "scip_calls"} & set(phases)
    assert sum(phases.values()) <= summary["total_seconds"] + 0.005
    assert summary["post_parse_seconds"] <= summary["total_seconds"]
    assert summary["serialization_seconds"] == summary["post_parse_seconds"]


@pytest.mark.parametrize("slow, phase", [
    ("write_function_call_groups", "calls_write"),
    ("write_inheritance_links", "inheritance"),
    ("write_decorated_by_links", "decorated_by"),
    ("write_embeds_links", "type_links"),
    ("write_cpp_class_function_links", "framework_links"),
    ("add_file_to_graph", "write_nodes"),
])
def test_a_slow_step_shows_in_its_own_phase(tmp_path, monkeypatch, slow, phase):
    summary, _, _, _ = _run_tree_sitter(tmp_path, monkeypatch, slow=slow)
    phases = summary["phase_seconds"]
    assert phases[phase] >= SLOW
    assert max(phases, key=phases.get) == phase, phases
    # the after-parse window still covers it: the deprecated alias keeps its meaning
    assert summary["post_parse_seconds"] >= SLOW


def test_the_slow_parse_loop_is_parse_not_post_parse(tmp_path, monkeypatch):
    paths = [tmp_path / "a.py"]
    paths[0].write_text("pass\n")
    monkeypatch.setattr(pipeline, "discover_files_to_index", lambda *a, **k: (paths, tmp_path))
    monkeypatch.setattr(pipeline, "pre_scan_for_imports", lambda *a: {})
    monkeypatch.setattr("codegraphcontext.cli.config_manager.get_config_value", _no_optional_passes)
    writer = MagicMock()
    writer.repair_missing_contains_links.return_value = 0

    def slow_parse(repo, f, dep):
        time.sleep(SLOW)
        return {"path": str(f), "functions": [], "classes": []}

    summary: dict = {}
    asyncio.run(pipeline.run_tree_sitter_index_async(
        tmp_path, False, None, None, writer, JobManager(), {".py": "python"}, lambda s: None,
        slow_parse, writer.add_minimal_file_node, index_summary=summary,
    ))
    assert summary["phase_seconds"]["parse"] >= SLOW
    assert summary["post_parse_seconds"] < SLOW
    assert summary["total_seconds"] >= SLOW


def test_the_post_processing_log_lines_are_sums_of_phases(tmp_path, monkeypatch):
    """The two INFO lines keep their text and windows: they are the phase sums."""
    summary, logged, _, _ = _run_tree_sitter(tmp_path, monkeypatch, slow="write_inheritance_links")
    phases = summary["phase_seconds"]
    inh = next(m for m in logged if m.startswith("Inheritance links created in "))
    calls = next(m for m in logged if m.startswith("Function calls created in "))
    inh_s = float(re.search(r"created in ([\d.]+)s", inh).group(1))
    calls_s, total_s = map(float, re.search(r"created in ([\d.]+)s\. Total post-processing: ([\d.]+)s", calls).groups())
    expect_inh = phases["inheritance"] + phases["type_links"] + phases["decorated_by"]
    expect_calls = phases["calls_resolve"] + phases["calls_write"]
    assert inh_s == pytest.approx(expect_inh, abs=0.06)
    assert calls_s == pytest.approx(expect_calls, abs=0.06)
    assert total_s == pytest.approx(expect_inh + expect_calls, abs=0.06)
    assert inh.endswith("s. Starting function calls...")


def test_the_mcp_job_carries_the_summary(tmp_path, monkeypatch):
    summary, _, jobs, job_id = _run_tree_sitter(tmp_path, monkeypatch)
    job = jobs.get_job(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.result["index_summary"] == summary
    assert job.result["index_summary"] is not summary, "a later run clearing the builder's dict must not empty the job's"

    from codegraphcontext.tools.handlers.management_handlers import check_job_status

    status = check_job_status(jobs, job_id=job_id)
    reported = status["job"]["result"]["index_summary"]
    assert reported["phase_seconds"] == summary["phase_seconds"]
    assert reported["total_seconds"] == summary["total_seconds"]


def test_a_job_summary_is_published_without_a_caller_dict(tmp_path, monkeypatch):
    """MCP jobs get the summary even when the caller passes no index_summary."""
    p = tmp_path / "a.py"
    p.write_text("pass\n")
    monkeypatch.setattr(pipeline, "discover_files_to_index", lambda *a, **k: ([p], tmp_path))
    monkeypatch.setattr(pipeline, "pre_scan_for_imports", lambda *a: {})
    monkeypatch.setattr("codegraphcontext.cli.config_manager.get_config_value", _no_optional_passes)
    writer = MagicMock()
    writer.repair_missing_contains_links.return_value = 0
    jobs = JobManager()
    job_id = jobs.create_job(str(tmp_path))
    asyncio.run(pipeline.run_tree_sitter_index_async(
        tmp_path, False, job_id, None, writer, jobs, {".py": "python"}, lambda s: None,
        lambda repo, f, dep: {"path": str(f), "functions": [], "classes": []}, writer.add_minimal_file_node,
    ))
    assert "parse" in jobs.get_job(job_id).result["index_summary"]["phase_seconds"]


# ── real writer (embedded Kùzu): IMPORTS split out of the per-file write ──────

kuzu = pytest.importorskip("kuzu")


class _DBM:
    def __init__(self, driver):
        self._driver = driver

    def get_driver(self, graph_name=None):
        return self._driver

    def get_backend_type(self):
        return "kuzudb"


@pytest.fixture
def kuzu_builder(tmp_path, monkeypatch):
    from codegraphcontext.core.database_kuzu import KuzuDBManager
    from codegraphcontext.tools.graph_builder import GraphBuilder

    for key in ("SCIP_INDEXER", "ENABLE_VECTOR_RESOLVE", "ENABLE_INHERIT_RESOLVE"):
        monkeypatch.setenv(key, "false")  # never the user's global config
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    jobs = JobManager()
    loop = asyncio.new_event_loop()
    builder = GraphBuilder(_DBM(driver), jobs, loop)
    builder.create_schema()
    try:
        yield builder, jobs, loop
    finally:
        loop.close()
        manager.close_driver()


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("import os\nimport json\n\nclass A:\n    def run(self):\n        return os.getcwd()\n")
    (repo / "b.py").write_text("from a import A\n\ndef go():\n    return A().run()\n")
    return repo


def test_imports_writes_are_their_own_phase(tmp_path, monkeypatch, kuzu_builder):
    from codegraphcontext.tools.indexing.persistence import writer as writer_mod

    builder, jobs, loop = kuzu_builder
    real = writer_mod._run_node_then_rel

    def slow_imports(session, node_query, node_rows, rel_query, *a, **k):
        if rel_query is writer_mod.IMPORTS_EDGE_QUERY:
            time.sleep(SLOW)
        return real(session, node_query, node_rows, rel_query, *a, **k)

    monkeypatch.setattr(writer_mod, "_run_node_then_rel", slow_imports)
    repo = _repo(tmp_path)
    job_id = jobs.create_job(str(repo))
    loop.run_until_complete(builder.build_graph_from_path_async(repo, job_id=job_id))
    phases = builder.last_index_summary["phase_seconds"]
    assert phases["write_imports"] >= 2 * SLOW  # both files import something
    assert phases["write_nodes"] < phases["write_imports"], "IMPORTS time must not stay in write_nodes"
    assert jobs.get_job(job_id).result["index_summary"]["phase_seconds"] == phases
    with builder._writer.driver.session() as s:
        n = s.run("MATCH (:File)-[r:IMPORTS]->(:Module) RETURN count(r) AS c").data()[0]["c"]
    assert n >= 2, "the timer must not change what is written"


def test_incremental_writes_outside_a_run_record_nothing(tmp_path, kuzu_builder):
    """The watcher's single-file path calls the same writer: no run, no timings, no error."""
    builder, _, _ = kuzu_builder
    repo = _repo(tmp_path)
    data = builder.parse_file(repo, repo / "a.py", False)
    builder._writer.add_file_to_graph(data, repo.name, {}, repo_path_str=repo.as_posix())


# ── SCIP pipeline ─────────────────────────────────────────────────────────────

class _JM:
    def update_job(self, *a, **k):
        pass


def _fake_scip(covered: Path):
    class FakeIndexer:
        def run(self, path, lang, tmpdir):
            time.sleep(SLOW)
            return Path(tmpdir) / "index.scip"

    class FakeParser:
        def parse(self, scip_file, path):
            return {"files": {str(covered.resolve()): {
                "path": str(covered.resolve()), "lang": "c_sharp", "imports": [],
                "functions": [{"name": "Covered", "line_number": 1, "end_line": 2, "args": []}],
                "classes": [], "variables": [], "function_calls_scip": [], "module_level_calls_scip": [],
            }}}

    return SimpleNamespace(ScipIndexer=FakeIndexer, ScipIndexParser=FakeParser)


def test_scip_summary_has_real_timings(tmp_path, kuzu_builder):
    from codegraphcontext.tools.indexing.scip_pipeline import run_scip_index_async

    builder, _, loop = kuzu_builder
    repo = tmp_path / "repo"
    repo.mkdir()
    covered = repo / "Program.cs"
    covered.write_text("class P { void Covered() {} }\n", encoding="utf-8")
    (repo / "helper.py").write_text("import os\n\ndef helper():\n    return os.sep\n", encoding="utf-8")
    jobs = JobManager()
    job_id = jobs.create_job(str(repo))
    summary: dict = {}
    loop.run_until_complete(run_scip_index_async(
        repo, False, job_id, "c_sharp", builder._writer, jobs, builder.parsers.keys(), builder.get_parser,
        _fake_scip(covered), None, index_summary=summary,
    ))
    phases = summary["phase_seconds"]
    for name in ("discover", "scip_index", "pre_scan", "write_nodes", "supplement", "inheritance",
                 "calls_resolve", "calls_write", "scip_calls"):
        assert name in phases, name
    assert list(phases) == [p for p in INDEX_PHASES if p in phases]
    assert phases["scip_index"] >= SLOW
    assert "write_imports" in phases  # helper.py (supplement) imports os
    assert sum(phases.values()) <= summary["total_seconds"] + 0.005
    assert summary["total_seconds"] >= SLOW
    assert 0 < summary["post_parse_seconds"] < summary["total_seconds"] - SLOW + 0.005
    assert summary["serialization_seconds"] == summary["post_parse_seconds"]
    assert jobs.get_job(job_id).result["index_summary"] == summary


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli_output(monkeypatch, summary):
    from rich.console import Console

    from codegraphcontext.cli import cli_helpers

    buf = io.StringIO()
    monkeypatch.setattr(cli_helpers, "console", Console(file=buf, width=200, force_terminal=False))
    cli_helpers._print_index_execution_summary(SimpleNamespace(last_index_summary=summary))
    return buf.getvalue()


def test_cli_prints_the_total_and_a_phase_table(monkeypatch):
    out = _cli_output(monkeypatch, {
        "total_scanned_files": 3, "files_by_extension": {".py (python)": 3}, "function_nodes": 4,
        "class_nodes": 1, "call_edges": 2, "failed_files": 0, "failed_file_details": [],
        "phase_seconds": {"discover": 0.1, "parse": 1.0, "write_nodes": 2.0, "calls_write": 0.9},
        "total_seconds": 4.0, "post_parse_seconds": 2.9, "serialization_seconds": 2.9,
    })
    assert "Serialization seconds" not in out
    assert re.search(r"Index seconds \(total\)\s*\|\s*4\.00", out)
    assert "Index phase timings" in out
    rows = re.findall(r"\|\s*(\w+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)%\s*\|", out)
    assert rows == [("discover", "0.10", "2.5"), ("parse", "1.00", "25.0"),
                    ("write_nodes", "2.00", "50.0"), ("calls_write", "0.90", "22.5")]


def test_cli_tolerates_a_summary_without_phases(monkeypatch):
    out = _cli_output(monkeypatch, {"total_scanned_files": 1, "files_by_extension": {}, "function_nodes": 0,
                                    "class_nodes": 0, "call_edges": 0, "serialization_seconds": 0.93})
    assert "Index phase timings" not in out
    assert "Serialization seconds" not in out
    assert re.search(r"Post-parse seconds\s*\|\s*0\.93", out)
