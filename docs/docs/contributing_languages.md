# Adding Language Support

This guide outlines the steps required to add parsing support for a new programming language to CodeGraphContext.

---

## 1. Architectural Integration

CGC uses a modular parsing system based on Tree-sitter:

1. **`TreeSitterParser` (`graph_builder.py`)**: The primary generic wrapper that dispatches files to specific language sub-parsers.
2. **Language Parser Modules (`src/codegraphcontext/tools/languages/`)**: Individual python modules containing:
   - Tree-sitter AST tags queries (`<LANG>_QUERIES`).
   - A `<Lang>TreeSitterParser` class inheriting from the parser interface.
   - A `pre_scan_<lang>` method for rapid initial symbol caching.
3. **`GraphBuilder`**: Dispatches files to language parsers, resolves imports, and feeds nodes/relationships to the persistence drivers.

---

## 2. Step-by-Step Implementation

### Step A: Create the Language Parser Module
Create a new file under `src/codegraphcontext/tools/languages/` (e.g., `typescript.py`).

Add standard parser imports:
```python
from pathlib import Path
from typing import Dict, Any, List
from codegraphcontext.tools.languages.base import BaseParser
```

### Step B: Define AST Tag Queries
AST tags are parsed using Tree-sitter query expressions. Define queries to target:
- **`functions`**: Standard functions, methods, arrow assignments.
- **`classes`**: Class and interface boundaries.
- **`imports`**: Syntax specifying external file or module dependencies.
- **`calls`**: Function or method invocations.
- **`variables`**: Variable declarations and assignments.

*Tip: Use the CLI `tree-sitter parse` tool to inspect a sample source file's Concrete Syntax Tree (CST) and locate the correct node name keys.*

### Step C: Implement the Parser Class
Inherit from the base parser and implement AST extraction routines:

```python
class TypescriptTreeSitterParser(BaseParser):
    def __init__(self, generic_parser):
        super().__init__(generic_parser, "typescript")
        self.queries = self.load_queries()

    def parse(self, path: Path, is_dependency: bool = False) -> Dict[str, Any]:
        content = path.read_text()
        tree = self.parser.parse(bytes(content, "utf8"))
        
        # Populate and return standardized AST data structures
        return {
            "functions": self._find_functions(tree, content),
            "classes": self._find_classes(tree, content),
            "calls": self._find_calls(tree, content),
            "imports": self._find_imports(tree, content),
            "variables": self._find_variables(tree, content),
        }
```

### Step D: Implement the Fast Pre-Scan
Define a fast pre-scan routine to map declaration locations before linking call relationships:

```python
def pre_scan_typescript(files: List[Path], parser_wrapper) -> Dict[str, Path]:
    # Returns a dictionary mapping class/function symbol names to file paths.
    ...
```

### Step E: Register the Parser
Map the file extension to the new parser class in `parser_factory.py`:

```python
# Map extension inside the registry
SUPPORTED_LANGUAGES = {
    ".ts": "typescript",
    ".tsx": "typescript",
}
```

---

## 3. Verification & Diagnostic Queries

Once the parser is registered, verify graph extraction using sample source files:

1. **Index a test codebase**:
   ```bash
   cgc index ./tests/fixtures/sample_ts_project/ --force
   ```
2. **Execute verification queries using Cypher**:
   - Verify files are parsed:
     ```bash
     cgc query "MATCH (f:File) RETURN f.path, f.language"
     ```
   - Verify functions are identified:
     ```bash
     cgc query "MATCH (f:File)-[:CONTAINS]->(fn:Function) RETURN f.path, fn.name"
     ```
   - Verify caller links:
     ```bash
     cgc query "MATCH (caller:Function)-[:CALLS]->(callee:Function) RETURN caller.name, callee.name"
     ```

### Emacs Lisp smoke check

Emacs Lisp support uses the `elisp` grammar already distributed by `tree-sitter-language-pack`; no external Emacs process or manual grammar compilation is required for the Tree-sitter path.

To smoke-test the checked-in two-file fixture against an isolated Kuzu database:

```bash
tmpdir=$(mktemp -d)
export PYTHONPATH=src
export DEFAULT_DATABASE=kuzudb
export CGC_RUNTIME_DB_TYPE=kuzudb
export CGC_RUNTIME_DB_PATH="$tmpdir/kuzu.db"

uv run python -m codegraphcontext index tests/fixtures/sample_projects/sample_project_elisp --force

uv run python -m codegraphcontext query "MATCH (f:File) WHERE f.path ENDS WITH '.el' RETURN f.name AS file ORDER BY file"
uv run python -m codegraphcontext query "MATCH (fn:Function) WHERE fn.lang = 'elisp' RETURN fn.name AS function ORDER BY function"
uv run python -m codegraphcontext query "MATCH (v:Variable) WHERE v.lang = 'elisp' RETURN v.name AS variable ORDER BY variable"
uv run python -m codegraphcontext query "MATCH (f:File)-[:IMPORTS]->(m:Module) RETURN f.name AS file, m.name AS module ORDER BY file, module"
uv run python -m codegraphcontext query "MATCH (caller:Function)-[:CALLS]->(callee:Function) WHERE caller.lang = 'elisp' RETURN caller.name AS caller_name, callee.name AS callee_name ORDER BY caller_name, callee_name"

rm -rf "$tmpdir"
```

Expected results include `foo-core.el` and `foo-ui.el`, function nodes such as `foo-core-greet` and `foo-ui-render`, variable nodes such as `foo-core-count` and `foo-core-loud`, module nodes for `cl-lib`, `foo-core`, and `foo-ui`, and direct call edges including `foo-ui-render -> foo-core-greet` and `foo-core-greet -> foo-core-format`.

### Emacs Lisp SCIP follow-up

The initial Emacs Lisp implementation intentionally stays on the Tree-sitter pipeline. There is no standard `scip-elisp` indexer to register in `EXTENSION_TO_SCIP`, and the commonly used `elisp-refs` package is designed as an interactive Emacs reference finder rather than a batch indexer: it searches files recorded in the running Emacs `load-history`, renders results in a special buffer instead of emitting JSON or SCIP data, and exposes useful Lisp-2 function/variable heuristics only through internal APIs.

A future semantic indexer could reuse those heuristics in a dedicated batch wrapper, but it would still need directory discovery, side-effect-safe loading or buffer creation, line/column conversion from character offsets, structured output, and explicit handling for macro expansion and indirect calls. Until that exists, `.el` files should continue to use Tree-sitter indexing with documented limitations around arbitrary macro semantics and dynamic dispatch.
