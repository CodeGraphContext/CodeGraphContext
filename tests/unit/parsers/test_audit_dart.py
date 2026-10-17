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


CASES = [('class_methods',
  'class S {\n void run() { helper(); }\n}\n',
  [('has', 'classes', 'S'), ('has', 'functions', 'run'), ('has', 'function_calls', 'helper')]),
 ('expression_function',
  'int add(int x, int y) => helper(x, y);\n',
  [('has', 'functions', 'add'), ('has', 'function_calls', 'helper')]),
 ('constructors',
  'class S {\n S() { setup(); }\n S.named() { setup(); }\n}\n',
  [('has', 'classes', 'S'),
   ('has', 'functions', 'S'),
   ('has', 'functions', 'S.named'),
   ('has', 'function_calls', 'setup')]),
 ('import_alias',
  "import 'dart:math' as math;\n",
  [('has', 'imports', 'dart:math'), ('attr', 'imports', 'dart:math', 'alias', 'math')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('dart')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".dart")
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


def test_named_constructor_body_calls_have_the_named_owner(tmp_path):
    path = tmp_path / 'constructors.dart'
    path.write_text('class S {\n S.named() { helper(); }\n factory S.create() => S.named();\n}\n')
    result = TreeSitterParser('dart').parse(path)
    assert {'S.named', 'S.create'} <= {f['name'] for f in result['functions']}
    helper = next(c for c in result['function_calls'] if c['name'] == 'helper')
    assert helper['context'][0] == 'S.named'
