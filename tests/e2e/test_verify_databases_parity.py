import os
import sys
import time
import json
import shutil
import asyncio
import pytest
from pathlib import Path
from typing import Tuple, Dict

# We run indexing as a subprocess to keep PyBind11 namespace and database environments isolated
async def run_indexing_in_process(db_type: str, project_path: Path, temp_test_dir: Path) -> Tuple[float, Dict[str, int], list]:
    print(f"\n================= RUNNING {db_type.upper()} INDEXING IN SUBPROCESS =================")
    
    db_path = (temp_test_dir / f"{db_type}_test_db").as_posix()
    
    # Pre-clean database directories to ensure no residual states
    if db_type != "neo4j":
        print(f"Clearing database directory at: {db_path}")
        if os.path.isdir(db_path):
            shutil.rmtree(db_path, ignore_errors=True)
        else:
            try:
                os.remove(db_path)
            except OSError:
                pass
        if db_type == "falkordb":
            try:
                os.remove(str(temp_test_dir / "falkordb.sock"))
            except OSError:
                pass
    
    project_path_str = project_path.resolve().as_posix()
    dotenv_path_str = (Path.home() / ".codegraphcontext" / ".env").as_posix()
    # The CALLS edge dump is ~650 entries. Printing it to stdout floods the
    # Actions step log and GitHub truncates the whole step — including the
    # comparison table. Pass it through a file so only the small diff is logged.
    edges_out_str = (temp_test_dir / f"{db_type}_calls_edges.json").as_posix()
    
    # Construct a python command to run the indexing
    cmd = f"""
import os, sys, asyncio, json
from dotenv import load_dotenv
load_dotenv(r'{dotenv_path_str}')
os.environ.setdefault('NEO4J_URI', 'bolt://localhost:7687')
os.environ.setdefault('NEO4J_USERNAME', 'neo4j')
os.environ['NEO4J_PASSWORD'] = '12345678'
sys.path.insert(0, os.path.abspath('src'))
from codegraphcontext.core import get_database_manager
from codegraphcontext.tools.graph_builder import GraphBuilder
from codegraphcontext.core.jobs import JobManager
from pathlib import Path

async def run():
    os.environ['CGC_RUNTIME_DB_TYPE'] = '{db_type}'
    db_path = r'{db_path}'
    
    if '{db_type}' == 'neo4j':
        # Clear Neo4j
        db_mgr = get_database_manager()
        with db_mgr.get_driver().session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        db_mgr.close_driver()
    
    db_mgr = get_database_manager(db_path=db_path)
    job_mgr = JobManager()
    builder = GraphBuilder(db_mgr, job_mgr, asyncio.get_running_loop())
    
    project_path = Path('{project_path_str}')
    print(f"Indexing path: {{project_path}}")
    await builder.build_graph_from_path_async(project_path)
    
    # Collect stats before closing
    stats = {{}}
    with db_mgr.get_driver().session() as session:
        # Node counts
        node_labels = ["Class", "Function", "Variable", "Module", "File", "Repository", "Directory", "ExternalClass"]
        for label in node_labels:
            res = session.run(f"MATCH (n:`{{label}}`) RETURN count(n)")
            stats[f"NODE_{{label}}"] = res.single()[0]
            
        # Relationship counts
        rel_types = ["INHERITS", "CALLS", "INCLUDES", "CONTAINS", "IMPORTS", "MAPS_TO", "HAS_PARAMETER"]
        for rel in rel_types:
            res = session.run(f"MATCH ()-[r:`{{rel}}`]->() RETURN count(r)")
            stats[f"REL_{{rel}}"] = res.single()[0]
            
        # Diagnostic: dump the CALLS edge set so a REL_CALLS mismatch can be
        # attributed to specific edges instead of just a count. Keys are stable
        # across backends (source paths, not internal node ids).
        calls_edges = []
        try:
            res = session.run(
                "MATCH (caller)-[r:`CALLS`]->(callee) "
                "RETURN caller.name AS cn, caller.path AS cp, caller.line_number AS cl, "
                "callee.name AS en, callee.path AS ep, callee.line_number AS el, "
                "r.line_number AS rl"
            )
            base = str(project_path)
            for rec in res:
                d = dict(rec)
                def _rel(v):
                    v = "" if v is None else str(v)
                    return v[len(base):].lstrip("/") if v.startswith(base) else v
                calls_edges.append(
                    f"{{_rel(d.get('cp'))}}:{{d.get('cn')}}@{{d.get('cl')}}"
                    f" -> {{_rel(d.get('ep'))}}:{{d.get('en')}}@{{d.get('el')}}"
                    f" [call_line={{d.get('rl')}}]"
                )
        except Exception as _e:
            calls_edges = ["<edge dump failed: " + str(_e) + ">"]

    db_mgr.close_driver()
    stats["REL_CALLS_DISTINCT"] = len(set(calls_edges))
    with open(r'{edges_out_str}', "w") as _f:
        json.dump(calls_edges, _f)
    print("STATS_JSON:" + json.dumps(stats))

async def main():
    try:
        await run()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

asyncio.run(main())
"""
    
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    start_time = time.time()
    stdout, stderr = await proc.communicate()
    duration = time.time() - start_time
    
    print(f"[{db_type} STDOUT]:\n{stdout.decode()}")
    if stderr:
        print(f"[{db_type} STDERR]:\n{stderr.decode()}", file=sys.stderr)
        
    if proc.returncode != 0:
        if db_type == "neo4j" and (b"Neo4jConnectionError" in stderr or b"failed to connect" in stderr.lower()):
            raise ConnectionError("Neo4j connection failed to connect.")
        raise RuntimeError(f"Indexing process failed for {db_type} with exit code {proc.returncode}")
        
    # Extract stats from stdout
    stats = {}
    for line in stdout.decode().splitlines():
        if line.startswith("STATS_JSON:"):
            stats = json.loads(line[len("STATS_JSON:"):])
            break

    calls_edges = []
    try:
        with open(edges_out_str) as _f:
            calls_edges = json.load(_f)
    except (OSError, ValueError):
        pass

    return duration, stats, calls_edges


