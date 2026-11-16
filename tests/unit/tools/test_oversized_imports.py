import pytest

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
