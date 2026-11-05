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


CASES = [('module_functions',
  'defmodule Demo do\n def run(x), do: helper(x)\n defp helper(x), do: x\nend\n',
  [('has', 'modules', 'Demo'),
   ('has', 'functions', 'run'),
   ('has', 'functions', 'helper'),
   ('has', 'function_calls', 'helper')]),
 ('aliases',
  'defmodule Demo do\n alias MyApp.{One, Two}\n alias MyApp.Three, as: Third\nend\n',
  [('has', 'imports', 'MyApp.One'),
   ('has', 'imports', 'MyApp.Two'),
   ('has', 'imports', 'MyApp.Three'),
   ('attr', 'imports', 'MyApp.Three', 'alias', 'Third')]),
 ('pipeline',
  'defmodule Demo do\n def run(x), do: x |> helper() |> finish()\nend\n',
  [('has', 'function_calls', 'helper'),
   ('has', 'function_calls', 'finish'),
   ('count', 'function_calls', 'helper', 1)]),
 ('guards_not_definitions',
  'defmodule Demo do\n def run(x) when is_integer(x), do: helper(x)\nend\n',
  [('has', 'functions', 'run'), ('has', 'function_calls', 'helper'), ('absent', 'functions', 'is_integer')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('elixir')
    offset = 0
    if variant == "padded":
        source = '# audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".ex")
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


def test_guarded_definition_does_not_create_a_self_call(tmp_path):
    from codegraphcontext.tools.languages.elixir import pre_scan_elixir
    path = tmp_path / 'guard.ex'
    path.write_text('defmodule Demo do\n def run(x) when is_integer(x), do: helper(x)\nend\n')
    parser = TreeSitterParser('elixir')
    result = parser.parse(path)
    assert next(f for f in result['functions'] if f['name'] == 'run')['args'] == ['x']
    assert 'run' not in {c['name'] for c in result['function_calls']}
    assert next(c for c in result['function_calls'] if c['name'] == 'helper')['context'][0] == 'run'
    assert 'run' in pre_scan_elixir([path], parser)


@pytest.mark.parametrize("name,source", [('repeated_same_line', 'defmodule Demo do\n def run do\n helper(1); helper(2);\n end\nend\n'),
 ('nested_arguments', 'defmodule Demo do\n def run do\n helper(inner(1, 2), 3);\n end\nend\n')])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_invocation_identity_and_arguments(tmp_path, name, source, variant):
    parser = TreeSitterParser('elixir')
    if variant == "padded":
        source = '# π\n' + source
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / "calls.elixir"
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
