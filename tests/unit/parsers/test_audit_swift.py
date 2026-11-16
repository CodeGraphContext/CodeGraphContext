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


CASES = [('struct_method',
  'struct S {\n func run() { helper() }\n}\n',
  [('has', 'structs', 'S'),
   ('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('attr', 'function_calls', 'helper', 'class_context.0', 'S')]),
 ('protocol_signature',
  'protocol Draw {\n func draw(x: Int)\n}\n',
  [('has', 'traits', 'Draw'), ('has', 'functions', 'draw')]),
 ('extension',
  'extension String {\n func clean() { helper() }\n}\n',
  [('has', 'functions', 'clean'),
   ('has', 'function_calls', 'helper'),
   ('attr', 'functions', 'clean', 'class_context', 'String')]),
 ('init_deinit',
  'class S {\n init() { setup() }\n deinit { cleanup() }\n}\n',
  [('has', 'functions', 'init'),
   ('has', 'functions', 'deinit'),
   ('has', 'function_calls', 'setup'),
   ('has', 'function_calls', 'cleanup')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('swift')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".swift")
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


def test_initializer_and_deinitializer_calls_keep_distinct_owners(tmp_path):
    path = tmp_path / 'lifetime.swift'
    path.write_text('class S {\n init() { setup() }\n deinit { cleanup() }\n}\n')
    result = TreeSitterParser('swift').parse(path)
    calls = {c['name']: c for c in result['function_calls']}
    assert calls['setup']['context'][0] == 'init'
    assert calls['cleanup']['context'][0] == 'deinit'
    assert calls['cleanup']['class_context'] == ('S', 1)


def test_requirement_stays_indexed_but_default_implementation_receives_the_call(tmp_path):
    from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
    path = tmp_path / 'default.swift'
    path.write_text('protocol Draw { func draw() }\nextension Draw { func draw() {} }\nfunc run(x: Draw) { x.draw() }\n')
    result = TreeSitterParser('swift').parse(path)
    assert len([f for f in result['functions'] if f['name'] == 'draw']) == 2
    edges, *_ = build_function_call_groups([result], {})
    calls = [e for e in edges if e['caller_name'] == 'run' and e['called_name'] == 'draw']
    assert len(calls) == 1 and calls[0]['called_line_number'] == 2


def test_parameter_types_and_internal_labels_drive_receiver_resolution(tmp_path):
    path = tmp_path / 'labels.swift'
    path.write_text('class S { func work() {} }\nfunc run(_ service: S) { service.work() }\n')
    result = TreeSitterParser('swift').parse(path)
    assert next(f for f in result['functions'] if f['name'] == 'run')['args'] == ['service']
    assert next(v for v in result['variables'] if v['name'] == 'service')['type'] == 'S'


@pytest.mark.parametrize("name,source", [('repeated_same_line', 'func run() { helper(1); helper(2); }\n'),
 ('nested_arguments', 'func run() { helper(inner(1, 2), 3); }\n')])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_invocation_identity_and_arguments(tmp_path, name, source, variant):
    parser = TreeSitterParser('swift')
    if variant == "padded":
        source = '// π\n' + source
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / "calls.swift"
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


def test_prescan_indexes_top_level_functions_without_comment_or_member_phantoms(tmp_path):
    from codegraphcontext.tools.languages.swift import pre_scan_swift
    path = tmp_path / 'scan.swift'
    path.write_text('// class Ghost {}\nfunc run() { func inner() {} }\nclass S { func member() {} }\n')
    scan = pre_scan_swift([path], TreeSitterParser('swift'))
    assert {'run', 'S'} <= scan.keys()
    assert not {'inner', 'member', 'Ghost'} & scan.keys()
