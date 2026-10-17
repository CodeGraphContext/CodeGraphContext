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


CASES = [('curried_call',
  'module Demo where\nrun x y = helper x y\n',
  [('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('count', 'function_calls', 'helper', 1)]),
 ('types',
  'module Demo where\ndata Point = Point Int Int\nclass Draw a where\n draw :: a -> String\n',
  [('has', 'classes', 'Point'), ('has', 'classes', 'Draw')]),
 ('imports',
  'module Demo where\nimport qualified Data.Map as M\nimport Data.List (sort, nub)\n',
  [('has', 'imports', 'Data.Map'), ('has', 'imports', 'Data.List')]),
 ('infix_call',
  'module Demo where\nrun x y = x `helper` y\n',
  [('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('count', 'function_calls', 'helper', 1)])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('haskell')
    offset = 0
    if variant == "padded":
        source = '-- audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".hs")
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


@pytest.mark.parametrize("source,name", [('module Demo where\nrun x y = helper x y\n', 'run'), ('module Demo where\nrun x y = x `helper` y\n', 'run')])
def test_prescan_keeps_declarations(tmp_path, source, name):
    from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
    path = tmp_path / "scan.hs"
    path.write_text(source, encoding="utf-8")
    parser = TreeSitterParser('haskell')
    result = pre_scan_for_imports([path], {".hs"}, lambda _: parser)
    assert name in result, result


def test_backtick_operands_and_prescan_do_not_include_comments(tmp_path):
    from codegraphcontext.tools.languages.haskell import pre_scan_haskell
    path = tmp_path / 'Demo.hs'
    path.write_text('module Demo where\n-- ghost :: Int\nrun x y = x `helper` y\nhelper x y = x\n')
    parser = TreeSitterParser('haskell')
    result = parser.parse(path)
    call = next(c for c in result['function_calls'] if c['name'] == 'helper')
    assert call['args'] == ['x', 'y']
    assert call['context'][0] == 'run'
    scan = pre_scan_haskell([path], parser)
    assert {'run', 'helper'} <= scan.keys()
    assert 'ghost' not in scan
