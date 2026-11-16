"""Invocation identity and argument regression tests."""
import pytest
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser


@pytest.mark.parametrize("name,source", [('repeated_same_line',
  'pragma solidity ^0.8.0; contract S { function run() public { helper(1); helper(2); } }\n'),
 ('nested_arguments',
  'pragma solidity ^0.8.0; contract S { function run() public { helper(inner(1, 2), 3); } }\n')])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_invocation_identity_and_arguments(tmp_path, name, source, variant):
    parser = TreeSitterParser('solidity')
    if variant == "padded":
        source = '// π\n' + source
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / "calls.solidity"
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
    path = tmp_path / 'strings.sol'
    path.write_text('pragma solidity ^0.8.0; contract S { function run() public { helper("a,b", inner(1, 2), 3); } }\n')
    result = TreeSitterParser('solidity').parse(path)
    call = next(c for c in result['function_calls'] if c['name'] == 'helper')
    assert call['args'] == ['"a,b"', 'inner(1, 2)', '3']


def test_inline_contract_prescan_does_not_invent_commented_types(tmp_path):
    from codegraphcontext.tools.languages.solidity import pre_scan_solidity
    path = tmp_path / 'scan.sol'
    path.write_text('pragma solidity ^0.8.0; contract S {} // contract Ghost {}\n')
    scan = pre_scan_solidity([path], TreeSitterParser('solidity'))
    assert 'S' in scan and 'Ghost' not in scan
