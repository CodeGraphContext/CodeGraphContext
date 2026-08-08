# System Prerequisites

CodeGraphContext (CGC) is designed as a client-server architecture. To ensure a successful installation, understand the primary roles and requirements of the environment.

---

## Architecture Components

1. **The Ingestion Engine**: The core Python package responsible for scanning source directories, running Tree-sitter and SCIP syntax parsers, and linking references.
2. **The Graph Storage Layer**: The database backend containing nodes and edges representing code entities and their interactions.
3. **The Interface Clients**:
    - **CLI (`cgc`)**: Terminal interface used for managing indices, running analytical searches, and system diagnostics.
    - **MCP Server**: Gateway enabling Model Context Protocol communication for IDEs and AI assistants.

---

## Hardware & OS Requirements

| Resource | Minimum Requirement | Notes |
| :--- | :--- | :--- |
| **Operating System** | Linux, macOS, or Windows | Windows WSL is supported but native installation works via KuzuDB. |
| **Python Version** | Python 3.10 or higher | Python 3.10+ is required for the core package and KuzuDB. |
| **Memory** | 4 GB RAM | Large repositories benefit from 8 GB+ memory during initial scans. |

---

## Database Backend Selection

CGC supports multiple database engines. You only need to set up the engine that fits your requirements.

| Database Backend | Setup Type | Target Platform | Use Case |
| :--- | :--- | :--- | :--- |
| **FalkorDB Lite (Default)** | In-process (Embedded) | Unix (Linux/macOS), Python 3.12+ | Default when `falkordblite` is installed. In-memory, extremely low latency. |
| **KuzuDB** | In-process (Embedded) | Cross-Platform (Linux/macOS/Windows) | Automatic fallback on Windows or when FalkorDB Lite is unavailable. Python 3.10+. |
| **LadybugDB** | In-process (Embedded) | Cross-Platform | Alternative embedded engine; `pip install ladybug`. |
| **FalkorDB Remote** | Networked Server | Cross-Platform Client | Connects to a remote FalkorDB/Redis-compatible server. |
| **Neo4j** | Networked Server | Cross-Platform Client | Enterprise clustering, Neo4j Browser, AuraDB. |
| **Nornic DB** | Embedded / Bolt client | Cross-Platform | Neo4j-compatible driver without a full Neo4j deployment. |

---

## Development Environment Interfaces

To use CodeGraphContext inside your coding workflow, ensure you have an MCP-compliant workspace interface, such as:

- **Cursor IDE** (Native MCP Support)
- **VS Code** (with the Continue or similar MCP extension)
- **Claude Desktop** (Native local process or SSE support)
- **Windsurf IDE / OpenCode**
