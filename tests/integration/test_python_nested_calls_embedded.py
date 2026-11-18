"""Nested argument expressions retain their real caller on both embedded engines."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.integration
@pytest.mark.parametrize('backend,module', [('kuzudb', 'kuzu'), ('ladybugdb', 'ladybug')])
def test_nested_arguments_are_calls_from_lexical_function(tmp_path, backend, module):
    if importlib.util.find_spec(module) is None:
        pytest.skip(f'{module} is not installed')
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'calls.py').write_text(
        'def f(x): return x\ndef g(x): return x\ndef h(x): return g(f(x))\n')
    env = os.environ.copy()
    env.update(CGC_RUNTIME_DB_TYPE=backend, CGC_RUNTIME_DB_PATH=str(tmp_path / 'graph.db'),
               SCIP_INDEXER='false', ENABLE_INHERIT_RESOLVE='false', ENABLE_VECTOR_RESOLVE='false')
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'src')
    script = '''
import asyncio, os, sys
from pathlib import Path
from codegraphcontext.core import get_database_manager
from codegraphcontext.core.jobs import JobManager
from codegraphcontext.tools.graph_builder import GraphBuilder
manager = get_database_manager(db_path=os.environ['CGC_RUNTIME_DB_PATH'])
try:
    async def index():
        jobs = JobManager()
        builder = GraphBuilder(manager, jobs, asyncio.get_running_loop())
        repo = Path(sys.argv[1])
        await builder.build_graph_from_path_async(repo, job_id=jobs.create_job(str(repo), is_dependency=False))
    asyncio.run(index())
    with manager.get_driver().session() as session:
        rows = session.run('MATCH (a:Function)-[:CALLS]->(b:Function) RETURN a.name AS caller, b.name AS callee').data()
    pairs = {(row['caller'], row['callee']) for row in rows}
    assert ('h', 'f') in pairs and ('h', 'g') in pairs, pairs
    assert ('g', 'f') not in pairs, pairs
finally:
    manager.close_driver()
'''
    result = subprocess.run([sys.executable, '-c', script, str(repo)], env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
