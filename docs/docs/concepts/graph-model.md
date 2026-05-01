# The Code Graph Model

CodeGraphContext represents your source code as a **Property Graph**. This model allows for complex relationship mapping that traditional text-based search cannot achieve.

## Nodes

Nodes represent the structural entities within your codebase. Each node has a set of properties (e.g., `name`, `path`, `start_line`).

| Label | Description |
| :--- | :--- |
| **Repository** | The root node of a project. |
| **File** | A source file on disk. |
| **Module** | A logical grouping of code (e.g., Python package/module). |
| **Class** | Object-oriented class definitions. |
| **Function** | Methods and standalone functions. |
| **Variable** | Global or local variable definitions. |

## Relationships

Relationships (Edges) define how these entities interact.

| Relationship | Direction | Description |
| :--- | :--- | :--- |
| `CONTAINS` | `File` → `Function` | Ownership hierarchy. |
| `CALLS` | `Function` → `Function` | A direct call from one function to another. |
| `IMPORTS` | `File` → `Module` | Dependency link between files/modules. |
| `INHERITS` | `Class` → `Class` | Class inheritance hierarchy. |
| `IMPLEMENTS` | `Class` → `Interface` | Interface implementation (for supported languages). |

## Language Support

CGC uses **Tree-sitter** parsers to extract these entities across multiple languages.

*   **Primary Support**: Python, JavaScript, TypeScript, Java, C++, Go.
*   **Secondary Support**: Ruby, PHP, Rust, C#, and more.

## Why a Graph?

By using a graph, CGC can perform "multi-hop" queries that are impossible with regex or symbol tables alone:

1.  **Call Chains**: Find every function that eventually calls `process_payment()`.
2.  **Impact Analysis**: See which modules are affected if a specific class is modified.
3.  **Dead Code Detection**: Identify functions that have no incoming `CALLS` relationships from the rest of the application.

---

For advanced users, you can query this graph directly using **Cypher**. See the **[CLI Reference](../reference/cli.md)** for details on the `query` command.
