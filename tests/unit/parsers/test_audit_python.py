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


CASES = [('nested_async',
  'async def outer(x):\n    def inner(y):\n        return helper(y)\n    return inner(x)\n',
  [('has', 'functions', 'outer'),
   ('has', 'functions', 'inner'),
   ('has', 'function_calls', 'helper'),
   ('has', 'function_calls', 'inner'),
   ('attr', 'function_calls', 'helper', 'context.0', 'inner')]),
 ('decorated_class',
  '@decorate\nclass Child(Base):\n    @staticmethod\n    def run(x):\n        return helper(x)\n',
  [('has', 'classes', 'Child'),
   ('has', 'functions', 'run'),
   ('attr', 'classes', 'Child', 'bases', ['Base']),
   ('attr', 'functions', 'run', 'line_number', 4)]),
 ('import_bindings',
  'import os.path as path\nfrom ..pkg import one as first, two\n',
  [('has', 'imports', 'os.path'),
   ('has', 'imports', 'one'),
   ('has', 'imports', 'two'),
   ('attr', 'imports', 'one', 'alias', 'first'),
   ('attr', 'imports', 'one', 'full_import_name', '..pkg.one')]),
 ('destructuring',
  'a, (b, c) = (1, (2, 3))\n',
  [('has', 'variables', 'a'), ('has', 'variables', 'b'), ('has', 'variables', 'c')]),
 ('lambda_owner',
  'def outer():\n    cb = lambda x: helper(x)\n    return cb(1)\n',
  [('has', 'functions', 'outer'),
   ('has', 'functions', 'cb'),
   ('has', 'function_calls', 'helper'),
   ('has', 'function_calls', 'cb'),
   ('attr', 'function_calls', 'helper', 'context.0', 'cb')]),
 ('annotations_are_not_calls',
  'def run(x: list[int]) -> str:\n    return helper(x)\n',
  [('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('absent', 'function_calls', 'list'),
   ('absent', 'function_calls', 'str')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('python')
    offset = 0
    if variant == "padded":
        source = '# audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".py")
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


def test_unpacking_does_not_declare_attribute_or_subscript_receivers(tmp_path):
    path = tmp_path / 'bindings.py'
    path.write_text('a, (b, *rest) = values\nobj.attr, items[0] = pair\n')
    result = TreeSitterParser('python').parse(path)
    assert {v['name'] for v in result['variables']} == {'a', 'b', 'rest'}


def test_lambda_call_owner_resolves_to_the_lambda_function(tmp_path):
    from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
    path = tmp_path / 'owner.py'
    path.write_text('def helper(x): return x\ndef outer():\n cb = lambda x: helper(x)\n return cb(1)\n')
    data = TreeSitterParser('python').parse(path)
    edges, *_ = build_function_call_groups([data], {})
    pairs = {(e['caller_name'], e['called_name']) for e in edges}
    assert ('cb', 'helper') in pairs
    assert ('outer', 'helper') not in pairs
