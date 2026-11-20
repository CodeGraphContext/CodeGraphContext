"""Execute the visualizer's actual query in isolated embedded engine processes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codegraphcontext.cli import visualizer

_SCRIPT = r'''
import json, sys
from codegraphcontext.core import get_database_manager
queries = json.loads(sys.argv[2])
observed = []
for order in ('small', 'forward', 'reverse'):
    manager = get_database_manager(db_path=sys.argv[1] + '/' + order)
    try:
        with manager.get_driver().session() as s:
            s.run("CREATE (:Function {uid:'source',name:'source',path:'/repo/000source',line_number:1})")
            s.run("CREATE (:Function {uid:'target',name:'target',path:'/repo/zzz_target',line_number:1})")
            count = 1 if order == 'small' else 130
            indices = list(range(count))
            if order == 'reverse': indices.reverse()
            for i in indices:
                uid = f'mid{i:03d}'
                s.run("CREATE (:Function {uid:$uid,name:$uid,path:$path,line_number:2})",
                      uid=uid, path='/repo/' + uid)
                calls = [('source', uid, 5, 'a'), (uid, 'target', 6, 'b')]
                if i == 0 and order != 'small':
                    calls.extend([('source', uid, 5, 'z'), ('source', uid, 9, 'a')])
                if order == 'reverse': calls.reverse()
                for src, dst, line, args in calls:
                    s.run("MATCH (a:Function {uid:$src}), (b:Function {uid:$dst}) "
                          "CREATE (a)-[:CALLS {line_number:$line,args_key:$args}]->(b)",
                          src=src,dst=dst,line=line,args=args)
            # CALLS also supports Function -> File -> Function paths, e.g.
            # module evaluation. Keep the real intermediate labels/endpoints.
            s.run("CREATE (:File {path:'/repo/midfile',name:'midfile'})")
            s.run("MATCH (a:Function {uid:'source'}), (f:File {path:'/repo/midfile'}), "
                  "(b:Function {uid:'target'}) "
                  "CREATE (a)-[:CALLS {line_number:11,args_key:'import'}]->(f) "
                  "CREATE (f)-[:CALLS {line_number:12,args_key:'module'}]->(b)")
            rows = s.run(queries[0]).data()
            observed.append([[r['n'].get('uid') or r['n']['name'], r['m'].get('uid') or r['m']['name'], r['rel']['line_number'],
                              r['rel']['args_key']] for r in rows])
            # A depth of one cannot include either hop of this two-hop chain.
            assert s.run(queries[1]).data() == []
    finally:
        manager.close_driver()
print('RESULT ' + json.dumps(observed))
'''


@pytest.mark.integration
@pytest.mark.parametrize('backend,module', [('kuzudb', 'kuzu'), ('ladybugdb', 'ladybug')])
def test_call_chain_exact_hops_and_stable_limit(tmp_path, monkeypatch, backend, module):
    if importlib.util.find_spec(module) is None:
        pytest.skip(f'{module} is not installed')
    queries = []
    monkeypatch.setattr(visualizer, '_launch_visualizer', queries.append)
    for depth in (2, 1):
        visualizer.visualize_call_chain([], 'source', 'target', max_depth=depth,
                                       from_file='/repo/000source', to_file='/repo/zzz_target')
    env = dict(os.environ, CGC_RUNTIME_DB_TYPE=backend)
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'src')
    result = subprocess.run([sys.executable, '-c', _SCRIPT, str(tmp_path), json.dumps(queries)],
                            env=env, text=True, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = next(line[7:] for line in result.stdout.splitlines() if line.startswith('RESULT '))
    small, forward, reverse = json.loads(payload)
    assert small == [
        ['source', 'mid000', 5, 'a'], ['source', 'midfile', 11, 'import'],
        ['mid000', 'target', 6, 'b'], ['midfile', 'target', 12, 'module'],
    ]
    expected = [['source', f'mid{i:03d}', 5, 'a'] for i in range(130)]
    expected.extend([['source', 'mid000', 5, 'z'], ['source', 'mid000', 9, 'a']])
    expected.extend([[f'mid{i:03d}', 'target', 6, 'b'] for i in range(130)])
    expected.extend([['source', 'midfile', 11, 'import'], ['midfile', 'target', 12, 'module']])
    expected.sort(key=lambda edge: (
        '/repo/000source' if edge[0] == 'source' else '/repo/' + edge[0],
        '/repo/zzz_target' if edge[1] == 'target' else '/repo/' + edge[1],
        edge[2], edge[3]))
    assert forward == reverse == expected[:200]
