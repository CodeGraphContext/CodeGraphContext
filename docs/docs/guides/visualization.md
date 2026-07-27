# Interactive Graph Visualization

Visualizing your code graph helps identify complex call paths, cyclical dependencies, and architectural anomalies. CodeGraphContext includes a built-in React-based interactive force-directed graph visualizer.

---

## 1. Running the Local Visualizer Server

Start the local visualization server using the `visualize` command:

```bash
cgc visualize
```

By default, this command:
1. Resolves the active database context.
2. Launches a FastAPI web server on port **8000**.
3. Opens your default web browser to `http://localhost:8000`.

### Custom Port & Repo Overrides
Specify a custom port or target repository path when starting the server:

```bash
# Run server on port 9000 for a specific repository
cgc visualize --repo ~/projects/my-api --port 9000

# Use a specific named context database
cgc visualize --context StagingGraph
```

---

## 2. Using the Interactive UI

The browser interface serves a force-directed graph showing your codebase structures:

- **Node Interactions**: Click on any node (file, class, function) to view its code details, extracted signatures, cyclomatic complexity scores, and docstrings in the detail pane.
- **Dynamic Search**: Use the search filter to highlight specific symbols.
- **Relationship Filters**: Toggle visibility of relationship edges (e.g., hiding `IMPORTS` to focus exclusively on execution `CALLS` flow).
- **Navigation Controls**: Zoom, pan, and drag nodes to isolate call loops and modules.

---

## 3. Neo4j Browser Visualizations (Neo4j Backend Only)

If you are using Neo4j as your active database backend, you can leverage the native **Neo4j Browser Console** for complex Cypher queries.

1. Open your browser and navigate to the Neo4j Console (typically `http://localhost:7474`).
2. Log in using your configured credentials.
3. Execute a Cypher query to retrieve and render graph structures:

```cypher
// Visualize all functions called by the "process_payment" function
MATCH (f1:Function {name: 'process_payment'})-[r:CALLS]->(f2:Function)
RETURN f1, r, f2
```
