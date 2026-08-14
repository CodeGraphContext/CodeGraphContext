# C++ Parser Fixes Bugfix Design

## Overview

The C++ tree-sitter parser (`cpp.py`) has six independent bugs that produce incorrect graph data or miss code elements entirely. This design formalizes each bug condition, defines expected behavior, hypothesizes root causes from the source code, and plans a minimal targeted fix for each. The bugs are isolated to specific methods in `CppTreeSitterParser` and to the `CPP_QUERIES` dictionary, making them safe to fix independently without cross-contamination.

## Glossary

- **Bug_Condition (C)**: The set of inputs (C++ source constructs) that trigger incorrect parser output
- **Property (P)**: The desired correct output for each bug condition after the fix is applied
- **Preservation**: Existing behaviors for non-buggy inputs that must remain unchanged by the fix
- **CppTreeSitterParser**: The class in `src/codegraphcontext/tools/languages/cpp.py` responsible for parsing C++ source files into graph data
- **CPP_QUERIES**: Dictionary of tree-sitter query strings used to match AST node patterns
- **tree-sitter**: The incremental parsing library providing AST nodes with `start_point`/`end_point` (0-indexed row, column) tuples
- **init_declarator**: AST node wrapping an identifier and its initializer in `int x = 5;`
- **declaration**: AST node representing the full declaration including type specifier
- **preproc_def**: AST node for object-like macros (`#define NAME value`)
- **preproc_function_def**: AST node for function-like macros (`#define NAME(params) body`)
- **class_specifier**: AST node representing a `class` or `struct` definition body

## Bug Details

### Bug Condition

The bugs manifest across six independent conditions in the C++ parser. Each condition identifies a specific class of C++ source construct that is either parsed incorrectly or missed entirely.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type CppSourceConstruct
  OUTPUT: boolean
  
  RETURN isLocalInclude(input)            -- Bug 1: #include "file.h"
         OR isInitializedVariable(input)   -- Bug 2: int x = 5;
         OR isUninitializedVariable(input)  -- Bug 3: int count;
         OR isInlineClassMethod(input)      -- Bug 4: class Foo { void bar() {} };
         OR isFunctionLikeMacro(input)      -- Bug 5: #define SQUARE(x) ((x)*(x))
         OR isObjectLikeMacro(input)        -- Bug 6: #define MAX 100 (end_line off)
END FUNCTION

FUNCTION isLocalInclude(input)
  RETURN input.type == "preproc_include"
         AND input.path.type == "string_literal"  -- quoted include
END FUNCTION

FUNCTION isInitializedVariable(input)
  RETURN input.type == "declaration"
         AND input.declarator.type == "init_declarator"
         AND input.declarator.child("value") IS NOT NULL
END FUNCTION

FUNCTION isUninitializedVariable(input)
  RETURN input.type == "declaration"
         AND input.declarator.type == "identifier"  -- bare identifier, no init_declarator
         AND input NOT IN field_declarations
END FUNCTION

FUNCTION isInlineClassMethod(input)
  RETURN input.type == "function_definition"
         AND input.ancestor("class_specifier") IS NOT NULL
         AND input.declarator NOT contains "::"
END FUNCTION

FUNCTION isFunctionLikeMacro(input)
  RETURN input.type == "preproc_function_def"
END FUNCTION

FUNCTION isObjectLikeMacro(input)
  RETURN input.type == "preproc_def"
         -- end_line calculation is always wrong due to +1 double-count
END FUNCTION
```

### Examples

- **Bug 1**: `#include "local.h"` → parser returns name `"local.h"` (with quotes) instead of `local.h`
- **Bug 2**: `int x = 5;` → parser returns type `None` instead of `int` because it queries `init_declarator` (no type field) rather than the parent `declaration`
- **Bug 3**: `int count;` → parser returns nothing (variable not captured) because the query only matches `init_declarator` patterns
- **Bug 4**: `class Foo { void bar() { return; } };` → parser returns `bar` without `class_context: "Foo"` because `_find_functions` only sets `class_context` for qualified names with `::`
- **Bug 5**: `#define SQUARE(x) ((x)*(x))` → parser misses it entirely because the macros query only matches `preproc_def`, not `preproc_function_def`
- **Bug 6**: `#define MAX 100` on line 5 → parser reports `end_line: 6` instead of `end_line: 5` because tree-sitter's `end_point` for a single-line macro with trailing newline points to the next row

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- System/angle-bracket includes (`#include <system.h>`) must continue to produce clean module name `system.h`
- Class field declarations (`field_declaration`) must continue to be extracted with correct type and class context
- Out-of-line qualified methods (`void Foo::bar()`) must continue to get `class_context` via `::` splitting
- Object-like macros (`#define MAX_SIZE 100`) must continue to be extracted with correct name
- File-scope functions (not inside a class) must continue to have no `class_context`
- Lambda assignments must continue to be extracted as function nodes with correct context

**Scope:**
All inputs that do NOT match any of the six bug conditions should be completely unaffected by this fix. This includes:
- System includes with angle brackets
- Variables declared as class fields
- Functions defined at file scope or with qualified names
- Lambda assignments
- All other tree-sitter query patterns (enums, structs, unions, calls, classes)

