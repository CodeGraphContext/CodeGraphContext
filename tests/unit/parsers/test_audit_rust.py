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


CASES = [('generic_calls',
  'fn run() { identity::<u32>(1); }\n',
  [('has', 'functions', 'run'), ('has', 'function_calls', 'identity')]),
 ('generic_impl',
  'struct Box<T> { value: T }\nimpl<T> Box<T> {\n fn get(&self) { helper(); }\n}\n',
  [('has', 'structs', 'Box'),
   ('has', 'functions', 'get'),
   ('has', 'function_calls', 'helper'),
   ('attr', 'functions', 'get', 'class_context', 'Box')]),
 ('trait_signatures',
  'trait Draw {\n fn draw(&self);\n fn size(&self) -> u32 { 1 }\n}\n',
  [('has', 'traits', 'Draw'), ('has', 'functions', 'draw'), ('has', 'functions', 'size')]),
 ('nested_import',
  'use crate::{self, foo::{Bar, Baz as Q}, baz::*};\n',
  [('has', 'imports', 'self'),
   ('has', 'imports', 'Bar'),
   ('has', 'imports', 'Q'),
   ('has', 'imports', '*'),
   ('attr', 'imports', 'Q', 'full_import_name', 'crate::foo::Baz')]),
 ('method_chain',
  'fn run() { service.build().send(); }\n',
  [('has', 'function_calls', 'build'),
   ('has', 'function_calls', 'send'),
   ('count', 'function_calls', 'build', 1),
   ('count', 'function_calls', 'send', 1)])]

@pytest.mark.parametrize("case_name,source,checks", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("variant", ["plain", "crlf", "padded", "dependency_source", "reuse"])
def test_semantic_audit(tmp_path, case_name, source, checks, variant):
    parser = TreeSitterParser('rust')
    offset = 0
    if variant == "padded":
        source = '// audit π\n' + source
        offset = 1
    elif variant == "crlf":
        source = source.replace("\n", "\r\n")
    path = tmp_path / (case_name + ".rs")
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


def test_generic_method_arguments_owner_line_and_trait_owner(tmp_path):
    path = tmp_path / 'generic.rs'
    path.write_text('struct Box<T> { value: T }\nimpl<T> Box<T> { fn get(&self) { service.work::<u8>(2); } }\ntrait Draw { fn draw(&self); }\n')
    result = TreeSitterParser('rust').parse(path)
    functions = {f['name']: f for f in result['functions']}
    assert functions['get']['class_context'] == 'Box'
    assert functions['get']['class_context_line'] == 1
    assert functions['draw']['class_context'] == 'Draw'
    assert functions['draw']['class_context_line'] == 3
    call = next(c for c in result['function_calls'] if c['name'] == 'work')
    assert call['args'] == ['2']
    assert call['context'][0] == 'get'


def test_extern_signature_is_not_duplicated_or_marked_as_a_trait_method(tmp_path):
    path = tmp_path / 'ffi.rs'
    path.write_text('extern "C" { fn external(x: i32); }\n')
    result = TreeSitterParser('rust').parse(path)
    functions = [f for f in result['functions'] if f['name'] == 'external']
    assert len(functions) == 1
    assert functions[0]['is_extern'] is True
