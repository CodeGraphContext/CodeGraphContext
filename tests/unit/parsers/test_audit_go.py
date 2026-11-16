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


CASES = [('receiver',
  'package demo\n'
  'type Service struct {}\n'
  'func (s *Service) Run(x int) int { return helper(x) }\n'
  'func helper(x int) int { return x }\n',
  [('has', 'functions', 'Run'),
   ('has', 'functions', 'helper'),
   ('has', 'structs', 'Service'),
   ('has', 'function_calls', 'helper'),
   ('attr', 'functions', 'Run', 'class_context', 'Service')]),
 ('imports_aliases',
  'package demo\nimport (\n alias "example.com/one"\n "fmt"\n)\n',
  [('has', 'imports', 'one'), ('has', 'imports', 'fmt'), ('attr', 'imports', 'one', 'alias', 'alias')]),
 ('generic_invocation',
  'package demo\nfunc run() { identity[int](1) }\n',
  [('has', 'functions', 'run'), ('has', 'function_calls', 'identity')]),
 ('closure_owner',
  'package demo\nfunc outer() {\n inner := func() { helper() }\n inner()\n}\n',
  [('has', 'functions', 'outer'),
   ('has', 'functions', 'inner'),
   ('has', 'function_calls', 'helper'),
   ('has', 'function_calls', 'inner'),
   ('attr', 'function_calls', 'helper', 'context.0', 'inner')]),
 ('interface',
  'package demo\ntype Reader interface { Read(p []byte) (int, error) }\n',
  [('has', 'interfaces', 'Reader')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('go')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".go")
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


def test_generic_candidates_resolve_across_files_without_turning_casts_into_calls(tmp_path):
    from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
    helper = tmp_path / 'helper.go'
    helper.write_text('package demo\nfunc identity[T any](x T) T { return x }\n')
    caller = tmp_path / 'main.go'
    caller.write_text('package demo\ntype Box[T any] []T\nfunc run() { identity[int](1); identity[int](2); Box[int](nil) }\n')
    parser = TreeSitterParser('go')
    data = [parser.parse(helper), parser.parse(caller)]
    candidates = [c for c in data[1]['function_calls'] if c['name'] == 'identity']
    assert [c['args'] for c in candidates] == [['1'], ['2']]
    assert 'Box' not in {c['name'] for c in data[1]['function_calls']}
    edges, *_ = build_function_call_groups(data, {'identity': [str(helper)]})
    matches = [e for e in edges if e['caller_name'] == 'run' and e['called_name'] == 'identity']
    assert len(matches) == 2


def test_unknown_generic_candidate_does_not_invent_an_edge(tmp_path):
    from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
    path = tmp_path / 'unknown.go'
    path.write_text('package demo\nfunc run() { Unknown[int](value) }\n')
    result = TreeSitterParser('go').parse(path)
    assert result['function_calls'][0]['call_kind'] == 'generic_or_conversion'
    assert not build_function_call_groups([result], {})[0]


@pytest.mark.parametrize("name,source", [('repeated_same_line', 'package demo\nfunc run() { helper(1); helper(2); }\n'),
 ('nested_arguments', 'package demo\nfunc run() { helper(inner(1, 2), 3); }\n')])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_invocation_identity_and_arguments(tmp_path, name, source, variant):
    parser = TreeSitterParser('go')
    if variant == "padded":
        source = '// π\n' + source
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / "calls.go"
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
