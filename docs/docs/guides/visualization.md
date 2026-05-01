# Visualizing the Graph

Sometimes a table of text is not enough—you need to see the map. CodeGraphContext ships a local visualization server and also offers a hosted explorer.

## Local server: `cgc visualize`

Run:

```bash
cgc visualize
```

This starts a **local FastAPI server** that serves a **React** visualization of your current graph. Open the URL printed in the terminal (typically `http://127.0.0.1` with a chosen port).

### Modes

The UI supports several views of the same graph data:

- **2D force-directed graph** — classic node–link layout for navigation and clustering.
- **3D force-directed graph** — spatial exploration of larger graphs.
- **3D city view** — an alternative structural layout for hierarchy and density.
- **Mermaid flowchart** — diagram-style export and inspection of selected subgraphs.

Use the in-app controls to switch modes and focus on the neighborhood you care about.

## Hosted explorer

You can also open the public site **[codegraphcontext.vercel.app/explore](https://codegraphcontext.vercel.app/explore)** to explore graphs in the browser (including flows that align with bundle and registry workflows).

## Neo4j users: Neo4j Browser and Bloom

If your **`DEFAULT_DATABASE`** (or config) points at **Neo4j**, you can still use **Neo4j Browser** (and **Neo4j Bloom** on Desktop) for Cypher-centric exploration. The local `cgc visualize` experience is backend-agnostic where supported; Neo4j-specific URLs and tools remain available when Neo4j is your active backend.

---

For CLI details and options, see the CLI reference for the `visualize` command.
