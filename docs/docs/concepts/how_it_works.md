# How It Works

Understanding the pipeline helps you write better queries.

## 1. Parsing (Tree-Sitter)
We use **Tree-Sitter** to parse your source code into an Abstract Syntax Tree (AST). This allows us to support many languages (Python, JS, Go, etc.) with high accuracy.

## 2. Graph Construction
We walk the AST and generate **Nodes** and **Edges**.

*   **Nodes:** Entities like `Class`, `Function`, `File`, `Module`.
*   **Edges:** Relationships like `CALLS`, `IMPORTS`, `INHERITS`.

## 3. Storage
These nodes and edges are written to the Graph Database (FalkorDB or Neo4j).

## 4. Querying
When you ask "Who calls X?", we translate that into a Cypher query:

```cypher
MATCH (caller:Function)-[:CALLS]->(callee:Function {name: 'X'})
RETURN caller
```
