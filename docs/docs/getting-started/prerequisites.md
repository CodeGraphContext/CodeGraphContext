# Prerequisites & Context

Before installing CodeGraphContext (CGC), it helps to understand the pieces involved. CGC is a **Client-Server system**, even if you run it all on your laptop.

## The Three Components

1.  **The Engine (This Tool)**
    *   A Python package responsible for parsing code and talking to the database.
2.  **The Database**
    *   Where the graph lives. CGC needs a place to store "Function A calls Function B".
3.  **The Client**
    *   **CLI:** Your terminal.
    *   **MCP:** Your AI Editor (Cursor, VS Code, Claude).

---

## 💻 System Requirements

*   **OS:** Linux, macOS, or Windows (WSL recommended).
*   **Python:** 3.10 or higher.
*   **Memory:** At least 4GB RAM (Graph DBs love RAM).

## 🗄️ Database Options (Context)

You do **not** need to install a database yet. The installer will help you. But you should know your choice:

| Option | Best For... | Complexity |
| :--- | :--- | :--- |
| **FalkorDB Lite** | **Quick Start / Linux / macOS.** Runs inside Python. No extra setup. | ⭐ |
| **Neo4j** | **Windows / Production / Large Team.** Persistent storage. Requires Docker or Desktop App. | ⭐⭐⭐ |

---

## 🤖 AI Assistant (Optional)

If you plan to use CGC with an AI, you need an **MCP-compliant client**. We officially support:

*   [Cursor IDE](https://cursor.sh)
*   [VS Code](https://code.visualstudio.com/) 
*   [Claude Desktop App](https://claude.ai/download)
*   ...and **any other tool** relevant to Agentic Coding that supports the Model Context Protocol.
