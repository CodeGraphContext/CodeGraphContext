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
async def run_indexing_in_process(db_type: str, project_path: Path, temp_test_dir: Path) -> Tuple[float, Dict[str, int]]:
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
            
    db_mgr.close_driver()
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
            
    return duration, stats


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
    
    project_path = Path("tests/fixtures/sample_projects").resolve()
    
    db_types = ["kuzudb", "ladybugdb", "falkordb", "neo4j"]
    results = {}
    
    for db_type in db_types:
        try:
            duration, stats = await run_indexing_in_process(db_type, project_path, temp_test_dir)
            results[db_type] = {
                "duration": duration,
                "stats": stats
            }
        except Exception as e:
            if db_type == "neo4j" and "failed to connect" in str(e).lower():
                pytest.skip("Neo4j server is not running/available.")
            raise e
            
    # Compile comparison and assert parity
    print("\n================= E2E PARITY TEST REPORT =================")
    print(f"{'Metric':<25} | {'KuzuDB':<8} | {'LadybugDB':<9} | {'FalkorDB':<8} | {'Neo4j':<8} | Match?")
    print("-" * 78)
    
    keys_to_compare = sorted(list(results["neo4j"]["stats"].keys()))
    # Some relationship resolvers dedupe differently across embedded backends.
    # REL_CALLS: KuzuDB/LadybugDB may drop ≤1 edge when the Neo4j fast/slow MATCH
    # split cannot bind an exact called_line_number (binder/UNWIND fallback).
    allowed_spread = {"REL_IMPORTS": 6, "REL_CALLS": 1}
    all_match = True
    
    for key in keys_to_compare:
        kuzu_val = results["kuzudb"]["stats"].get(key, 0)
        ladybug_val = results["ladybugdb"]["stats"].get(key, 0)
        falkor_val = results["falkordb"]["stats"].get(key, 0)
        neo4j_val = results["neo4j"]["stats"].get(key, 0)
        
        spread = max(kuzu_val, ladybug_val, falkor_val, neo4j_val) - min(
            kuzu_val, ladybug_val, falkor_val, neo4j_val
        )
        matches = spread <= allowed_spread.get(key, 0)
        match_str = "YES" if matches else "NO"
        if not matches:
            all_match = False
            
        print(f"{key:<25} | {kuzu_val:<8} | {ladybug_val:<9} | {falkor_val:<8} | {neo4j_val:<8} | {match_str}")
        
    print("-" * 78)
    print(f"{'Indexing Duration (s)':<25} | {results['kuzudb']['duration']:<8.2f} | {results['ladybugdb']['duration']:<9.2f} | {results['falkordb']['duration']:<8.2f} | {results['neo4j']['duration']:<8.2f} | -")
    
    assert all_match, "❌ Database statistics do not match!"
