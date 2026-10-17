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


CASES = [('pointer_returns',
  'int *build(int x) { helper(x); return 0; }\n',
  [('has', 'functions', 'build'), ('has', 'function_calls', 'helper'), ('absent', 'functions', 'x')]),
 ('function_pointer',
  'int run(int (*cb)(int), int x) { return cb(x); }\n',
  [('has', 'functions', 'run'), ('has', 'function_calls', 'cb'), ('absent', 'functions', 'cb')]),
 ('nested_calls',
  'int run(void) { return outer(inner(1), inner(2)); }\n',
  [('has', 'function_calls', 'outer'),
   ('has', 'function_calls', 'inner'),
   ('count', 'function_calls', 'inner', 2)]),
 ('prototypes',
  'int helper(int x);\nint run(void) { return helper(1); }\n',
  [('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('count', 'function_calls', 'helper', 1)]),
 ('namespaces',
  'namespace demo {\nclass Service { public: void run() { helper(); } };\n}\n',
  [('has', 'classes', 'Service'),
   ('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('attr', 'functions', 'run', 'class_context', 'Service')]),
 ('constructor_destructor',
  'class S { public: S() { init(); } ~S() { cleanup(); } };\n',
  [('has', 'functions', 'S'),
   ('has', 'functions', '~S'),
   ('has', 'function_calls', 'init'),
   ('has', 'function_calls', 'cleanup')]),
 ('generic_call',
  'void run() { identity<int>(1); }\n',
  [('has', 'functions', 'run'), ('has', 'function_calls', 'identity')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('cpp')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".cpp")
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


def test_template_member_scoped_calls_and_destructor_owner(tmp_path):
    path = tmp_path / 'template.cpp'
    path.write_text('class S { public: ~S() { cleanup(); } };\nvoid run() { obj.method<int>(2); N::identity<int>(3); }\n')
    result = TreeSitterParser('cpp').parse(path)
    calls = {c['name']: c for c in result['function_calls']}
    assert calls['cleanup']['context'][0] == '~S'
    assert calls['method']['args'] == ['2']
    assert calls['identity']['args'] == ['3']
    assert calls['identity']['inferred_obj_type'] == 'N'
