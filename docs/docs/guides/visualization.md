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

### Natural-language graph queries with API Route

The visualizer's AI query feature can use [API Route](https://www.api-route.com),
an OpenAI-compatible gateway. Set your key before starting the server:

```bash
export API_ROUTE_API_KEY="your-api-route-key"
cgc visualize
```

The default endpoint is `https://global.api-route.com/v1` and the default model
is `gpt-6.1-sol`. Set `API_ROUTE_API_BASE` or `API_ROUTE_MODEL` to override them
with an endpoint or model available to your account.

When multiple provider keys are configured, Gemini, OpenAI, Atlas Cloud and
Cheaper Inference retain their existing priority over API Route. Use only the
API Route key for this server process to select it. AI queries send the question,
graph schema and query results to the selected provider to generate and explain
read-only Cypher queries.

### Natural-language graph queries with Runcrate

The AI query feature can also use [Runcrate](https://www.runcrate.ai/?utm_source=codegraphcontext&utm_medium=directory&utm_campaign=gpu_pricing),
an OpenAI-compatible API for open models (open models are free with your GitHub account).
Set your key before starting the server:

```bash
export RUNCRATE_API_KEY="your-runcrate-key"
cgc visualize
```

The default endpoint is `https://api.runcrate.ai/v1` and the default model is
`deepseek-ai/DeepSeek-V4.1-Flash`. Set `RUNCRATE_API_BASE` or `RUNCRATE_MODEL` to
override them, for example `RUNCRATE_MODEL=openai/gpt-oss-120b`.

Gemini, OpenAI, Atlas Cloud, Cheaper Inference and API Route keep their priority
over Runcrate; use only the Runcrate key for this server process to select it.
AI queries send the question, graph schema and query results to the selected
provider to generate and explain read-only Cypher queries.

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
