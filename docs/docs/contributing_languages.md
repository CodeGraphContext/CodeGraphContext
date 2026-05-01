# Contributing New Language Support to CodeGraphContext

This document outlines the steps and best practices for adding support for a new programming language to CodeGraphContext. By following this guide, contributors can efficiently integrate new languages and verify structure and relationships in the **graph database** (regardless of whether the active backend is FalkorDB, KuzuDB, Neo4j, or another supported store).

## 1. Understanding the Architecture

CodeGraphContext uses a modular architecture for multi-language support:

*   **Generic `TreeSitterParser` (in `graph_builder.py`):** This acts as a wrapper, dispatching parsing tasks to language-specific implementations.
*   **Language-Specific Parser Modules (in `src/codegraphcontext/tools/languages/`):** Each language (e.g., Python, JavaScript) has its own module (e.g., `python.py`, `javascript.py`) containing:
    *   Tree-sitter queries (`<LANG>_QUERIES`).
    *   A `<Lang>TreeSitterParser` class that encapsulates language-specific parsing logic.
    *   A `pre_scan_<lang>` function for initial symbol mapping.
*   **`GraphBuilder` (in `graph_builder.py`):** Manages the overall graph building process, including file discovery, pre-scanning, and dispatching to the correct language parser. Persistence goes through **`GraphWriter`** in **`tools/indexing/persistence/writer.py`**, which writes nodes and edges via the database abstraction—**not** by calling `session.run` (or equivalent) directly from the builder.

## 2. Steps to Add a New Language (e.g., TypeScript - `.ts`)

### Step 2.1: Create the Language Module File

1.  Create a new file: `src/codegraphcontext/tools/languages/typescript.py`.
2.  Add the necessary imports: `from pathlib import Path`, `from typing import Any, Dict, Optional, Tuple`, `import logging`, `import ast` (if needed for AST manipulation).
3.  Define `TS_QUERIES` (Tree-sitter queries for TypeScript).
4.  Create a `TypescriptTreeSitterParser` class.
5.  Create a `pre_scan_typescript` function.

### Step 2.2: Define Tree-sitter Queries (`TS_QUERIES`)

This is the most critical and often iterative step. You'll need to define queries for:

*   **`functions`**: Function declarations, arrow functions, methods.
*   **`classes`**: Class declarations, class expressions.
*   **`imports`**: ES6 imports (`import ... from ...`), CommonJS `require()`.
*   **`calls`**: Function calls, method calls.
*   **`variables`**: Variable declarations (`let`, `const`, `var`).
*   **`docstrings`**: (Optional) How documentation comments are identified.
*   **`lambda_assignments`**: (Optional, Python-specific) If the language has similar constructs.

**Tips for Query Writing:**
*   **Consult Tree-sitter Grammars:** Find the `node-types.json` or grammar definition for your language (e.g., `tree-sitter-typescript`).
*   **Use `tree-sitter parse`:** Use the `tree-sitter parse` command-line tool to inspect the AST of sample code snippets. This is invaluable for identifying correct node types and field names.
*   **Start Simple:** Begin with basic queries and gradually add complexity.
*   **Test Iteratively:** After each query, test it with sample code.

### Step 2.3: Implement `<Lang>TreeSitterParser` Class

This class (e.g., `TypescriptTreeSitterParser`) will encapsulate the language-specific logic.

1.  **`__init__(self, generic_parser_wrapper)`**:
    *   Store `generic_parser_wrapper`, `language_name`, `language`, `parser` from the generic wrapper.
    *   Load `TS_QUERIES` using `self.language.query(query_str)`.
2.  **Helper Methods**:
    *   `_get_node_text(self, node)`: Extracts text from a tree-sitter node.
    *   `_get_parent_context(self, node, types=...)`: (Language-specific node types for context).
    *   `_calculate_complexity(self, node)`: (Language-specific complexity nodes).
    *   `_get_docstring(self, body_node)`: (Language-specific docstring extraction).
3.  **`parse(self, path: Path, is_dependency: bool = False) -> Dict`**:
    *   Reads the file, parses it with `self.parser`.
    *   Calls its own `_find_*` methods (`_find_functions`, `_find_classes`, etc.).
    *   Returns a standardized dictionary format (as seen in `python.py` and `javascript.py`).
4.  **`_find_*` Methods**:
    Implement these for each query type, extracting data from the AST and populating the standardized dictionary.

### Step 2.4: Implement `pre_scan_<lang>` Function

This function (e.g., `pre_scan_typescript`) will quickly scan files to build an initial `imports_map`.

1.  It takes `files: list[Path]` and `parser_wrapper` (an instance of `TreeSitterParser`).
2.  Uses a simplified query (e.g., for `class_declaration` and `function_declaration`) to quickly find definitions.
3.  Returns a dictionary mapping symbol names to file paths.

### Step 2.5: Integrate into `graph_builder.py`

