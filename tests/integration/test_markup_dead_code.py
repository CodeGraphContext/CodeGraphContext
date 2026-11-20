"""Selectors are searchable markup facts, not uncalled executable functions."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize('backend,module', [('kuzudb', 'kuzu'), ('ladybugdb', 'ladybug')])
def test_markup_is_excluded_without_losing_null_language_code(tmp_path, backend, module):
    if importlib.util.find_spec(module) is None:
        pytest.skip(f'{module} is not installed')
    env = os.environ.copy()
    env.update(CGC_RUNTIME_DB_TYPE=backend, CGC_RUNTIME_DB_PATH=str(tmp_path/'db'),
               PYTHONPATH=str(Path(__file__).resolve().parents[2]/'src'))
    script = '''
import os
from codegraphcontext.core import get_database_manager
from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools import report_generator
manager=get_database_manager(db_path=os.environ['CGC_RUNTIME_DB_PATH'])
try:
    with manager.get_driver().session() as session:
        for name,path in [('css_selector','/repo/style.css'),('html_selector','/repo/view.html'),
                          ('htm_selector','/repo/view.htm'),('calculate','/repo/work.py')]:
            session.run('CREATE (:Function {uid:$uid,name:$name,path:$path,line_number:1,is_dependency:false})',
                        uid=path,name=name,path=path)
    finder=CodeFinder(manager)
    for show_all in [False,True]:
        result=finder.find_dead_code(include_low_confidence=show_all)
        assert [r['function_name'] for r in result['potentially_unused_functions']]==['calculate'],result
    run=report_generator._run_cypher
    def checked(*args,**kwargs):
        rows=run(*args,**kwargs)
        assert not rows or '_error' not in rows[0], rows
        return rows
    report_generator._run_cypher=checked
    for scope in [None,'/repo']:
        report=report_generator._section_dead_code(finder.driver,repo_path=scope)
        assert 'calculate' in report,report
        assert 'selector' not in report,report
    assert report_generator._section_dead_code(finder.driver,repo_path='/absent')==''
finally:
    manager.close_driver()
'''
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
