# CLI: Analysis & Querying

These commands allow you to extract insights from your indexed code.

## Code Analysis

### `analyze callers`
Finds every function that calls a specific function. Essential for "Impact Analysis" before refactoring.

**Usage:**
```bash
cgc analyze callers <func_name>
```

### `analyze calls`
The reverse of `callers`. Shows what a specific function calls.

**Usage:**
```bash
cgc analyze calls <func_name>
```

### `analyze chain`
Connects the dots. Finds the path of execution between two functions.

**Usage:**
```bash
cgc analyze chain <start_func> <end_func> --depth 5
```

### `analyze deps`
Shows dependencies and imports for a specific module.

**Usage:**
```bash
cgc analyze deps <module>
```

### `analyze tree`
Visualizes the Class Inheritance hierarchy for a given class.

**Usage:**
```bash
cgc analyze tree <class_name>
```

### `analyze complexity`
Finds functions that are difficult to maintain (Cyclomatic Complexity).

**Usage:**
```bash
cgc analyze complexity --threshold 10
```

### `analyze dead-code`
Finds potentially unused functions (0 callers).

**Usage:**
```bash
cgc analyze dead-code --exclude "@route"
```

### `analyze overrides`
Shows methods that override parent class methods.

**Usage:**
```bash
cgc analyze overrides <class_name>
```

### `analyze variable`
Analyzes where a variable is defined and used.

**Usage:**
```bash
cgc analyze variable <var_name>
```

---

## Discovery & Search

### `find pattern`
Fuzzy search for code elements. Use this when you don't know the exact name.

**Usage:**
```bash
cgc find pattern <text>
```

### `find name`
Finds code elements (Class, Function) by their **exact** name.

**Usage:**
```bash
cgc find name <name>
```

### `find type`
List all nodes of a specific type.

**Usage:**
```bash
cgc find type <type>
```

**Supported Types:**

*   `class`: Find all classes.
*   `function`: Find all functions/methods.
*   `module`: Find all indexed files/modules.

**Example:**
```bash
# Find all classes in the codebase
cgc find type class
```

### `find content`
Full-text search across your source code and docstrings.

**Usage:**
```bash
cgc find content "search term"
```

### `find decorator`
Finds all functions that are decorated with a specific decorator.

**Usage:**
```bash
cgc find decorator @app.route
```

### `find argument`
Finds all functions that define a specific argument name.

**Usage:**
```bash
cgc find argument user_id
```
