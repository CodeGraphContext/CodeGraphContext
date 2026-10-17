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


CASES = [('extension',
  'fun String.clean(): String = trim()\n',
  [('has', 'functions', 'clean'), ('has', 'function_calls', 'trim')]),
 ('nested_context',
  'class Outer {\n class Inner { fun run() { helper() } }\n}\n',
  [('has', 'classes', 'Outer'),
   ('has', 'classes', 'Inner'),
   ('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('attr', 'function_calls', 'helper', 'class_context.0', 'Inner')]),
 ('companion',
  'class S {\n companion object {\n  fun build() = S()\n }\n}\n',
  [('has', 'classes', 'S'), ('has', 'functions', 'build'), ('has', 'function_calls', 'S')]),
 ('destructuring',
  'fun run() { val (first, second) = pair() }\n',
  [('has', 'functions', 'run'),
   ('has', 'variables', 'first'),
   ('has', 'variables', 'second'),
   ('has', 'function_calls', 'pair')]),
 ('interface',
  'interface Draw { fun draw() }\n',
  [('has', 'interfaces', 'Draw'), ('has', 'functions', 'draw')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('kotlin')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".kt")
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


def test_multiline_destructuring_skips_placeholders_and_keeps_scope(tmp_path):
    path = tmp_path / 'bindings.kt'
    path.write_text('fun run() {\n val (first, _, third) = Triple(1, 2, 3)\n}\n')
    result = TreeSitterParser('kotlin').parse(path)
    bindings = [v for v in result['variables'] if v['name'] in {'first', '_', 'third'}]
    assert {v['name'] for v in bindings} == {'first', 'third'}
    assert len(bindings) == 2
    assert all(v['context'] == 'run' and v['line_number'] == 2 for v in bindings)
    assert all(v['type'] == 'Unknown' for v in bindings)
