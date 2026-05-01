# Visualizing the Code Graph

Visualizing your codebase can help reveal architectural patterns, circular dependencies, and complex call chains that are difficult to see in raw code.

## 1. CLI Visualization

CGC provides a quick way to visualize the graph directly from the terminal.

```bash
cgc visualize
```

This command generates a temporary visualization file (usually an HTML file with an interactive graph) and opens it in your default web browser.

### Visualizing Specific Queries
You can visualize the result of a specific relationship query:

```bash
cgc visualize --query "callers find_request_handler"
```

---

## 2. Interactive Analysis with Neo4j

If you are using the **Neo4j** backend, you can leverage the full power of the **Neo4j Browser**.

1.  **Start Neo4j**: Ensure your Neo4j container or service is running.
2.  **Access Browser**: Open `http://localhost:7474` in your browser.
3.  **Run Cypher**: Write custom Cypher queries to explore the graph visually.

### Example: Visualizing a Module Hierarchy
```cypher
MATCH (m:Module)-[:CONTAINS]->(c:Class)
RETURN m, c
```

---

## 3. Visualizing via MCP Tools

When using CGC with an AI assistant (like Cursor or Claude), the AI can generate visualization URLs for you.

**Ask the AI**:
> "Visualize the call chain leading to the `process_order` function."

The AI will call the `visualize_graph_query` tool and provide you with a link to view the resulting graph.

---

## Common Visualization Types

*   **Call Graphs**: Showing which functions call which others.
*   **Dependency Graphs**: Mapping imports between files and modules.
*   **Class Hierarchies**: Visualizing inheritance and implementations.
*   **Complexity Heatmaps**: (Experimental) Nodes sized or colored by their cyclomatic complexity.
