import pytest
from unittest.mock import MagicMock

from codegraphcontext.tools.indexing.persistence.writer import build_import_rows, build_module_inclusion_rows
from codegraphcontext.tools.indexing.sanitize import MAX_STR_LEN
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser


@pytest.mark.parametrize('value', ['', '  ', '#section', 'data:image/png;base64,' + 'a' * 10000,
                                   'DATA:text/plain,hello', 'javascript:alert(1)', 'mailto:a@b',
                                   'tel:123', 'blob:https://example.com/id', 'about:blank'])
def test_inline_html_values_are_not_modules(tmp_path, value):
    path = tmp_path / 'report.html'
    path.write_text(f'<img src="{value}"><script src="app.js"></script>')
    imports = TreeSitterParser('html').parse(path)['imports']
    assert [row['name'] for row in imports] == ['app.js']


@pytest.mark.parametrize('lang', ['javascript', 'typescript', 'python', 'ruby', 'html'])
@pytest.mark.parametrize('prefix', ['x' * (MAX_STR_LEN + 1), '😀' * (MAX_STR_LEN // 4 + 1)])
def test_oversized_import_identities_are_skipped_without_collisions(lang, prefix, monkeypatch):
    warnings = []
    monkeypatch.setattr('codegraphcontext.tools.indexing.persistence.writer.warning_logger', warnings.append)
    records = [{'name': name, 'source': name, 'lang': lang, 'line_number': i}
               for i, name in enumerate([prefix + 'a', prefix + 'b', 'valid-module'])]
    assert [row['name'] for row in build_import_rows(records, lang)] == ['valid-module']
    assert len(warnings) == 2
    assert all('UTF-8 bytes' in message for message in warnings)


def test_inclusions_share_the_module_guard_and_properties_are_sanitized():
    rows = build_module_inclusion_rows([
        {'class': 'Example', 'module': 'x' * (MAX_STR_LEN + 1)},
        {'class': 'Example', 'module': 'Valid'},
    ])
    assert rows == [{'class_name': 'Example', 'module_name': 'Valid'}]
    row = build_import_rows([{'name': 'Valid', 'source': 'Valid', 'alias': 'x' * 10000}], 'python')[0]
    assert len(row['alias']) == MAX_STR_LEN


@pytest.mark.parametrize('name', ['data', 'about', 'tel', 'blob', 'mailto', 'javascript'])
def test_relative_resources_that_resemble_schemes_are_retained(tmp_path, name):
    path = tmp_path / 'index.html'
    path.write_text(f'<a href="{name}">link</a>')
    assert [row['name'] for row in TreeSitterParser('html').parse(path)['imports']] == [name]


def test_an_entirely_rejected_inclusion_batch_is_not_sent_to_the_database(tmp_path, monkeypatch):
    from codegraphcontext.tools.indexing.persistence import writer as module
    session = MagicMock()
    monkeypatch.setattr(module, 'execute_write_operation', lambda driver, backend, operation: operation(session))
    monkeypatch.setattr(module, 'get_backend_type', lambda *args: 'kuzudb')
    graph_writer = module.GraphWriter(MagicMock())
    path = tmp_path / 'example.rb'
    path.write_text('class Example; end')
    graph_writer.add_file_to_graph({'path': str(path), 'repo_path': str(tmp_path), 'lang': 'ruby',
                                   'module_inclusions': [{'class': 'Example', 'module': 'x' * (MAX_STR_LEN + 1)}]},
                                  tmp_path.name, {}, repo_path_str=str(tmp_path))
    assert not any('INCLUDES' in call.args[0] for call in session.run.call_args_list)
