"""Repository spelling and concurrent graph choices must not change the answer."""
import ast
import inspect
import threading
import textwrap
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.code_finder import CodeFinder


def test_concurrent_calls_keep_their_own_graph_during_repository_lookup(monkeypatch):
    logs = []
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value.run.return_value.data.return_value = [
        {'name': 'shop', 'path': '/repo/shop'},
    ]

    def get_driver(graph_name=None):
        logs.append((threading.current_thread().name, graph_name))
        return driver

    finder = CodeFinder(SimpleNamespace(get_backend_type=lambda: 'falkordb', get_driver=get_driver))
    ready, done = threading.Event(), threading.Event()
    normalize = finder._normalize_repo_path_filter

    def held(path):
        if threading.current_thread().name.endswith('_0'):
            ready.set()
            assert done.wait(5)
        return normalize(path)

    monkeypatch.setattr(finder, '_normalize_repo_path_filter', held)

    def second():
        assert ready.wait(5)
        try:
            finder.list_indexed_repositories(graph_name='graph_b')
        finally:
            done.set()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='scope') as pool:
        first = pool.submit(finder.find_most_complex_functions, 5, repo_path='shop', graph_name='graph_a')
        other = pool.submit(second)
        first.result(timeout=10)
        other.result(timeout=10)
    assert [g for who, g in logs if who.endswith('_0')] == ['graph_a', 'graph_a']
    assert [g for who, g in logs if who.endswith('_1')] == ['graph_b']
    finder.list_indexed_repositories()
    assert logs[-1][1] is None


@pytest.mark.parametrize('method,args', [
    ('find_by_function_name', ('compute_total', False)),
    ('find_by_class_name', ('Cart', False)),
    ('find_by_variable_name', ('TAX_RATE',)),
    ('find_by_content', ('price',)),
])
def test_direct_searches_resolve_all_repository_spellings(tmp_path, monkeypatch, method, args):
    pytest.importorskip('kuzu')
    manager = KuzuDBManager(str(tmp_path / 'db'))
    root = (tmp_path / 'shop').as_posix()
    finder = CodeFinder(SimpleNamespace(get_backend_type=lambda: 'kuzudb', get_driver=lambda *a: manager.get_driver()))
    monkeypatch.setattr(finder, 'list_indexed_repositories', lambda **kw: [{'name': 'graph_alias', 'path': root}])
    monkeypatch.chdir(tmp_path)
    try:
        with manager.get_driver().session() as session:
            for repo in [root, root + '-old']:
                for label, name in [('Function', 'compute_total'), ('Class', 'Cart'), ('Variable', 'TAX_RATE')]:
                    session.run(f'CREATE (n:{label} {{uid:$uid,name:$name,path:$path,line_number:1,source:$source,is_dependency:false}})',
                                uid=repo+name, name=name, path=repo+'/a.py', source='price')
        results = [getattr(finder, method)(*args, repo_path=spelling)
                   for spelling in ['graph_alias', 'shop', 'shop/', root, './shop']]
        assert all(rows == results[0] for rows in results)
        assert results[0]
        assert {row['path'] for row in results[0]} == {root+'/a.py'}
    finally:
        manager.close_driver()


def test_all_public_repository_scoped_methods_normalize():
    methods = [n for n in ast.parse(textwrap.dedent(inspect.getsource(CodeFinder))).body[0].body
               if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')
               and 'repo_path' in {a.arg for a in n.args.args + n.args.kwonlyargs}]
    allow = {'format_query': 'Formats query text only; callers bind the normalized parameter.'}
    assert {'find_by_content', 'find_by_class_name', 'find_by_variable_name', 'find_by_function_name'} <= {n.name for n in methods}
    offenders = [n.name for n in methods if n.name not in allow and not any(
        isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
        and c.func.attr in {'_normalize_repo_path_filter', '_repo_path_prefix'} for c in ast.walk(n))]
    assert not offenders, offenders
    assert not any(isinstance(n, ast.Attribute) and n.attr == '_active_graph'
                   for n in ast.walk(ast.parse(textwrap.dedent(inspect.getsource(CodeFinder)))))
