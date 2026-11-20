from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.code_finder import CodeFinder, _escape_lucene, _lucene_query


@pytest.fixture
def finder():
    manager = MagicMock()
    manager.get_backend_type.return_value = 'neo4j'
    session = manager.get_driver.return_value.session.return_value.__enter__.return_value
    session.run.return_value.data.return_value = []
    return CodeFinder(manager), session


@pytest.mark.parametrize('char', list('+-&|!(){}[]^"~*?:\\/'))
def test_lucene_metacharacters_are_literal(char):
    assert _escape_lucene('x' + char) == 'x\\' + char


def test_only_whole_operator_words_are_lowercased():
    assert _escape_lucene('AND OR NOT TO ANDROID NOTIFY') == 'and or not to ANDROID NOTIFY'


@pytest.mark.parametrize('query,expected', [('apply_route(', r'apply_route\('), ('NOT', 'not'),
                                           ('[x]', r'\[x\]'), ('src/app', r'src\/app')])
def test_content_query_escapes_code_at_database_boundary(finder, query, expected):
    code, session = finder
    code.find_by_content(query)
    assert session.run.call_args.kwargs['search_term'] == expected


@pytest.mark.parametrize('method', ['find_by_function_name', 'find_by_class_name'])
def test_fuzzy_names_escape_each_token_before_adding_modifiers(finder, method):
    code, session = finder
    getattr(code, method)('apply_route(', True)
    assert session.run.call_args.kwargs['search_term'] == r'name:apply_route\(~2'


@pytest.mark.parametrize('query', ['', '  ', '(', '[]', '\\', '&& ||'])
def test_no_terms_never_reach_lucene(finder, query):
    code, session = finder
    assert code.find_by_content(query) == []
    assert code.find_by_function_name(query, True) == []
    assert code.find_by_class_name(query, True) == []
    session.run.assert_not_called()


def test_related_code_escapes_exactly_once_and_keeps_exact_names_raw(finder):
    code, session = finder
    code.find_related_code('apply_route(', fuzzy_search=False, edit_distance=2)
    calls = session.run.call_args_list
    assert calls[0].kwargs['name'] == 'apply_route('
    assert calls[-1].kwargs['search_term'] == r'apply_route\('
    session.run.reset_mock()
    code.find_related_code('apply_route(', fuzzy_search=True, edit_distance=2)
    assert session.run.call_args_list[0].kwargs['search_term'] == r'name:apply_route\(~2'
    assert session.run.call_args.kwargs['search_term'] == r'apply_route\(~2'
    assert _lucene_query('NOT', 2) == 'not~2'


@pytest.mark.parametrize('query,expected', [('[x]', r'\[x\]~2'), ('src/app', r'src\/app~2'),
                                           ('AND OR NOT', 'and~2 or~2 not~2'), ('foo_bar', 'foo_bar~2')])
def test_fuzzy_content_preserves_identifier_tokens_and_escapes_literals(finder, query, expected):
    code, session = finder
    code.find_by_content(query, fuzzy_search=True)
    assert session.run.call_args.kwargs['search_term'] == expected


@pytest.mark.parametrize('distance,expected', [(1.5, 1), (-1, 0), (10, 2), ('bad', 2),
                                              (float('nan'), 2), (float('inf'), 2)])
def test_fuzzy_distance_is_an_integer_within_lucene_bounds(finder, distance, expected):
    code, session = finder
    code.find_by_function_name('foo_bar', True, edit_distance=distance)
    assert session.run.call_args.kwargs['search_term'] == f'name:foo_bar~{expected}'


def test_combined_search_retains_name_matches_when_content_lookup_fails(finder, monkeypatch):
    from codegraphcontext.tools.handlers.analysis_handlers import find_code
    code, _ = finder
    monkeypatch.setattr(code, 'find_by_function_name', lambda *args: [{'name': 'foo_bar', 'is_dependency': False}])
    monkeypatch.setattr(code, 'find_by_class_name', lambda *args: [])
    monkeypatch.setattr(code, 'find_by_variable_name', lambda *args: [])
    monkeypatch.setattr(code, 'find_by_content', MagicMock(side_effect=RuntimeError('index is populating')))
    response = find_code(code, query='foo_bar')
    assert response['results']['content_matches'] == []
    assert response['results']['content_error'] == 'index is populating'
    assert response['results']['ranked_results'][0]['name'] == 'foo_bar'


def test_content_timeouts_are_not_downgraded_to_partial_success(finder, monkeypatch):
    from codegraphcontext.core.read_timeout import ReadQueryTimeout
    code, _ = finder
    monkeypatch.setattr(code, 'find_by_content', MagicMock(side_effect=ReadQueryTimeout('find_code', 1)))
    with pytest.raises(ReadQueryTimeout):
        code.find_related_code('foo_bar', False, 2)