## Hypothesized Root Cause

Based on the bug description and source code analysis, the root causes are:

1. **Incorrect Strip Characters (Bug 1)**: `_find_imports` uses `.strip('<>')` which only removes angle brackets. Local includes use double quotes (`"local.h"`), so the quotes are never stripped. The C parser correctly uses `.strip('"<>')`.

2. **Wrong Parent Node for Type Extraction (Bug 2)**: In `_find_variables`, `node.parent` is the `init_declarator` node. The code calls `assignment_node.child_by_field_name('type')` but `init_declarator` has no `type` field — only the grandparent `declaration` node has it. This always returns `None`.

3. **Missing Query Pattern for Plain Declarations (Bug 3)**: The `variables` query in `CPP_QUERIES` only matches `init_declarator` patterns (variables with initializers). A plain declaration like `int count;` has a `declaration` node with a direct `identifier` declarator (no `init_declarator` wrapper), so it is never matched.

4. **No Class Ancestor Check for Inline Methods (Bug 4)**: `_find_functions` only sets `class_context` when the function has a qualified name containing `::`. Inline methods defined inside a class body have simple names (no `::`), so `class_context` is never set for them. The fix needs to check if the function's ancestor is a `class_specifier`.

5. **Missing Node Type in Macros Query (Bug 5)**: The `macros` query only matches `(preproc_def name: (identifier) @name)`. Function-like macros use the AST node type `preproc_function_def`, which is a separate tree-sitter node type not covered by this query.

6. **End Point Double-Count (Bug 6)**: The code uses `macro_node.end_point[0] + 1`. Tree-sitter's `end_point` is the position *after* the last character. For a macro with a trailing newline, `end_point[0]` already points to the next row (0-indexed). Adding `+1` converts to 1-indexed but double-counts, giving a line number one past the actual last line. The fix should use `macro_node.end_point[0]` when `end_point[1] == 0` (meaning the end is at column 0 of the next line, i.e. the trailing newline), or `macro_node.end_point[0] + 1` otherwise.

## Correctness Properties

Property 1: Bug Condition - Include Name Stripping

_For any_ C++ source file containing a local quoted include (`#include "file.h"`), the fixed `_find_imports` method SHALL return the module name without surrounding double quotes, producing just the filename (e.g., `local.h`).

**Validates: Requirements 2.1**

Property 2: Bug Condition - Variable Type Extraction for Initialized Declarations

_For any_ C++ variable declaration with an initializer (e.g., `int x = 5;`), the fixed `_find_variables` method SHALL extract the type from the enclosing `declaration` node and report it correctly (e.g., `int`).

**Validates: Requirements 2.2**

Property 3: Bug Condition - Uninitialized Variable Capture

_For any_ C++ variable declaration without an initializer (e.g., `int count;`) that is not a field declaration, the fixed parser SHALL capture the variable with its type extracted from the `declaration` node.

**Validates: Requirements 2.3**

Property 4: Bug Condition - Inline Class Method Context

_For any_ function defined inline inside a class body, the fixed `_find_functions` method SHALL set `class_context` to the enclosing class name.

**Validates: Requirements 2.4**

Property 5: Bug Condition - Function-Like Macro Extraction

_For any_ function-like macro definition (`#define NAME(params) body`), the fixed `_find_macros` method SHALL extract it as a macro node with correct name and parameters.

**Validates: Requirements 2.5**

Property 6: Bug Condition - Macro End Line Accuracy

_For any_ object-like macro definition, the fixed `_find_macros` method SHALL report `end_line` pointing to the actual last line of the macro definition without double-counting.

**Validates: Requirements 2.6**

Property 7: Preservation - Existing Parser Behavior for Non-Bug Inputs

_For any_ C++ source construct that does NOT match any of the six bug conditions (system includes, field declarations, qualified-name functions, file-scope functions, lambda assignments), the fixed parser SHALL produce exactly the same output as the original parser.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/codegraphcontext/tools/languages/cpp.py`

**Change 1 — Fix include name stripping** (`_find_imports`):

Replace `.strip('<>')` with `.strip('"<>')` to handle both quoted and angle-bracket includes, matching the C parser's behavior.

```python
# Before
path = self._get_node_text(node).strip('<>')
# After
path = self._get_node_text(node).strip('"<>')
```

**Change 2 — Fix variable type extraction** (`_find_variables`):

Navigate from the `init_declarator` node up to the parent `declaration` node to access the `type` field.

```python
# Before
assignment_node = node.parent  # init_declarator
type_node = assignment_node.child_by_field_name('type')
# After
assignment_node = node.parent  # init_declarator
decl_node = assignment_node.parent  # declaration
type_node = decl_node.child_by_field_name('type') if decl_node else None
```

**Change 3 — Add query pattern for uninitialized variables** (`CPP_QUERIES['variables']`):

Add a new pattern to the variables query that matches `declaration` nodes with a bare `identifier` declarator (no `init_declarator`):

```
(declaration
    type: (_) @var_type
    declarator: (identifier) @name)
