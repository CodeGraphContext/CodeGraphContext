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


CASES = [('singleton',
  'class S\n def self.build(x)\n  helper(x)\n end\nend\n',
  [('has', 'classes', 'S'), ('has', 'functions', 'build'), ('has', 'function_calls', 'helper')]),
 ('module_context',
  'module Demo\n class S\n  def run\n   helper\n  end\n end\nend\n',
  [('has', 'modules', 'Demo'),
   ('has', 'classes', 'S'),
   ('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper')]),
 ('attribute_variables',
  "class S\n @@count = 0\n def run\n  @name = 'x'\n end\nend\n$flag = true\n",
  [('has', 'variables', '@@count'), ('has', 'variables', '@name'), ('has', 'variables', '$flag')]),
 ('imports',
  "require 'json'\nrequire_relative './helper'\n",
  [('has', 'imports', 'json'), ('has', 'imports', './helper')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('ruby')
    offset = 0
    if variant == "padded":
        source = '# audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".rb")
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


def test_bare_calls_distinguish_parameters_locals_and_earlier_vcalls(tmp_path):
    path = tmp_path / 'locals.rb'
    path.write_text('class S\n def run(x)\n  before\n  before = 1\n  before\n  x\n  helper\n  items = []\n  items.each { |item| item; x; helper }\n end\nend\n')
    result = TreeSitterParser('ruby').parse(path)
    bare = [c for c in result['function_calls'] if c['name'] in {'x', 'item', 'items', 'before', 'helper'}]
    assert [(c['name'], c['line_number']) for c in bare] == [('before', 3), ('helper', 7), ('helper', 9)]


@pytest.mark.parametrize("name,source", [('repeated_same_line', 'def run; helper(1); helper(2);; end\n'),
 ('nested_arguments', 'def run; helper(inner(1, 2), 3);; end\n')])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_invocation_identity_and_arguments(tmp_path, name, source, variant):
    parser = TreeSitterParser('ruby')
    if variant == "padded":
        source = '# π\n' + source
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / "calls.ruby"
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
