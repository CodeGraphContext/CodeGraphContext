# Prerequisites

Before you install CodeGraphContext (CGC), it helps to see how the pieces fit. CGC is a **client–server style** system even on a laptop: a **Python engine**, a **graph database backend**, and **clients** (CLI and/or MCP).

## The three roles

1. **Engine (this package)** — Parses code, builds the graph, and talks to the database through a single abstraction API.
2. **Database** — Stores nodes and relationships (“function A calls function B”, containment, imports, …).
3. **Clients**
   - **CLI** — `cgc` in the terminal.
   - **MCP** — AI-capable editors (Cursor, VS Code, Claude Desktop, and other MCP hosts).

## System requirements

| Requirement | Notes |
| :---------- | :---- |
| **OS** | Linux, macOS, or Windows (WSL is a good option on Windows). |
| **Python** | **3.10+** for CGC generally. **FalkorDB Lite** (default embedded path on Unix) requires **Python 3.12+**. |
| **Memory** | At least **4 GB RAM** recommended; larger repos and graph stores benefit from more. |

## Database options

You do not need to manually install every backend—pick one flow during setup. Use this table to decide:

| Option | Best for | Complexity |
| :----- | :------- | :--------- |
| **FalkorDB Lite** | **Recommended on Linux and macOS** for local development: embedded use, minimal setup. Requires **Python 3.12+**. | Low |
| **FalkorDB Remote** | Teams or shared graphs: connect to a **remote** FalkorDB server instead of embedded Lite. | Low–medium |
| **KuzuDB** | **Recommended on Windows** (and anywhere you want a **portable embedded** graph without FalkorDB Lite). Good **fallback** when FalkorDB is not the right fit. | Low |
| **Neo4j** | **Production / enterprise**: operational tooling, clustering, and mature Neo4j ecosystem. | Medium–high |

!!! note "Python version and FalkorDB Lite"

    If you are on Linux or macOS and want the **default** embedded experience, plan for **Python 3.12 or newer** so **FalkorDB Lite** is available. On older Python versions, choose **KuzuDB**, **FalkorDB Remote**, or **Neo4j** according to your environment.

## AI assistant (optional)

To use CGC from an AI workflow you need an **MCP-capable client**. Examples:

- [Cursor](https://cursor.sh)
- [Visual Studio Code](https://code.visualstudio.com/)
- [Claude Desktop](https://claude.ai/download)

Any other MCP-compatible agent or IDE can integrate the same way.
