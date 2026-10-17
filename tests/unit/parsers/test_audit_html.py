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


CASES = [('quoted_attributes',
  '<div id="main" class="one two"></div>\n'
  '<script src="app.js"></script>\n'
  '<link href="app.css" rel="stylesheet">\n',
  [('has', 'classes', 'one'),
   ('has', 'classes', 'two'),
   ('has', 'variables', 'main'),
   ('has', 'imports', 'app.js'),
   ('has', 'imports', 'app.css')]),
 ('unquoted_attributes',
  '<div id=main class=one></div>\n<script src=app.js></script>\n<link href=app.css rel=stylesheet>\n',
  [('has', 'classes', 'one'),
   ('has', 'variables', 'main'),
   ('has', 'imports', 'app.js'),
   ('has', 'imports', 'app.css')]),
 ('void_selfclosing_tags',
  '<img src="x.png" />\n<input id="email">\n<br>\n',
  [('has', 'tags', 'img'),
   ('has', 'tags', 'input'),
   ('has', 'tags', 'br'),
   ('has', 'imports', 'x.png'),
   ('has', 'variables', 'email')]),
 ('upper_case',
  '<DIV CLASS="one" ID="main"></DIV>\n',
  [('has', 'classes', 'one'), ('has', 'variables', 'main'), ('has', 'tags', 'div')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('html')
    offset = 0
    if variant == "padded":
        source = '<!-- audit π -->\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".html")
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


def test_attribute_forms_preserve_locations_and_deduplicate_classes(tmp_path):
    path = tmp_path / 'index.html'
    path.write_text('<div class=one id=main></div>\n<img class="one two" src=image.png />\n<script src="app.js"></script>\n')
    result = TreeSitterParser('html').parse(path)
    assert [(c['name'], c['line_number']) for c in result['classes']] == [('one', 1), ('two', 2)]
    assert {(i['name'], i['line_number']) for i in result['imports']} == {('image.png', 2), ('app.js', 3)}
    assert {(t['name'], t['line_number']) for t in result['tags']} == {('div', 1), ('img', 2), ('script', 3)}
