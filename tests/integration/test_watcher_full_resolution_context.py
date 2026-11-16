"""An unchanged save must retain full-index call edges on both embedded engines."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.integration
@pytest.mark.parametrize('backend,module', [('kuzudb', 'kuzu'), ('ladybugdb', 'ladybug')])
def test_unchanged_save_matches_full_index_and_reuses_context(tmp_path, backend, module):
    if importlib.util.find_spec(module) is None:
        pytest.skip(f'{module} is not installed')
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'svc.py').write_text('class Service:\n    def go(self): return 1\n\ndef make_service() -> Service:\n    return Service()\n')
    (repo / 'app.py').write_text('from svc import Service, make_service\n\ndef run():\n    s = Service()\n    s.go()\n\ndef run2():\n    make_service().go()\n')
    env = os.environ.copy()
    env.update(CGC_RUNTIME_DB_TYPE=backend, CGC_RUNTIME_DB_PATH=str(tmp_path / 'graph.db'),
               SCIP_INDEXER='false', ENABLE_INHERIT_RESOLVE='false', ENABLE_VECTOR_RESOLVE='false')
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'src')
    script = '''
import asyncio, json, os, sys
from pathlib import Path
from codegraphcontext.core import get_database_manager
from codegraphcontext.core.jobs import JobManager
from codegraphcontext.core.watcher import RepositoryEventHandler
from codegraphcontext.tools.graph_builder import GraphBuilder
manager = get_database_manager(db_path=os.environ['CGC_RUNTIME_DB_PATH'])
repo = Path(sys.argv[1])
try:
    async def index():
        jobs = JobManager()
        builder = GraphBuilder(manager, jobs, asyncio.get_running_loop())
        await builder.build_graph_from_path_async(repo, job_id=jobs.create_job(str(repo), is_dependency=False))
        return builder
    builder = asyncio.run(index())
    def snapshot():
        rows = []
        with manager.get_driver().session() as session:
            for rel in ['CALLS', 'HEURISTIC_CALLS']:
                result = session.run(f'MATCH (a)-[r:{rel}]->(b) RETURN a.name AS caller, a.path AS caller_path, b.name AS target, b.path AS target_path, r.line_number AS line, r.resolution_tier AS tier').data()
                rows.extend((rel, json.dumps(row, sort_keys=True)) for row in result)
        return sorted(rows)
    full = snapshot()
    assert any('"caller": "run"' in row and '"target": "Service"' in row for _, row in full), full
    handler = RepositoryEventHandler(builder, repo, perform_initial_scan=False)
    handler.imports_map = builder.pre_scan_imports(list(repo.glob('*.py')))
    handler._handle_modification(str(repo / 'app.py'))
    assert snapshot() == full, (full, snapshot())
    parsed = []
    parse_file = builder.parse_file
    def record_parse(root, path, *args, **kwargs):
        parsed.append(Path(path).name)
        return parse_file(root, path, *args, **kwargs)
    builder.parse_file = record_parse
    handler._handle_modification(str(repo / 'app.py'))
    assert snapshot() == full, (full, snapshot())
    assert 'svc.py' not in parsed, parsed
    assert parsed.count('app.py') == 1, parsed
    handler.cancel_timers()
finally:
    manager.close_driver()
'''
    result = subprocess.run([sys.executable, '-c', script, str(repo)], env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
