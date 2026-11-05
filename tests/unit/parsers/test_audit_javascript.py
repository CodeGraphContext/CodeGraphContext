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


CASES = [('nested_arrows',
  'function outer() {\n  const inner = (x) => helper(x);\n  return inner(1);\n}\n',
  [('has', 'functions', 'outer'),
   ('has', 'functions', 'inner'),
   ('has', 'function_calls', 'helper'),
   ('has', 'function_calls', 'inner'),
   ('attr', 'function_calls', 'helper', 'context.0', 'inner')]),
 ('function_expression',
  'const build = function named(x) { return helper(x); };\n',
  [('has', 'functions', 'build'), ('has', 'function_calls', 'helper')]),
 ('class_methods',
  'class Child extends Base {\n'
  '  run(x) { return this.helper(x); }\n'
  '  static build() { return new Child(); }\n'
  '}\n',
  [('has', 'classes', 'Child'),
   ('has', 'functions', 'run'),
   ('has', 'functions', 'build'),
   ('has', 'function_calls', 'helper'),
   ('has', 'function_calls', 'Child'),
   ('attr', 'function_calls', 'helper', 'class_context.0', 'Child')]),
 ('imports',
  "import main, {one as first, two} from './lib';\nimport * as ns from './other';\n",
  [('has', 'imports', 'default'),
   ('has', 'imports', 'one'),
   ('has', 'imports', 'two'),
   ('has', 'imports', '*'),
   ('attr', 'imports', 'one', 'alias', 'first'),
   ('attr', 'imports', 'one', 'source', './lib'),
   ('attr', 'imports', 'default', 'alias', 'main'),
   ('attr', 'imports', '*', 'alias', 'ns')]),
 ('destructure',
  'const {one: first, two, ...rest} = input;\nconst [a, b] = values;\n',
  [('has', 'variables', 'first'),
   ('has', 'variables', 'two'),
   ('has', 'variables', 'rest'),
   ('has', 'variables', 'a'),
   ('has', 'variables', 'b'),
   ('absent', 'variables', 'one')]),
 ('optional_calls',
  'function run(obj) { obj?.work?.(1); obj.work(2); }\n',
  [('has', 'functions', 'run'), ('count', 'function_calls', 'work', 2)]),
 ('template_and_comments',
  "const text = 'fake()';\n// phantom()\nfunction run() { return `${helper()}`; }\n",
  [('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('absent', 'function_calls', 'fake'),
   ('absent', 'function_calls', 'phantom')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('javascript')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".js")
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


def test_nested_binding_defaults_and_keys_are_not_variables(tmp_path):
    path = tmp_path / 'bindings.js'
    path.write_text('const {[key()]: local = fallback(), nested: {x}, ...rest} = input;\nconst [a = initial(),, ...tail] = values;\n')
    result = TreeSitterParser('javascript').parse(path)
    assert {v['name'] for v in result['variables']} == {'local', 'x', 'rest', 'a', 'tail'}
    assert {'key', 'fallback', 'initial'} <= {c['name'] for c in result['function_calls']}


@pytest.mark.parametrize("name,source", [('repeated_same_line', 'function run() { helper(1); helper(2); }\n'),
 ('nested_arguments', 'function run() { helper(inner(1, 2), 3); }\n')])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_invocation_identity_and_arguments(tmp_path, name, source, variant):
    parser = TreeSitterParser('javascript')
    if variant == "padded":
        source = '// π\n' + source
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / "calls.javascript"
    path.write_bytes(source.encode("utf-8"))
    if variant == "reuse":
        parser.parse(path, index_source=True)
    result = parser.parse(path, is_dependency=variant == "dependency_source", index_source=variant == "dependency_source")
    calls = [c for c in result["function_calls"] if c["name"] == "helper"]
    if name == "repeated_same_line":
        assert len(calls) == 2, calls
    else:
        assert len(calls) == 1, calls
        assert calls[0]["args"] == ['inner(1, 2)', "3"], calls