```

Also update `_find_variables` to handle this new capture, extracting the type from the matched `declaration` node.

**Change 4 — Set class_context for inline methods** (`_find_functions`):

After extracting the function name, if no `class_context` was set from a qualified name, walk ancestors to check if the function is inside a `class_specifier` and set `class_context` accordingly:

```python
if not class_context:
    parent = func_node.parent
    while parent:
        if parent.type == 'class_specifier':
            name_node = parent.child_by_field_name('name')
            if name_node:
                class_context = self._get_node_text(name_node)
            break
        parent = parent.parent
```

**Change 5 — Add function-like macro query** (`CPP_QUERIES['macros']`):

Extend the macros query to also match `preproc_function_def` nodes:

```
(preproc_function_def
    name: (identifier) @name
) @macro
```

Also update `_find_macros` to extract parameters from the `preproc_function_def` node's `parameters` field.

**Change 6 — Fix macro end_line calculation** (`_find_macros`):

Adjust the end_line calculation to account for tree-sitter's end_point behavior with trailing newlines:

```python
# Before
"end_line": macro_node.end_point[0] + 1,
# After — if end column is 0, the end_point row is already "past" the last line
end_row = macro_node.end_point[0]
end_col = macro_node.end_point[1]
end_line = end_row if end_col == 0 else end_row + 1
```

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fixes work correctly and preserve existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write unit tests that parse specific C++ source snippets and assert the expected output. Run these tests on the UNFIXED code to observe failures and confirm root causes.

**Test Cases**:
1. **Local Include Test**: Parse `#include "local.h"` and assert module name is `local.h` (will fail on unfixed code — returns `"local.h"`)
2. **Initialized Variable Type Test**: Parse `int x = 5;` and assert type is `int` (will fail on unfixed code — returns `None`)
3. **Uninitialized Variable Test**: Parse `int count;` and assert variable is captured (will fail on unfixed code — returns empty list)
4. **Inline Method Context Test**: Parse `class Foo { void bar() {} };` and assert `class_context` is `Foo` (will fail on unfixed code — no `class_context`)
5. **Function-Like Macro Test**: Parse `#define SQUARE(x) ((x)*(x))` and assert macro is extracted (will fail on unfixed code — not captured)
6. **Macro End Line Test**: Parse a single-line `#define MAX 100` at line 1 and assert `end_line` is 1 (will fail on unfixed code — returns 2)

**Expected Counterexamples**:
- Include names contain surrounding double quotes
- Variable types are `None` for all initialized declarations
- Uninitialized variables are completely missing from output
- Inline methods have no `class_context` key
- Function-like macros absent from macros list
- Macro `end_line` values are one greater than expected

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed functions produce the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := CppTreeSitterParser_fixed.parse(input)
  ASSERT expectedBehavior(result)
END FOR
```

Specifically:
- For local includes: `result.imports[i].name` does not contain `"` characters
- For initialized variables: `result.variables[i].type` is not None
- For uninitialized variables: variable appears in `result.variables`
- For inline methods: `result.functions[i].class_context` equals enclosing class name
- For function-like macros: macro appears in `result.macros`
- For macro end lines: `result.macros[i].end_line` equals actual last line

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed parser produces the same result as the original parser.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT CppTreeSitterParser_original.parse(input) == CppTreeSitterParser_fixed.parse(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many C++ source constructs automatically across the input domain
- It catches edge cases that manual unit tests might miss (unusual declarations, nested classes, etc.)
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for non-bug inputs, then write property-based tests capturing that behavior.

**Test Cases**:
1. **System Include Preservation**: Verify `#include <stdio.h>` continues to produce `stdio.h`
2. **Field Declaration Preservation**: Verify class fields (`int m_count;` inside a class) continue to be extracted with type
3. **Qualified Method Preservation**: Verify `void Foo::bar()` continues to get `class_context: "Foo"`
4. **Object-Like Macro Preservation**: Verify `#define MAX 100` continues to be extracted with correct name (just verify end_line is now correct)
5. **File-Scope Function Preservation**: Verify top-level `void process()` has no `class_context`
6. **Lambda Assignment Preservation**: Verify `auto fn = [](int x) { return x; };` continues to be extracted as a function

### Unit Tests

- Test each bug fix in isolation with minimal C++ source snippets
- Test edge cases: empty includes, variables with complex types (`std::vector<int>`), nested classes, multi-line macros
- Test that field declarations are unaffected by variable query changes
- Test function-like macros with zero, one, and multiple parameters

### Property-Based Tests

- Generate random valid C++ include directives (both quoted and angle-bracket) and verify names are always stripped
- Generate random variable declarations (with/without initializers, various types) and verify type extraction
- Generate random class definitions with inline methods and verify `class_context` is set
- Generate random macro definitions (object-like and function-like) and verify extraction and line numbers

### Integration Tests

- Parse a complete C++ file containing all six bug scenarios and verify the full output
- Parse real-world C++ header files and verify no regressions in extraction counts
- Verify the full indexing pipeline handles the corrected parser output (imports link, class-method edges created)
