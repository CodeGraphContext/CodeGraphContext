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


CASES = [('namespace',
  '<?php\nnamespace Demo;\nclass S { function run() { helper(); } }\n',
  [('has', 'classes', 'S'),
   ('has', 'functions', 'run'),
   ('has', 'function_calls', 'helper'),
   ('attr', 'function_calls', 'helper', 'class_context.0', 'S')]),
 ('enum',
  "<?php\nenum Status: string { case Ok = 'ok'; public function label() { return helper(); } }\n",
  [('has', 'classes', 'Status'), ('has', 'functions', 'label'), ('has', 'function_calls', 'helper')]),
 ('trait',
  '<?php\ntrait Work { function run() { helper(); } }\n',
  [('has', 'traits', 'Work'), ('has', 'functions', 'run'), ('has', 'function_calls', 'helper')]),
 ('imports',
  '<?php\nuse Vendor\\Package\\Thing as T;\nuse Vendor\\Package\\{One, Two as Second};\n',
  [('has', 'imports', 'T'), ('has', 'imports', 'One'), ('has', 'imports', 'Second')]),
 ('arrow_function',
  '<?php\nfunction outer() { $cb = fn($x) => helper($x); return $cb(1); }\n',
  [('has', 'functions', 'outer'), ('has', 'functions', 'cb'), ('has', 'function_calls', 'helper')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('php')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".php")
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


@pytest.mark.parametrize("source,name", [("<?php\nenum Status: string { case Ok = 'ok'; public function label() { return helper(); } }\n", 'Status')])
def test_prescan_keeps_declarations(tmp_path, source, name):
    from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
    path = tmp_path / "scan.php"
    path.write_text(source, encoding="utf-8")
    parser = TreeSitterParser('php')
    result = pre_scan_for_imports([path], {".php"}, lambda _: parser)
    assert name in result, result


def test_assigned_arrow_has_parameters_and_owns_its_calls(tmp_path):
    path = tmp_path / 'arrow.php'
    path.write_text('<?php\nfunction outer() { $cb = fn($x) => helper($x); return $cb(1); }\n')
    result = TreeSitterParser('php').parse(path)
    callback = next(f for f in result['functions'] if f['name'] == 'cb')
    assert callback['parameters'] == ['$x']
    helper = next(c for c in result['function_calls'] if c['name'] == 'helper')
    assert helper['context'][0] == 'cb'
    assert next(c for c in result['function_calls'] if c['name'] == 'cb')['context'][0] == 'outer'
