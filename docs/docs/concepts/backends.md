# Database Backends

CodeGraphContext is backend-agnostic. It supports multiple graph database engines to balance performance, ease of use, and scalability.

## Comparison Overview

| Backend | Mode | Best For | Complexity |
| :--- | :--- | :--- | :--- |
| **KùzuDB** | Embedded | Local development, quick starts | Zero Config |
| **FalkorDB** | Embedded/Remote | High-performance semantic queries | Low to Medium |
| **Neo4j** | Server | Enterprise-scale, visualization | High |

---

## 1. KùzuDB (Embedded)

KùzuDB is the **default recommendation** for most users. It is an extremely lightweight, in-process graph database.

*   **Zero Infrastructure**: No Docker or separate services required.
*   **Performance**: Optimized for analytical queries (OLAP) on graph data.
*   **Storage**: Saves the graph as a directory on your local machine (usually in `.codegraphcontext/`).

**Installation**:
```bash
pip install real_ladybug
```

## 2. FalkorDB (High Performance)

FalkorDB is a low-latency graph database designed for massive throughput.

*   **Speed**: One of the fastest graph engines available for relationship traversal.
*   **Modes**:
    *   **FalkorDB Lite**: Runs as an embedded engine (Linux/macOS only).
    *   **FalkorDB Remote**: Connects to a standard Redis-based FalkorDB instance.

**Installation (Lite)**:
```bash
pip install falkordblite
```

## 3. Neo4j (Enterprise)

Neo4j is the industry standard for graph databases. Use Neo4j when you need advanced visualization or are working with exceptionally large datasets.

*   **Visualization**: Use the **Neo4j Browser** (`localhost:7474`) to see your code graph in a rich, interactive UI.
*   **Scalability**: Handles billions of nodes and relationships across distributed environments.

**Setup**:
1.  Start Neo4j via Docker or use AuraDB.
2.  Configure CGC to use Neo4j:
    ```bash
    cgc config set-db neo4j
    cgc config set-neo4j-uri bolt://localhost:7687
    ```

---

## Backend Selection Logic

CGC follows a specific priority when deciding which backend to use:

1.  **Explicit**: Any database specified via the `--database` flag or `CGC_RUNTIME_DB_TYPE` env var.
2.  **Configured**: The default set via `cgc config db`.
3.  **Automatic**:
    *   **Remote FalkorDB**: If `FALKORDB_HOST` is detected.
    *   **Unix**: Tries FalkorDB Lite → KùzuDB → Neo4j.
    *   **Windows**: Tries KùzuDB → Neo4j.
