# How to Add Language-Specific Features

This document outlines the standard pattern for extending the CodeGraphContext tool to support new, language-specific code constructs (like Go interfaces, Rust traits, Dart mixins, C++ macros, etc.).

## Core Philosophy

The system is designed with a clear separation of concerns:
1.  **Language-Specific Parsers:** Located in `src/codegraphcontext/tools/languages/`, these are responsible for understanding the syntax of a single language and extracting its constructs into a standardized Python dictionary.
2.  **Generic Graph Builder:** The `GraphBuilder` in `src/codegraphcontext/tools/graph_builder.py` consumes these dictionaries and is responsible for creating nodes and relationships in the **graph database (FalkorDB/KuzuDB/Neo4j, depending on configuration)**. It is language-agnostic.

Adding a new feature always involves these two steps: **(1) Specialize the Parser** and **(2) Generalize the Builder**.

---

## Step-by-Step Guide: Adding a New Node Type

We will walk through two examples:
1.  Adding support for Go `interface` nodes.
2.  Adding support for C/C++ `macro` nodes.

### Part 1: Modify the Language Parser

Your first goal is to teach the correct language parser to identify the new construct and return it under a unique key.

#### Example: Go Interfaces

**File to Edit:** `src/codegraphcontext/tools/languages/go.py`

**1. Add a Tree-sitter Query:**
Ensure a query exists in the `GO_QUERIES` dictionary to find the construct.

```python
GO_QUERIES = {
    # ... existing queries
    "interfaces": """
        (type_declaration
            (type_spec
                name: (type_identifier) @name
                type: (interface_type) @interface_body
            )
        ) @interface_node
    """,
}
```

**2. Create a Dedicated Parsing Method:**
Create a new method in the `GoTreeSitterParser` class to handle the results from your new query.

```python
# In GoTreeSitterParser class
def _find_interfaces(self, root_node):
    interfaces = []
    interface_query = self.queries['interfaces']
    for node, capture_name in interface_query.captures(root_node):
        if capture_name == 'name':
            interface_node = self._find_type_declaration_for_name(node)
            if interface_node:
                name = self._get_node_text(node)
                interfaces.append({
                    "name": name,
                    "line_number": interface_node.start_point[0] + 1,
                    "end_line": interface_node.end_point[0] + 1,
                    "source": self._get_node_text(interface_node),
                })
    return interfaces
```

**3. Update the Main `parse` Method:**
In the parser's main `parse` method, call your new function and add its results to the dictionary that gets returned. **The key you use here (e.g., `"interfaces"`) is what the Graph Builder will use.**

```python
# In GoTreeSitterParser.parse()
def parse(self, path: Path, is_dependency: bool = False) -> Dict:
    # This comment explains the pattern for future developers.
    # This method orchestrates the parsing of a single file.
    # It calls specialized `_find_*` methods for each language construct.
    # The returned dictionary should map a specific key (e.g., 'functions', 'interfaces')
    # to a list of dictionaries, where each dictionary represents a single code construct.
    # The GraphBuilder will then use these keys to create nodes with corresponding labels.
    with open(path, "r", encoding="utf-8") as f:
        source_code = f.read()

    tree = self.parser.parse(bytes(source_code, "utf8"))
    root_node = tree.root_node

    functions = self._find_functions(root_node)
    structs = self._find_structs(root_node)
    interfaces = self._find_interfaces(root_node) # Call the new method
    # ... find other constructs

    return {
        "path": str(path),
        "functions": functions,
        "classes": structs,      # Structs are mapped to the generic :Class label
        "interfaces": interfaces, # The new key-value pair
        "variables": variables,
        "imports": imports,
        "function_calls": function_calls,
        "is_dependency": is_dependency,
        "lang": self.language_name,
    }
```

---

### Part 2: Update the Generic Graph Builder

Now, teach the `GraphBuilder` how to handle the new key (e.g., `"interfaces"`) produced by the parser.

**File to Edit:** `src/codegraphcontext/tools/graph_builder.py`

**1. Add a Schema Constraint:**
Add a uniqueness constraint (or equivalent) for the new node label you are introducing (e.g., `:Interface`, `:Macro`). This is crucial for data integrity.

Schema creation is **not** done with ad-hoc `session.run("CREATE CONSTRAINT...")` in the graph builder anymore; persistence goes through **`GraphWriter`** in `src/codegraphcontext/tools/indexing/persistence/writer.py`, with schema definitions coordinated via **`src/codegraphcontext/tools/indexing/schema.py`**. Extend those modules (and any backend-specific paths they delegate to) when you add new labels or constraints so all four backends stay consistent.

**2. Update the Node Creation Loop:**
File-to-graph ingestion is routed through **`GraphWriter`** (the old `add_file_to_graph`-style loop lives there). There is typically a mapping from parser keys to node labels (conceptually similar to an `item_mappings` list). Add your new construct there so **`GraphWriter`** persists it like other node types.

```python
# Conceptual pattern (actual code lives in GraphWriter / graph pipeline)

# 1. Ensure your language-specific parser returns a list under a unique key (e.g., 'traits': [...] or 'mixins': [...] ).
# 2. Add schema for the new label via indexing/schema.py and GraphWriter.
# 3. Register the new key in the writer’s mappings (e.g., (file_data.get('traits', []), 'Trait') or (file_data.get('mixins', []), 'Mixin') ).
item_mappings = [
    (file_data.get('functions', []), 'Function'),
    (file_data.get('classes', []), 'Class'),
    (file_data.get('variables', []), 'Variable'),
    (file_data.get('interfaces', []), 'Interface'), # Added for Go
    (file_data.get('macros', []), 'Macro')         # Added for C/C++
]
for item_data, label in item_mappings:
    for item in item_data:
        # ... generic node creation logic (handled by GraphWriter)
```
Using `file_data.get('macros', [])` ensures ingestion does not fail if a language parser (like Python's) doesn't produce a `macros` key.

---

## Advanced Topic: Scaling with Multi-Labeling

A valid concern is the proliferation of node labels. A more advanced pattern is to use multiple labels to capture both specific and general concepts.

For example:
- A Go interface node could have the labels: `[:Interface, :Contract, :Go]`
- A Rust trait node could have the labels: `[:Trait, :Contract, :Rust]`

This allows for powerful, cross-language queries (e.g., `MATCH (c:Contract)`) while retaining language-specific details.

This can be implemented in **`GraphWriter`** (during per-file node creation) by dynamically constructing the label string based on the data provided by the parser, which already includes a `lang` key.
