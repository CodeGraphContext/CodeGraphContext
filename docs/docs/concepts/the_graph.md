# The Graph Model

What does "Code as a Graph" actually look like?

## Nodes (The Nouns)

The graph contains these primary node types:

*   **`File`**: A physical file on disk (e.g., `main.py`).
*   **`Function`**: A function definition (e.g., `def process_data()`).
*   **`Class`**: A class definition (e.g., `class User`).
*   **`Module`**: A logical grouping (e.g., a Python package).
*   **`Import`**: Represents an external dependency (e.g., `import requests`).

## Relationships (The Verbs)

Edges connect the nodes to describe interaction:

*   `(:Function)-[:CALLS]->(:Function)`: Function A calls Function B.
*   `(:Class)-[:INHERITS]->(:Class)`: Class A extends Class B.
*   `(:File)-[:CONTAINS]->(:Function)`: Where the code lives.
*   `(:File)-[:IMPORTS]->(:Module)`: Dependency usage.

## Example Query

Using Cypher, you can query this structure:

```cypher
// Find all classes that inherit from 'BaseModel'
MATCH (c:Class)-[:INHERITS]->(p:Class {name: 'BaseModel'})
RETURN c.name
```
