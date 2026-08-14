# C++ Parser Fixes

Six independent bugs in the C++ tree-sitter parser that produced incorrect graph
data or silently dropped code elements. All changes are confined to a single file:

**`src/codegraphcontext/tools/languages/cpp.py`**

## Summary

| # | Bug | Location | Lines |
|---|---|---|---|
| 1 | Local quoted includes kept their `"` quotes | `_find_imports` | 383 |
| 2 | Initialized variables always reported `type: None` | `_find_variables` | 573–582 |
| 3 | Uninitialized variables never captured | `CPP_QUERIES['variables']` + `_find_variables` | 160–161, 600–624 |
| 4 | Inline class methods had no `class_context` | `_find_functions` | 256–263 |
| 5 | Function-like macros missed entirely | `CPP_QUERIES['macros']` + `_find_macros` | 145–147, 483, 495–501 |
| 6 | Macro `end_line` off by one | `_find_macros` | 487–488 |

## Bug 1 — Include name stripping

**Location:** `_find_imports`, line 383

Angle brackets were stripped but double quotes were not, so a local include
produced a name with the quotes still attached.

```python
# Before
path = self._get_node_text(node).strip('<>')
# After
path = self._get_node_text(node).strip('"<>')
```

`#include "local.h"` yielded `"local.h"` instead of `local.h`. This also made C++
inconsistent with the C parser, which already used `.strip('"<>')`.

**Preserved:** system includes (`#include <stdio.h>`) still resolve to `stdio.h`.

## Bug 2 — Variable type extraction for initialized declarations

**Location:** `_find_variables`, lines 573–582

The code read the `type` field off `node.parent`, which for `int x = 5;` is the
`init_declarator` node. That node has no `type` field, so the lookup always
returned `None`. The type lives on the enclosing `declaration` node.

```python
if assignment_node.type == 'init_declarator':
    decl_node = assignment_node.parent
    type_node = decl_node.child_by_field_name('type') if decl_node else None
else:
    type_node = assignment_node.child_by_field_name('type')
```

The `init_declarator` guard on line 577 is load-bearing. For a
`field_declaration` (`int m_count;` inside a class), `node.parent` is already the
`field_declaration` itself and carries `type` directly — walking up an extra
level there returned `None` and regressed class fields. This was caught during
verification and corrected.

**Preserved:** class field declarations keep their type and class context.

## Bug 3 — Uninitialized variable capture

**Location:** `CPP_QUERIES['variables']` lines 160–161; `_find_variables` lines 600–624

The variables query matched only `init_declarator` shapes. A bare declaration
like `int count;` has an `identifier` declarator with no `init_declarator`
wrapper, so it matched nothing and the variable was absent from the output
entirely.

Added query pattern:

```
(declaration
    type: (_) @var_type
    declarator: (identifier) @plain_name)
```

The `@plain_name` branch extracts the type from the `declaration` node directly.
A `seen_plain_names` set (populated at line 599, checked at line 603) keys on
`(name, row)` to prevent emitting a variable twice when it matches both the
initialized and plain patterns.

**Preserved:** field declarations and initialized variables are unaffected and
not duplicated.

## Bug 4 — Inline class method context

**Location:** `_find_functions`, lines 256–263

`class_context` was only ever set by splitting a qualified name on `::`. Methods
defined inline inside a class body have simple names, so they never got a
context — which meant the indexer's C++ post-pass could not create the
`Class-[:CONTAINS]->Function` edge for them.

```python
if not class_context:
    ancestor = func_node.parent
    while ancestor:
        if ancestor.type == 'class_specifier':
            class_name_node = ancestor.child_by_field_name('name')
            if class_name_node:
                class_context = self._get_node_text(class_name_node)
            break
        ancestor = ancestor.parent
```

Gated on `if not class_context` so qualified-name splitting still takes
precedence. The walk breaks at the first `class_specifier`, so a method in a
nested class gets the innermost class.

**Preserved:** out-of-line qualified methods (`void Foo::bar()`) still resolve to
`Foo`; file-scope functions still carry no `class_context`.

## Bug 5 — Function-like macro extraction

**Location:** `CPP_QUERIES['macros']` lines 145–147; `_find_macros` lines 483, 495–501

Function-like macros use the `preproc_function_def` AST node type, which is
distinct from `preproc_def`. The macros query matched only the latter, so
`#define SQUARE(x) ((x)*(x))` was never extracted.

Added query alternative:

```
(preproc_function_def
    name: (identifier) @func_name
) @func_macro
```

The capture guard at line 483 widened to `if capture_name in ('name', 'func_name')`,
and parameters are read from the node's `parameters` field into a `params` list.

**Preserved:** object-like macros (`#define MAX_SIZE 100`) still extract correctly.

## Bug 6 — Macro end_line accuracy

**Location:** `_find_macros`, lines 487–488

Tree-sitter's `end_point` is the position *after* the last character. For a macro
terminated by a newline, `end_point[0]` has already rolled to the next row, so
the unconditional `+ 1` that converts to 1-indexed double-counted and reported a
line one past the real end.

```python
end_row = macro_node.end_point[0]
end_col = macro_node.end_point[1]
end_line = end_row if end_col == 0 else end_row + 1
```

When the end column is 0 the row is already "past" the last line, so it is used
as-is; otherwise the `+ 1` conversion still applies.

**Preserved:** multi-line (line-continued) macros still span to their real end,
as do macros with no trailing newline.

## Verification

27 existing tests pass:

```
tests/unit/parsers/test_cpp_parser.py
tests/unit/parsers/test_cpp_enums.py
tests/unit/parsers/test_c_cpp_pointer_returns.py
```

No test files were added or modified.

An important caveat on coverage: those existing tests exercise enums,
inheritance, qualified methods, and call expressions. They do **not** cover the
six behaviours fixed here, so they confirm the absence of regressions rather
than confirming the fixes. The fixed behaviour was verified separately with a
temporary script covering each bug scenario plus a preservation case
(system includes, field declarations, qualified methods, file-scope functions,
object-like macros, lambda assignments). That script is where the Bug 2 field
declaration regression surfaced. It was deleted after use and is not part of the
repository, which leaves these six behaviours without permanent regression
coverage.

## Environment note

`src/codegraphcontext/utils/tree_sitter_manager.py` raises an error stating that
tree-sitter parsing is unavailable on Python 3.13 because
`tree-sitter-language-pack` publishes no cp313 wheels. That is now out of date:
version 1.14.3 installs and works on Python 3.13 via an abi3 wheel, and was used
to run the tests above. Loosening that version gate is a separate change and has
not been made here.
