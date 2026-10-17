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


CASES = [('nested_context',
  'namespace Demo { class Outer { class Inner { void Run() { Helper(); } } } }\n',
  [('has', 'classes', 'Outer'),
   ('has', 'classes', 'Inner'),
   ('has', 'functions', 'Run'),
   ('has', 'function_calls', 'Helper'),
   ('attr', 'function_calls', 'Helper', 'class_context.0', 'Inner')]),
 ('record',
  'record Point(int X, int Y) { int Sum() => Add(X, Y); }\n',
  [('has', 'records', 'Point'), ('has', 'functions', 'Sum'), ('has', 'function_calls', 'Add')]),
 ('local_function',
  'class S { void Outer() { void Inner() { Helper(); } Inner(); } }\n',
  [('has', 'functions', 'Outer'),
   ('has', 'functions', 'Inner'),
   ('has', 'function_calls', 'Helper'),
   ('has', 'function_calls', 'Inner'),
   ('attr', 'function_calls', 'Helper', 'context.0', 'Inner')]),
 ('generic_bases',
  'class Child : Map<string, int>, IOne, ITwo {}\n',
  [('has', 'classes', 'Child'), ('attr', 'classes', 'Child', 'bases', ['Map<string, int>', 'IOne', 'ITwo'])]),
 ('constructor',
  'class S { public S(int x) { Helper(x); } }\n',
  [('has', 'functions', 'S'), ('has', 'function_calls', 'Helper')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('c_sharp')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".cs")
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


def test_nested_local_functions_keep_the_nearest_owner(tmp_path):
    path = tmp_path / 'owner.cs'
    path.write_text('class S {\n void Outer() {\n  void Inner() {\n   void Deep() { Helper(); }\n   Deep();\n  }\n  Inner();\n }\n}\n')
    result = TreeSitterParser('c_sharp').parse(path)
    calls = {c['name']: c for c in result['function_calls']}
    assert calls['Helper']['context'][0] == 'Deep'
    assert calls['Deep']['context'][0] == 'Inner'
    assert calls['Inner']['context'][0] == 'Outer'
    assert calls['Helper']['class_context'][0] == 'S'
