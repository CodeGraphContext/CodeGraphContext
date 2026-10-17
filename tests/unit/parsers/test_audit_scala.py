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


CASES = [('definitions',
  'object S {\n def run = helper()\n def helper(): Int = 1\n}\n',
  [('has', 'objects', 'S'),
   ('has', 'functions', 'run'),
   ('has', 'functions', 'helper'),
   ('has', 'function_calls', 'helper')]),
 ('trait_signatures',
  'trait Draw {\n def draw(x: Int): Unit\n}\n',
  [('has', 'traits', 'Draw'), ('has', 'functions', 'draw')]),
 ('curried_parameters',
  'def add(x: Int)(y: Int): Int = x + y\n',
  [('has', 'functions', 'add'), ('attr', 'functions', 'add', 'args', ['x', 'y'])]),
 ('imports',
  'import scala.collection.{mutable, immutable}\n',
  [('has', 'imports', 'scala.collection.mutable'), ('has', 'imports', 'scala.collection.immutable')])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('scala')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".scala")
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


@pytest.mark.parametrize("source,name", [('def add(x: Int)(y: Int): Int = x + y\n', 'add')])
def test_prescan_keeps_declarations(tmp_path, source, name):
    from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
    path = tmp_path / "scan.scala"
    path.write_text(source, encoding="utf-8")
    parser = TreeSitterParser('scala')
    result = pre_scan_for_imports([path], {".scala"}, lambda _: parser)
    assert name in result, result


def test_generic_types_do_not_split_parameters_and_import_exclusions_are_not_bindings(tmp_path):
    path = tmp_path / 'demo.scala'
    path.write_text('def f[A](x: Map[String, Int], y: List[A])(implicit z: Z): A = ???\nimport scala.collection.{mutable, immutable => Im, Set => _}\n')
    result = TreeSitterParser('scala').parse(path)
    assert next(f for f in result['functions'] if f['name'] == 'f')['args'] == ['x', 'y', 'z']
    assert {(i['name'], i['alias']) for i in result['imports']} == {('scala.collection.mutable', None), ('scala.collection.immutable', 'Im')}