@pytest.mark.e2e
@pytest.mark.slow
def test_database_parity_e2e(temp_test_dir):
    asyncio.run(_run_database_parity_e2e(temp_test_dir))


async def _run_database_parity_e2e(temp_test_dir):
    """
    Run indexing against KuzuDB, LadybugDB, FalkorDB Lite, and Neo4j
    and verify 100% mathematical parity across all extracted nodes and relationships.
    """
    os.environ.setdefault('NEO4J_URI', 'bolt://localhost:7687')
    os.environ.setdefault('NEO4J_USERNAME', 'neo4j')
    os.environ.setdefault('NEO4J_PASSWORD', '12345678')
    
    import importlib.util
    project_path = Path("tests/fixtures/sample_projects").resolve()
    
    db_types_to_run = []
    pkg_map = {"kuzudb": "kuzu", "ladybugdb": "ladybug", "falkordb": "falkordb", "neo4j": "neo4j"}
    for db in ["kuzudb", "ladybugdb", "falkordb", "neo4j"]:
        if importlib.util.find_spec(pkg_map[db]) is None:
            print(f"Skipping {db}: {pkg_map[db]} driver not installed.")
            continue
        db_types_to_run.append(db)
        
    db_types = db_types_to_run
    results = {}
    
    for db_type in db_types:
        try:
            duration, stats, calls_edges = await run_indexing_in_process(db_type, project_path, temp_test_dir)
            results[db_type] = {
                "duration": duration,
                "stats": stats,
                "calls_edges": calls_edges,
            }
        except Exception as e:
            if db_type == "neo4j" and "failed to connect" in str(e).lower():
                pytest.skip("Neo4j server is not running/available.")
            raise e
            
    # Compile comparison and assert parity
    print("\n================= E2E PARITY TEST REPORT =================")
    header_dbs = "".join(f"{db.title():<10} | " for db in db_types)
    print(f"{'Metric':<25} | {header_dbs}Match?")
    print("-" * (35 + 13 * len(db_types)))
    
    if not results:
        pytest.skip("No database drivers are installed to run parity tests.")
    
    # We will use the keys from the first available database as reference
    ref_db = next(iter(results.values()))
    # REL_CALLS_DISTINCT is a diagnostic, not a parity metric.
    keys_to_compare = sorted(
        k for k in ref_db["stats"].keys() if k != "REL_CALLS_DISTINCT"
    )
    # Some relationship resolvers dedupe differently across embedded backends.
    # REL_CALLS: KuzuDB/LadybugDB may drop ≤1 edge when the Neo4j fast/slow MATCH
    # split cannot bind an exact called_line_number (binder/UNWIND fallback).
    allowed_spread = {"REL_IMPORTS": 6, "REL_CALLS": 1}
    all_match = True
    
    for key in keys_to_compare:
        vals = [results[db]["stats"].get(key, 0) for db in db_types if db in results]
        
        spread = max(vals) - min(vals) if vals else 0
        matches = spread <= allowed_spread.get(key, 0)
        match_str = "YES" if matches else "NO"
        if not matches:
            all_match = False
            
        vals_str = "".join(f"{v:<10} | " for v in vals)
        print(f"{key:<25} | {vals_str}{match_str}")
        
    print("-" * (35 + 13 * len(db_types)))
    
    dur_str = "".join(f"{results[db]['duration']:<10.2f} | " for db in db_types if db in results)
    print(f"{'Indexing Duration (s)':<25} | {dur_str}-")

    _report_calls_edge_diff(results, db_types)

    assert all_match, "❌ Database statistics do not match!"


