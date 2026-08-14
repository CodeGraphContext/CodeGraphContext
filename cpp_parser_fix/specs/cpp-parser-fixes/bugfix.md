# Bugfix Requirements Document

## Introduction

The C++ tree-sitter parser (`cpp.py`) has six independent bugs that produce incorrect graph data or miss code elements entirely. These bugs cause local-header include names to retain quotes, variable types to always be `None` for initialized declarations, uninitialized variables to go uncaptured, inline class methods to lack `class_context`, function-like macros to be missed, and macro end lines to be off by one. Together they degrade the accuracy of the code graph for C++ projects and create inconsistencies with the C parser's behavior on equivalent constructs.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a C++ file contains `#include "local.h"` (a local/quoted include) THEN the system produces a module name with surrounding double quotes (e.g. `"local.h"` instead of `local.h`) because `strip('<>')` only removes angle brackets

1.2 WHEN a C++ variable is declared with an initializer (e.g. `int x = 5;`) THEN the system always reports the variable type as `None` because `node.parent` is the `init_declarator` node (which has no `type` field) rather than the enclosing `declaration` node

1.3 WHEN a C++ variable is declared without an initializer (e.g. `int count;`) THEN the system does not capture the variable at all because the variables query only matches `init_declarator` patterns and not plain `declaration` with a bare `identifier` declarator

1.4 WHEN a method is defined inline inside a class body (e.g. `class Foo { void bar() { ... } }`) THEN the system does not set `class_context` on the function, so the indexer's C++ post-pass cannot create the `Class-[:CONTAINS]->Function` edge for that method

1.5 WHEN a function-like macro is defined (e.g. `#define SQUARE(x) ((x)*(x))`) THEN the system does not extract it because it uses a `preproc_function_def` node type which is not matched by the `preproc_def`-only macros query

1.6 WHEN a simple `#define` macro is parsed THEN the system reports `end_line` as one line past the actual last line of the definition because `macro_node.end_point[0] + 1` double-counts (tree-sitter's `end_point` row is already zero-indexed pointing to the last line and `+1` converts to 1-indexed, but the trailing newline causes `end_point` to reference the next line)

### Expected Behavior (Correct)

2.1 WHEN a C++ file contains `#include "local.h"` THEN the system SHALL produce a clean unquoted module name `local.h` by stripping both double quotes and angle brackets (consistent with the C parser's `.strip('"<>')`)

2.2 WHEN a C++ variable is declared with an initializer (e.g. `int x = 5;`) THEN the system SHALL extract the type from the enclosing `declaration` node's type field and report it correctly (e.g. `int`)

2.3 WHEN a C++ variable is declared without an initializer (e.g. `int count;`) THEN the system SHALL capture the variable with its type extracted from the `declaration` node

2.4 WHEN a method is defined inline inside a class body THEN the system SHALL set `class_context` to the enclosing class name so the indexer can create the `Class-[:CONTAINS]->Function` relationship

2.5 WHEN a function-like macro is defined (e.g. `#define SQUARE(x) ((x)*(x))`) THEN the system SHALL extract it as a macro node with its parameters captured

2.6 WHEN a simple `#define` macro is parsed THEN the system SHALL report `end_line` pointing to the actual last line of the macro definition without double-counting the trailing newline

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a C++ file contains `#include <system.h>` (a system/angle-bracket include) THEN the system SHALL CONTINUE TO produce a clean module name `system.h` with angle brackets stripped

3.2 WHEN a C++ variable is declared as a class field (via `field_declaration`) THEN the system SHALL CONTINUE TO extract the field correctly with its type and class context

3.3 WHEN a method is defined out-of-line with qualified name (e.g. `void Foo::bar() { ... }`) THEN the system SHALL CONTINUE TO set `class_context` via the `Foo::bar` qualified-name splitting logic

3.4 WHEN a simple object-like macro is defined (e.g. `#define MAX_SIZE 100`) THEN the system SHALL CONTINUE TO extract it as a macro node with correct name and line range

3.5 WHEN a C++ function is defined at file scope (not inside a class) THEN the system SHALL CONTINUE TO extract it without a `class_context`

3.6 WHEN lambda assignments are declared (e.g. `auto fn = [](int x) { ... };`) THEN the system SHALL CONTINUE TO be extracted as function nodes with their correct class and function context
