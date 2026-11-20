"""Same-line functions must belong only to their actual lexical container (#1919)."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize('backend,module', [('kuzudb','kuzu'), ('ladybugdb','ladybug')])
def test_same_line_method_and_nested_function_containment(tmp_path, backend, module):
    if importlib.util.find_spec(module) is None:
        pytest.skip(f'{module} is not installed')
    env = os.environ.copy()
    env.update(CGC_RUNTIME_DB_TYPE=backend, CGC_RUNTIME_DB_PATH=str(tmp_path/'db'),
               PYTHONPATH=str(Path(__file__).resolve().parents[2]/'src'))
    script = '''
import os,sys
from pathlib import Path
from codegraphcontext.core import get_database_manager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
repo=Path(sys.argv[1]); repo.mkdir()
manager=get_database_manager(db_path=os.environ['CGC_RUNTIME_DB_PATH'])
try:
    writer=GraphWriter(manager.get_driver(),db_manager=manager)
    writer.add_repository_to_graph(repo)
    sources={
        'methods.js':'class Cart{add(x){return x}}class Wishlist{add(x){return x}}',
        'nested.js':'function load(){function step(){return 1}return step()}function save(){function step(){return 2}return step()}',
    }
    parsed=[]
    for name,code in sources.items():
        path=repo/name; path.write_text(code)
        data=TreeSitterParser('javascript').parse(path)
        assert 'error' not in data,data
        parsed.append(data)
    for repeat in range(2):
        for data in parsed:
            writer.add_file_to_graph(data,repo.name,{},repo_path_str=repo.as_posix())
        with manager.get_driver().session() as session:
            methods=session.run("MATCH (c:Class)-[:CONTAINS]->(f:Function) RETURN c.name AS owner,f.class_context AS ctx,f.occurrence_index AS occ").data()
            nested=session.run("MATCH (o:Function)-[:CONTAINS]->(f:Function) RETURN o.name AS owner,f.context AS ctx,f.occurrence_index AS occ").data()
        assert sorted((r['owner'],r['ctx'],r['occ']) for r in methods)==[('Cart','Cart',0),('Wishlist','Wishlist',1)],methods
        assert sorted((r['owner'],r['ctx'],r['occ']) for r in nested)==[('load','load',0),('save','save',1)],nested
finally:
    manager.close_driver()
'''
    result = subprocess.run([sys.executable,'-c',script,str(tmp_path/'repo')],env=env,
                            capture_output=True,text=True,timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