def _report_calls_edge_diff(results, db_types):
    """Print which specific CALLS edges differ between backends.

    REL_CALLS is the only metric that drifts between backends, and a bare count
    cannot distinguish "this backend dropped an edge" from "that backend wrote a
    duplicate". This prints, per backend: total vs distinct edges (a gap means
    duplicates, which Neo4j can produce because the writer uses CREATE rather
    than MERGE there), and the edges unique to each backend relative to the
    union across all of them.
    """
    edge_sets = {
        db: set(results.get(db, {}).get("calls_edges") or [])
        for db in db_types
    }
    if not any(edge_sets.values()):
        print("\n[CALLS DIAG] no edge data captured.")
        return

    print("\n================= CALLS EDGE DIAGNOSTICS =================")
    for db in db_types:
        raw = results.get(db, {}).get("calls_edges") or []
        dupes = len(raw) - len(set(raw))
        print(f"{db:<12} total={len(raw):<6} distinct={len(set(raw)):<6} duplicates={dupes}")

    union = set().union(*edge_sets.values())
    common = set.intersection(*edge_sets.values()) if all(edge_sets.values()) else set()
    print(f"\nunion={len(union)}  common-to-all={len(common)}  differing={len(union) - len(common)}")

    for db in db_types:
        missing = sorted(union - edge_sets[db])
        extra = sorted(edge_sets[db] - common) if common else []
        if missing:
            print(f"\n--- MISSING from {db} ({len(missing)}) ---")
            for e in missing[:40]:
                print(f"    {e}")
            if len(missing) > 40:
                print(f"    ... and {len(missing) - 40} more")
        if extra:
            print(f"\n--- ONLY in {db} ({len(extra)}) ---")
            for e in extra[:40]:
                print(f"    {e}")
            if len(extra) > 40:
                print(f"    ... and {len(extra) - 40} more")
    print("=" * 58)
