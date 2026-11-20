# System Prerequisites

CodeGraphContext (CGC) can run locally with an embedded graph engine or connect to a graph server. To ensure a successful installation, understand the primary roles and requirements of the environment.

---

## Architecture Components

1. **The Ingestion Engine**: The core Python package responsible for scanning source directories, running Tree-sitter and SCIP syntax parsers, and linking references.
2. **The Graph Storage Layer**: The database backend containing nodes and edges representing code entities and their interactions.
3. **The Interface Clients**:
    - **CLI (`cgc`)**: Terminal interface used for managing indices, running analytical searches, and system diagnostics.
    - **MCP Server**: Gateway enabling Model Context Protocol communication for IDEs and AI assistants.

---

## Hardware & OS Requirements

| Resource | Requirement | Notes |
| :--- | :--- | :--- |
| **Operating system** | Linux, macOS, or Windows | Native engine and parser wheels must support your OS and architecture. |
| **Python** | Python 3.10 or higher | Backend availability varies. FalkorDB Lite requires Unix and Python 3.12+; CGC excludes Kuzu on macOS/Windows with Python 3.14+. |
| **Memory and disk** | Depend on repository size, queries and backend | The embedded buffer-pool setting does not cap total process RSS. See [operating notes](../reference/mcp-operating-notes.md#memory-response-limits-and-ownership). |

---

## Database Backend Selection

CGC supports multiple database engines. You only need to set up the engine that fits your requirements.

Choose an embedded engine for local use or configure a server connection. [Database Backends](../concepts/backends.md) describes all six supported identifiers, platform constraints and the actual fallback order. Install CGC with its declared dependency constraints rather than upgrading native drivers independently.

---

## Development Environment Interfaces

To use CodeGraphContext inside your coding workflow, ensure you have an MCP-compliant workspace interface, such as:

- **Cursor IDE** (Native MCP Support)
- **VS Code** (with the Continue or similar MCP extension)
- **Claude Desktop** (Native local process or SSE support)
- **Windsurf IDE / OpenCode**
