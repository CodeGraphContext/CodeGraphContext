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


CASES = [('function_macro',
  '(defun run (x) (helper x))\n(defmacro wrap (x) `(helper ,x))\n',
  [('has', 'functions', 'run'), ('has', 'functions', 'wrap'), ('has', 'function_calls', 'helper')]),
 ('quotes',
  "(setq value '(phantom 1))\n(defun run () (helper))\n",
  [('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('absent', 'function_calls', 'phantom')]),
 ('imports',
  '(require \'cl-lib)\n(load "helper")\n',
  [('has', 'imports', 'cl-lib'), ('has', 'imports', 'helper')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('elisp')
    offset = 0
    if variant == "padded":
        source = '; audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".el")
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


def test_load_forms_ignore_quoted_and_dynamic_targets(tmp_path):
    path = tmp_path / 'loads.el'
    path.write_text('(load-file "one.el")\n(load-library "two")\n(load target)\n\'(load "ghost")\n')
    result = TreeSitterParser('elisp').parse(path)
    assert {(i['name'], i['line_number']) for i in result['imports']} == {('one.el', 1), ('two', 2)}