1.  **`GraphBuilder.__init__`**:
    *   Add `'.ts': TreeSitterParser('typescript')` to `self.parsers`.
2.  **`TreeSitterParser.__init__`**:
    *   Add an `elif self.language_name == 'typescript':` block to initialize `self.language_specific_parser` with `TypescriptTreeSitterParser(self)`.
3.  **`GraphBuilder._pre_scan_for_imports`**:
    *   Add an `elif '.ts' in files_by_lang:` block to import `pre_scan_typescript` and call it.

## 3. Verification and debugging using the graph database

After implementing support for a new language, it's crucial to verify that the graph is being built correctly.

### Step 3.1: Prepare a sample project

Create a small sample project for your new language (e.g., `tests/sample_project_typescript/`) with:
*   Function declarations.
*   Class declarations (including inheritance).
*   Various import types (if applicable).
*   Function calls.
*   Variable declarations.

### Step 3.2: Index the sample project

From a shell, with your virtual environment active and **`DEFAULT_DATABASE`** (or `cgc config`) pointing at the backend you want to test:

1.  **Remove any prior index for that path (optional but avoids confusion):**
    ```bash
    cgc delete /path/to/your/sample_project
    ```
2.  **Index the project:**
    ```bash
    cgc index /path/to/your/sample_project
    ```
3.  **Confirm stats:**
    ```bash
    cgc stats /path/to/your/sample_project
    ```

If you use the MCP server instead, the same operations map to the management and indexing tools; the CLI commands above are the usual way to verify locally.

### Step 3.3: Query the graph with `cgc query`

Run **Cypher** through the CLI so you stay on the supported abstraction layer (works across backends that expose OpenCypher-compatible query surfaces):

*   **Check for files and language tags:**
    ```bash
    cgc query "MATCH (f:File) WHERE f.path STARTS WITH '/path/to/your/sample_project' RETURN f.name, f.path, f.lang"
    ```
    *Expected:* All files from your sample project should be listed with the correct `lang` tag.

*   **Check for functions:**
    ```bash
    cgc query "MATCH (f:File)-[:CONTAINS]->(fn:Function) WHERE f.path STARTS WITH '/path/to/your/sample_project' AND fn.lang = '<your_language_name>' RETURN f.name AS FileName, fn.name AS FunctionName, fn.line_number AS Line"
    ```
    *Expected:* All functions from your sample project should be listed.

*   **Check for classes:**
    ```bash
    cgc query "MATCH (f:File)-[:CONTAINS]->(c:Class) WHERE f.path STARTS WITH '/path/to/your/sample_project' AND c.lang = '<your_language_name>' RETURN f.name AS FileName, c.name AS ClassName, c.line_number AS Line"
    ```
    *Expected:* All classes from your sample project should be listed.

*   **Check for imports (module-level):**
    ```bash
    cgc query "MATCH (f:File)-[:IMPORTS]->(m:Module) WHERE f.path STARTS WITH '/path/to/your/sample_project' AND f.lang = '<your_language_name>' RETURN f.name AS FileName, m.name AS ImportedModule, m.full_import_name AS FullImportName"
    ```
    *Expected:* All module-level imports should be listed.

*   **Check for function calls:**
    ```bash
    cgc query "MATCH (caller:Function)-[:CALLS]->(callee:Function) WHERE caller.path STARTS WITH '/path/to/your/sample_project' AND caller.lang = '<your_language_name>' RETURN caller.name AS Caller, callee.name AS Callee, caller.path AS CallerFile, callee.path AS CalleeFile"
    ```
    *Expected:* All function calls should be correctly linked.

*   **Check for class inheritance:**
    ```bash
    cgc query "MATCH (child:Class)-[:INHERITS]->(parent:Class) WHERE child.path STARTS WITH '/path/to/your/sample_project' AND child.lang = '<your_language_name>' RETURN child.name AS ChildClass, parent.name AS ParentClass, child.path AS ChildFile, parent.path AS ParentFile"
    ```
    *Expected:* All inheritance relationships should be correctly linked.

### Step 3.4: Debugging Common Issues

*   **`NameError: Invalid node type ...`**: Your tree-sitter query is using a node type that doesn't exist in the language's grammar. Use `tree-sitter parse` to inspect the AST.
*   **Missing Relationships (e.g., `CALLS`, `IMPORTS`)**:
    *   **Check `_find_*` methods**: Ensure your `_find_*` methods are correctly extracting the necessary data.
    *   **Check `imports_map`**: Verify that the `pre_scan_<lang>` function is correctly populating the `imports_map`.
    *   **Check `local_imports` map**: Ensure the `local_imports` map (built in `_create_function_calls` and `_create_inheritance_links`) is correctly resolving symbols.
*   **Incorrect `lang` tags**: Ensure `self.language_name` is correctly passed and stored.

By following these steps, contributors can effectively add and verify new language support.
