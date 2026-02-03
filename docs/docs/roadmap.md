# 🗺️ Project Roadmap

CodeGraphContext is an evolving tool. We believe in transparency about where we are and where we are going.

## 🟢 Currently Supported (Stable)

These features are live and battle-tested in version `0.2.0+`.

*   **Core Indexing:** Python, JavaScript, TypeScript, Go, Java, C++, Ruby, PHP.
*   **Database Backends:**
    *   FalkorDB Lite (In-memory, default for Unix).
    *   Neo4j (Docker/Native, default for Production).
*   **MCP Server:** Full support for Cursor, Claude Desktop, Windsurf, VS Code.
*   **Live Watching:** Real-time updates via `cgc watch`.
*   **Bundles:** Export/Import indexed graphs.

## 🚧 In Progress (Beta / Active Dev)

We are actively writing code for these right now.

*   **Interactive Visualizer:** A new web-based UI to explore the graph without Neo4j Browser.
*   **Better C++ Support:** improved parsing for header/implementation linkage.
*   **Configuration UI:** A TUI (Text User Interface) for managing `mcp.json` configs.

## 🔮 Planned (Future)

Concepts we are researching for the next major versions.

*   **Cloud Sync:** Option to share private implementation graphs with team members.
*   **CI/CD Action:** GitHub Action to auto-index PRs and comment with impact analysis.
*   **Natural Language Query to Graph:** Improved "Text-to-Cypher" translation for the CLI.

---

!!! info "Request a Feature"
    Have an idea? Open an issue on our [GitHub Repository](https://github.com/CodeGraphContext/CodeGraphContext/issues).
