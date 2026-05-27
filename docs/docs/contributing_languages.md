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
