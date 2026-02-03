# How to Add Language-Specific Features

This document outlines the standard pattern for extending the CodeGraphContext tool to support new, language-specific code constructs (like Go interfaces, Rust traits, C++ macros, etc.).

## Core Philosophy

The system is designed with a clear separation of concerns:
1.  **Language-Specific Parsers:** Located in `src/codegraphcontext/tools/languages/`, these are responsible for understanding the syntax of a single language and extracting its constructs into a standardized Python dictionary.
2.  **Generic Graph Builder:** The `GraphBuilder` in `src/codegraphcontext/tools/graph_builder.py` consumes these dictionaries and is responsible for creating nodes and relationships in the Neo4j database. It is language-agnostic.

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
In the `create_schema` method, add a uniqueness constraint for the new Neo4j node label you are introducing (e.g., `:Interface`, `:Macro`). This is crucial for data integrity.

```python
# In GraphBuilder.create_schema()
def create_schema(self):
    """Create constraints and indexes in Neo4j."""
    # When adding a new node type with a unique key, add its constraint here.
    with self.driver.session() as session:
        try:
            # ... existing constraints
            session.run("CREATE CONSTRAINT class_unique IF NOT EXISTS FOR (c:Class) REQUIRE (c.name, c.path, c.line_number) IS UNIQUE")
            
            # Add constraints for the new types
            session.run("CREATE CONSTRAINT interface_unique IF NOT EXISTS FOR (i:Interface) REQUIRE (i.name, i.path, i.line_number) IS UNIQUE")
            session.run("CREATE CONSTRAINT macro_unique IF NOT EXISTS FOR (m:Macro) REQUIRE (m.name, m.path, m.line_number) IS UNIQUE")
            
            # ... other schema items
```

**2. Update the Node Creation Loop:**
In the `add_file_to_graph` method, there is a list called `item_mappings`. Add your new construct to this list. The builder will handle the rest automatically.

```python
# In GraphBuilder.add_file_to_graph()

# To add a new language-specific node type (e.g., 'Trait' for Rust):
# 1. Ensure your language-specific parser returns a list under a unique key (e.g., 'traits': [...] ).
# 2. Add a new constraint for the new label in the `create_schema` method.
# 3. Add a new entry to the `item_mappings` list below (e.g., (file_data.get('traits', []), 'Trait') ).
item_mappings = [
    (file_data.get('functions', []), 'Function'),
    (file_data.get('classes', []), 'Class'),
    (file_data.get('variables', []), 'Variable'),
    (file_data.get('interfaces', []), 'Interface'), # Added for Go
    (file_data.get('macros', []), 'Macro')         # Added for C/C++
]
for item_data, label in item_mappings:
    for item in item_data:
        # ... generic node creation logic
```
Using `file_data.get('macros', [])` ensures that the builder doesn't fail if a language parser (like Python's) doesn't produce a `macros` key.

---

## Advanced Topic: Scaling with Multi-Labeling

A valid concern is the proliferation of node labels. A more advanced pattern is to use multiple labels to capture both specific and general concepts.

For example:
- A Go interface node could have the labels: `[:Interface, :Contract, :Go]`
- A Rust trait node could have the labels: `[:Trait, :Contract, :Rust]`

This allows for powerful, cross-language queries (e.g., `MATCH (c:Contract)`) while retaining language-specific details.

This can be implemented in `add_file_to_graph` by dynamically constructing the label string based on the data provided by the parser, which already includes a `lang` key.
