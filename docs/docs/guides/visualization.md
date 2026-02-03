# Visualizing the Graph

Sometimes a table of text isn't enough. You need to see the map.

## 1. Browser link (`cgc visualize`)

The easiest way involves the `cgc visualize` command (alias `cgc v`).

```bash
cgc visualize
```

This will print a URL (e.g., `http://localhost:7474/browser?cmd=edit&arg=MATCH...`).
Clicking this links opens the **Neo4j Browser** with a pre-filled query to show the immediate neighborhood of your code.

## 2. Using Neo4j Bloom (Advanced)

If you are using Neo4j Desktop, you can use **Bloom**.
*   Bloom allows "Google Maps" style zooming.
*   Type logical phrases like "Show me callers of X".

## 3. Interactive Web View (Coming Soon)

We are building a lightweight React-based visualizer that runs directly from `cgc analyze --viz`.
*   [View Roadmap](../roadmap.md)
