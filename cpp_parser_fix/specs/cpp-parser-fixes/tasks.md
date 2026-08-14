# Implementation Plan

## Overview

This task list implements fixes for six independent bugs in the C++ tree-sitter parser (`cpp.py`). The workflow follows the exploratory bugfix methodology: write tests to confirm bugs exist, write preservation tests to protect existing behavior, implement fixes, then verify all tests pass.

## Tasks

- [ ] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - C++ Parser Six-Bug Exploration
  - **CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behavior - they will validate the fixes when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate all six bugs exist
  - **Scoped PBT Approach**: Each bug is deterministic; scope properties to concrete failing cases
  - Test 1 - Include name stripping: Parse `#include "local.h"` and assert module name is `local.h` (not `"local.h"`)
  - Test 2 - Variable type extraction: Parse `int x = 5;` and assert type is `int` (not `None`)
  - Test 3 - Uninitialized variable capture: Parse `int count;` and assert variable is captured with type `int`
  - Test 4 - Inline class method context: Parse `class Foo { void bar() {} };` and assert `class_context` is `Foo`
  - Test 5 - Function-like macro extraction: Parse `#define SQUARE(x) ((x)*(x))` and assert macro is extracted with name `SQUARE`
  - Test 6 - Macro end_line accuracy: Parse a single-line `#define MAX 100` at line 1 and assert `end_line` is `1` (not `2`)
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: All six tests FAIL (this is correct - it proves the bugs exist)
  - Document counterexamples found:
    - Include names contain surrounding double quotes
    - Variable types are `None` for initialized declarations
    - Uninitialized variables completely missing from output
    - Inline methods have no `class_context` key
    - Function-like macros absent from macros list
    - Macro `end_line` values one greater than expected
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing C++ Parser Behavior for Non-Bug Inputs
  - **IMPORTANT**: Follow observation-first methodology
  - **Step 1 - Observe**: Run UNFIXED code with non-buggy inputs and record actual outputs:
    - Observe: `#include <stdio.h>` produces module name `stdio.h` on unfixed code
    - Observe: Class field `int m_count;` inside a class is extracted with type `int` and correct class context
    - Observe: `void Foo::bar() {}` at file scope gets `class_context: "Foo"` via `::` splitting
    - Observe: `#define MAX_SIZE 100` is extracted as a macro with name `MAX_SIZE`
    - Observe: File-scope `void process() {}` has no `class_context`
    - Observe: `auto fn = [](int x) { return x; };` is extracted as a function node
  - **Step 2 - Write property-based tests**: Capture observed behavior patterns:
    - Property: For all system/angle-bracket includes, module name equals path with angle brackets stripped
    - Property: For all field declarations inside a class, type is extracted and class_context is set
    - Property: For all qualified-name methods (`ClassName::method`), class_context equals the qualifier
    - Property: For all object-like macros, name is extracted correctly
    - Property: For all file-scope functions (no enclosing class), class_context is None/empty
    - Property: For all lambda assignments, function node is extracted with correct context
  - **Step 3 - Verify**: Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: All preservation tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 3. Fix for C++ parser six-bug set

  - [ ] 3.1 Fix include name stripping in `_find_imports`
    - Replace `.strip('<>')` with `.strip('"<>')` to handle both quoted and angle-bracket includes
    - Location: `src/codegraphcontext/tools/languages/cpp.py`, `_find_imports` method
    - _Bug_Condition: isLocalInclude(input) where input.path.type == "string_literal"_
    - _Expected_Behavior: module name has no surrounding quotes or angle brackets_
    - _Preservation: System includes (#include <system.h>) continue to produce clean name_
    - _Requirements: 2.1, 3.1_

  - [ ] 3.2 Fix variable type extraction for initialized declarations in `_find_variables`
    - Navigate from `init_declarator` node up to parent `declaration` node to access the `type` field
    - Change: `assignment_node = node.parent` → also get `decl_node = assignment_node.parent` and use `decl_node.child_by_field_name('type')`
    - Location: `src/codegraphcontext/tools/languages/cpp.py`, `_find_variables` method
    - _Bug_Condition: isInitializedVariable(input) where declarator.type == "init_declarator"_
    - _Expected_Behavior: type extracted from enclosing declaration node, not None_
    - _Preservation: Field declarations continue to work correctly_
    - _Requirements: 2.2, 3.2_

  - [ ] 3.3 Add query pattern for uninitialized variables in `CPP_QUERIES['variables']`
    - Add pattern: `(declaration type: (_) @var_type declarator: (identifier) @name)`
    - Update `_find_variables` to handle the new capture, extracting type from the matched `declaration` node
    - Location: `src/codegraphcontext/tools/languages/cpp.py`, `CPP_QUERIES` dict and `_find_variables` method
    - _Bug_Condition: isUninitializedVariable(input) where declarator.type == "identifier" (no init_declarator)_
    - _Expected_Behavior: variable captured with correct type from declaration node_
    - _Preservation: Field declarations and initialized variables unaffected_
    - _Requirements: 2.3, 3.2_

  - [ ] 3.4 Set class_context for inline methods in `_find_functions`
    - After extracting function name, if no `class_context` from qualified name, walk ancestors to find `class_specifier`
    - Set `class_context` to enclosing class name if found
    - Location: `src/codegraphcontext/tools/languages/cpp.py`, `_find_functions` method
    - _Bug_Condition: isInlineClassMethod(input) where ancestor("class_specifier") exists and name has no "::"_
    - _Expected_Behavior: class_context equals enclosing class name_
    - _Preservation: Qualified-name methods and file-scope functions unaffected_
    - _Requirements: 2.4, 3.3, 3.5_

  - [ ] 3.5 Add function-like macro query in `CPP_QUERIES['macros']`
    - Add pattern: `(preproc_function_def name: (identifier) @name) @macro`
    - Update `_find_macros` to extract parameters from `preproc_function_def` node's `parameters` field
    - Location: `src/codegraphcontext/tools/languages/cpp.py`, `CPP_QUERIES` dict and `_find_macros` method
    - _Bug_Condition: isFunctionLikeMacro(input) where type == "preproc_function_def"_
    - _Expected_Behavior: macro extracted with correct name and parameters_
    - _Preservation: Object-like macros continue to be extracted correctly_
    - _Requirements: 2.5, 3.4_

  - [ ] 3.6 Fix macro end_line calculation in `_find_macros`
    - Replace `macro_node.end_point[0] + 1` with conditional: use `end_point[0]` when `end_point[1] == 0`, else `end_point[0] + 1`
    - Location: `src/codegraphcontext/tools/languages/cpp.py`, `_find_macros` method
    - _Bug_Condition: isObjectLikeMacro(input) — end_line always off by one when trailing newline present_
    - _Expected_Behavior: end_line points to actual last line of macro definition_
    - _Preservation: Multi-line macros and macros without trailing newline handled correctly_
    - _Requirements: 2.6, 3.4_

  - [ ] 3.7 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - C++ Parser Six-Bug Fixes Validated
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior for all six bugs
    - When these tests pass, it confirms:
      - Include names are properly stripped of quotes
      - Variable types are correctly extracted for initialized declarations
      - Uninitialized variables are captured
      - Inline methods have class_context set
      - Function-like macros are extracted
      - Macro end_line is accurate
    - Run bug condition exploration tests from step 1
    - **EXPECTED OUTCOME**: All six tests PASS (confirms all bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 3.8 Verify preservation tests still pass
    - **Property 2: Preservation** - No Regressions in Existing Behavior
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: All preservation tests PASS (confirms no regressions)
    - Confirm system includes, field declarations, qualified-name methods, object-like macros, file-scope functions, and lambda assignments are all unaffected
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Run full test suite to ensure no regressions
  - Verify all bug condition exploration tests pass (6 bugs fixed)
  - Verify all preservation property tests pass (no regressions)
  - Run any existing project tests to confirm compatibility
  - Ask the user if questions arise

## Task Dependency Graph

```json
{
  "waves": [
    ["1", "2"],
    ["3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],
    ["3.7", "3.8"],
    ["4"]
  ]
}
```

## Notes

- All six bugs are independent and can be fixed in any order within task 3
- The file under modification is `src/codegraphcontext/tools/languages/cpp.py` (CppTreeSitterParser class and CPP_QUERIES dictionary)
- Tasks 1 and 2 can be executed in parallel since they are independent
- Property-based testing is recommended for preservation tests to cover the broad input domain
- The exploration tests serve dual purpose: first they confirm bugs exist (fail on unfixed code), then they validate the fix (pass on fixed code)
