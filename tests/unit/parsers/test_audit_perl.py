"""Invocation identity and argument regression tests."""
import pytest
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser


@pytest.mark.parametrize("name,source", [('repeated_same_line', 'sub run { helper(1); helper(2); }\n'),
 ('nested_arguments', 'sub run { helper(inner(1, 2), 3); }\n')])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_invocation_identity_and_arguments(tmp_path, name, source, variant):
    parser = TreeSitterParser('perl')
    if variant == "padded":
        source = '# π\n' + source
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / "calls.perl"
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


def test_commas_inside_strings_and_nested_calls_do_not_split_arguments(tmp_path):
    path = tmp_path / 'strings.pl'
    path.write_text('sub run { helper("a,b", inner(1, 2), @items); }\n')
    result = TreeSitterParser('perl').parse(path)
    call = next(c for c in result['function_calls'] if c['name'] == 'helper')
    assert call['args'] == ['"a,b"', 'inner(1, 2)', '@items']
