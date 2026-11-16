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


CASES = [('nested_types',
  'package demo;\nclass Outer {\n class Inner { void run() { helper(); } }\n}\n',
  [('has', 'classes', 'Outer'),
   ('has', 'classes', 'Inner'),
   ('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('attr', 'function_calls', 'helper', 'class_context.0', 'Inner')]),
 ('generic_inheritance',
  'class Child extends Parent<String> implements A, B {}\n',
  [('has', 'classes', 'Child'), ('attr', 'classes', 'Child', 'bases', ['Parent<String>', 'A', 'B'])]),
 ('constructor',
  'class S { S(int x) { helper(x); } }\n',
  [('has', 'functions', 'S'), ('has', 'function_calls', 'helper')]),
 ('interface',
  'interface S { void run(); default void go() { run(); } }\n',
  [('has', 'interfaces', 'S'),
   ('has', 'functions', 'run'),
   ('has', 'functions', 'go'),
   ('has', 'function_calls', 'run')]),
 ('record',
  'record Point(int x, int y) { int sum() { return add(x,y); } }\n',
  [('has', 'classes', 'Point'),
   ('has', 'functions', 'sum'),
   ('has', 'function_calls', 'add'),
   ('attr', 'functions', 'sum', 'class_context', 'Point')]),
 ('static_import',
  'import static java.util.Collections.emptyList;\nclass S { void run() { emptyList(); } }\n',
  [('has', 'imports', 'java.util.Collections.emptyList'), ('has', 'function_calls', 'emptyList')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('java')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".java")
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


@pytest.mark.parametrize("source,name", [('record Point(int x, int y) { int sum() { return add(x,y); } }\n', 'Point')])
def test_prescan_keeps_declarations(tmp_path, source, name):
    from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
    path = tmp_path / "scan.java"
    path.write_text(source, encoding="utf-8")
    parser = TreeSitterParser('java')
    result = pre_scan_for_imports([path], {".java"}, lambda _: parser)
    assert name in result, result


def test_record_package_identity_prescan_and_call_owner(tmp_path):
    from codegraphcontext.tools.languages.java import pre_scan_java
    path = tmp_path / 'Point.java'
    path.write_text('package demo;\n// record Ghost(int x) {}\nrecord Point(int x) {\n int sum() { return helper(x); }\n}\n')
    parser = TreeSitterParser('java')
    data = parser.parse(path, index_source=True)
    record = next(c for c in data['classes'] if c['name'] == 'Point')
    assert record['qualified_name'] == 'demo.Point'
    assert record['line_number'] == 3
    call = next(c for c in data['function_calls'] if c['name'] == 'helper')
    assert call['class_context'] == ('Point', 3)
    prescan = pre_scan_java([path], parser)
    assert 'Point' in prescan and 'demo.Point' in prescan
    assert 'Ghost' not in prescan


@pytest.mark.parametrize("name,source", [('repeated_same_line', 'class S { void run() { helper(1); helper(2); } }\n'),
 ('nested_arguments', 'class S { void run() { helper(inner(1, 2), 3); } }\n')])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_invocation_identity_and_arguments(tmp_path, name, source, variant):
    parser = TreeSitterParser('java')
    if variant == "padded":
        source = '// π\n' + source
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / "calls.java"
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
