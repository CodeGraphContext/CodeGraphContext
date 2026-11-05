"""Semantic regression oracles from the installed-checkout language audit."""
import pytest
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser


def _field(record, key):
    current = record
    for part in key.split("."):
        if isinstance(current, (list, tuple)) and part.isdigit():
            current = current[int(part)] if int(part) < len(current) else None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


CASES = [('selectors_variables',
  '.one, #main, button { --accent: red; color: var(--accent); }\n',
  [('has', 'functions', '.one'),
   ('has', 'functions', '#main'),
   ('has', 'functions', 'button'),
   ('has', 'variables', '--accent'),
   ('attr', 'variables', '--accent', 'value', 'red')]),
 ('import_string', '@import "base.css";\n', [('has', 'imports', 'base.css')]),
 ('import_url',
  '@import url("base.css");\n@import url(theme.css);\n',
  [('has', 'imports', 'base.css'), ('has', 'imports', 'theme.css')]),
 ('nested_media', '@media (width > 10px) { .one { color: red; } }\n', [('has', 'functions', '.one')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('css')
    offset = 0
    if variant == "padded":
        source = '/* audit π */\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".css")
    path.write_bytes(source.encode("utf-8"))
    if variant == "reuse":
        parser.parse(path, index_source=True, is_dependency=True)
    result = parser.parse(path, index_source=variant == "dependency_source", is_dependency=variant == "dependency_source")
    assert not result.get("error"), result
    assert result["is_dependency"] == (variant == "dependency_source")
    for op, bucket, name, *rest in checks:
        rows = [r for r in result.get(bucket, []) if r.get("name") == name]
        if op == "has":
            assert rows, (bucket, name, result.get(bucket))
        elif op == "absent":
            assert not rows, (bucket, name, rows)
        elif op == "count":
            assert len(rows) == rest[0], rows
        elif op == "attr":
            key, expected = rest
            if key == "line_number":
                expected += offset
            assert any(_field(r, key) == expected for r in rows), (name, key, expected, rows)


def test_urls_in_declarations_and_comments_are_not_imports(tmp_path):
    path = tmp_path / 'style.css'
    path.write_text('/* @import url("ghost.css"); */\n.x { background: url("image.png"); }\n@import URL("real.css") screen;\n')
    result = TreeSitterParser('css').parse(path)
    assert [(i['name'], i['line_number']) for i in result['imports']] == [('real.css', 3)]
