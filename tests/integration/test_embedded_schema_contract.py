"""Execute map updates and a typed-parameter bundle round trip on both engines."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.integration
@pytest.mark.parametrize('backend,module', [('kuzudb', 'kuzu'), ('ladybugdb', 'ladybug')])
def test_schema_map_updates_and_typed_bundle_roundtrip(tmp_path, backend, module):
    if importlib.util.find_spec(module) is None:
        pytest.skip(f'{module} is not installed')
    env = os.environ.copy()
    env['CGC_RUNTIME_DB_TYPE'] = backend
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'src')
    script = '''
import sys
from pathlib import Path
from codegraphcontext.core import get_database_manager
from codegraphcontext.core.cgc_bundle import CGCBundle
from codegraphcontext.core.embedded_schema import NODE_PRIMARY_KEYS, NODE_PROPERTIES

root = Path(sys.argv[1])
manager = get_database_manager(db_path=str(root / 'source.db'))
try:
    with manager.get_driver().session() as session:
        for label, key in NODE_PRIMARY_KEYS.items():
            props = {key: f'{label}-key', 'unknown_column': 'must be filtered'}
            if 'name' in NODE_PROPERTIES[label]:
                props['name'] = f'{label}-key'
            if label == 'Function':
                props.update(name='greet', path='/sample/Greeter.java', line_number=1,
                             arg_types=['String', 'Int'], args=['name', 'times'], embedding=[0.1, 0.2])
            session.run(f'MERGE (n:`{label}` {{{key}: $key}}) SET n += $props',
                        key=f'{label}-key', props=props)
        row = session.run("MATCH (f:Function {name: 'greet'}) RETURN f.arg_types AS types, f.embedding AS vector").data()[0]
        assert row['types'] == ['String', 'Int'], row
        assert row['vector'] == [0.1, 0.2], row
    bundle = root / 'schema.cgc'
    ok, message = CGCBundle(manager).export_to_bundle(bundle)
    assert ok, message
finally:
    manager.close_driver()

manager = get_database_manager(db_path=str(root / 'destination.db'))
try:
    ok, message = CGCBundle(manager).import_from_bundle(bundle)
    assert ok, message
    with manager.get_driver().session() as session:
        row = session.run("MATCH (f:Function {name: 'greet'}) RETURN f.arg_types AS types, f.args AS args, f.embedding AS vector").data()[0]
        assert row == {'types': ['String', 'Int'], 'args': ['name', 'times'], 'vector': [0.1, 0.2]}, row
finally:
    manager.close_driver()
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)], env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
