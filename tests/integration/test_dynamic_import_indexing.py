"""Real JS/TS indexing must write dynamic imports to the intended File nodes."""

import os
import subprocess
import sys

import pytest

NATIVE_SCRIPT = r'''
import asyncio
import importlib.util
import os
import sys
from pathlib import Path

backend, root = sys.argv[1], Path(sys.argv[2])
module = "kuzu" if backend == "kuzudb" else "ladybug"
if importlib.util.find_spec(module) is None:
    raise SystemExit(77)
if backend == "ladybugdb":
    from codegraphcontext.core import ladybugdb_unavailable_reason
    reason = ladybugdb_unavailable_reason()
    if reason:
        print(reason)
        raise SystemExit(77)
    from codegraphcontext.core.database_ladybug import LadybugDBManager as Manager
else:
    from codegraphcontext.core.database_kuzu import KuzuDBManager as Manager
from codegraphcontext.core.jobs import JobManager, JobStatus
from codegraphcontext.tools.graph_builder import GraphBuilder

os.environ.update({"DEFAULT_DATABASE": backend, "CGC_RUNTIME_DB_TYPE": backend,
                   "CGC_EMBEDDED_BUFFER_POOL_MB": "256", "SCIP_INDEXER": "false",
                   "ENABLE_VECTOR_RESOLVE": "false", "ENABLE_INHERIT_RESOLVE": "false"})
repo = root / "repo"
repo.mkdir()
(repo / "loader.js").write_text("""export function loadJs() { return import('./lazy_js.js'); }
export const loadArrow = () => import('./lazy_js.js');
export class Loader { loadMethod() { return import('./lazy_js.js'); } }
export function loadComment() { return import(/* chunk */ './lazy_js.js'); }
export function loadUnknown(name) { return import(name); }
export function loadTemplate(name) { return import(`./lazy_${name}.js`); }
export function loadMissing() { return import('./missing.js'); }
import './unrelated.js';
""", encoding="utf-8")
(repo / "loader.ts").write_text("""export function loadTs() {
    const value: typeof import('./type_only.ts') = null;
    return import('./lazy_ts.ts');
}
""", encoding="utf-8")
for name in ("lazy_js.js", "lazy_ts.ts", "type_only.ts", "unrelated.js"):
    (repo / name).write_text("export function helper() { return 1; }\n", encoding="utf-8")

manager = Manager(str(root / "db"))
try:
    jobs = JobManager()
    async def index():
        builder = GraphBuilder(manager, jobs, asyncio.get_running_loop())
        job_id = jobs.create_job(str(repo), is_dependency=False)
        await builder.build_graph_from_path_async(repo, job_id=job_id)
        assert jobs.get_job(job_id).status == JobStatus.COMPLETED
    asyncio.run(index())
    with manager.get_driver().session() as session:
        rows = session.run("""MATCH (caller:Function)-[r:CALLS|HEURISTIC_CALLS]->(target:File)
            RETURN caller.name AS caller, target.path AS target, r.line_number AS line""").data()
    actual = {(row["caller"], Path(row["target"]).name, row["line"]) for row in rows}
    expected = {("loadJs", "lazy_js.js", 1), ("loadArrow", "lazy_js.js", 2),
                ("loadMethod", "lazy_js.js", 3), ("loadComment", "lazy_js.js", 4),
                ("loadTs", "lazy_ts.ts", 3)}
    assert actual == expected, (actual, expected)
    assert len(rows) == len(expected), rows
    print("dynamic import graph matches runtime-only literal targets")
finally:
    manager.close_driver()
'''


@pytest.mark.integration
@pytest.mark.parametrize("backend", ["kuzudb", "ladybugdb"])
def test_dynamic_imports_on_native_backend(backend, tmp_path):
    # The two native extensions must run in separate interpreters.
    result = subprocess.run(
        [sys.executable, "-c", NATIVE_SCRIPT, backend, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=90,
        env=os.environ.copy(),
    )
    if result.returncode == 77:
        pytest.skip(result.stdout.strip() or f"{backend} is unavailable")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "runtime-only literal targets" in result.stdout
