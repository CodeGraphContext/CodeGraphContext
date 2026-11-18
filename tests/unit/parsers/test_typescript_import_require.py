"""A TypeScript import-equals declaration must not discard its file (#1845)."""
import pytest

from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser


@pytest.mark.parametrize('language,suffix', [('typescript', '.ts'), ('tsx', '.tsx')])
@pytest.mark.parametrize('type_modifier', ['', 'type '])
def test_import_equals_preserves_bindings_and_rest_of_file(tmp_path, language, suffix, type_modifier):
    source = tmp_path / ('entry' + suffix)
    source.write_text(
        f"import {type_modifier}fs = require('node:fs');\n"
        "import local = require('./local');\n"
        "import { helper } from './helper';\n"
        "export function main() { return helper(); }\n",
        encoding='utf-8',
    )
    result = TreeSitterParser(language).parse(source)
    assert 'error' not in result, result
    assert {f['name'] for f in result['functions']} == {'main'}
    assert {(i['source'], i['alias']) for i in result['imports']} == {
        ('node:fs', 'fs'), ('./local', 'local'), ('./helper', None),
    }
    assert {c['name'] for c in result['function_calls']} == {'helper'}


@pytest.mark.parametrize('language,suffix', [('typescript', '.ts'), ('tsx', '.tsx')])
def test_incomplete_import_during_edit_does_not_discard_following_function(tmp_path, language, suffix):
    source = tmp_path / ('entry' + suffix)
    source.write_text('import fs;\nexport function main() {}\n', encoding='utf-8')
    result = TreeSitterParser(language).parse(source)
    assert 'error' not in result, result
    assert 'main' in {f['name'] for f in result['functions']}
