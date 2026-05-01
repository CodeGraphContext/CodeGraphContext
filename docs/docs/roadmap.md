# Project Roadmap

CodeGraphContext is continuously evolving. This roadmap outlines our current capabilities and our vision for the future of code intelligence.

## Current Capabilities

These features are available in the current release:

*   **Multi-Language Support**: Robust parsing for 19+ languages including Python, JS/TS, Go, Rust, C++, and Java.
*   **Plug-and-Play Backends**: Support for KùzuDB, FalkorDB, and Neo4j.
*   **MCP Ecosystem**: A rich set of tools for AI assistants, supporting stdio transport.
*   **Real-time Sync**: File system watchers that keep the code graph up-to-date automatically.
*   **Portable Bundles**: A registry and CLI tools for sharing and loading pre-indexed code graphs.
*   **Graph Visualization**: An interactive React-based UI for exploring code relationships.

## In Development (Short Term)

*   **Language-Specific Query Toolkits**: Specialized queries for deeper analysis of specific language patterns (e.g., React component trees, Python decorator chains).
*   **Enhanced SCIP Integration**: Moving SCIP support from beta to a first-class indexing citizen for even higher precision.
*   **Performance Optimizations**: Faster initial indexing for massive (1M+ LOC) repositories.

## Planned (Long Term)

*   **Advanced AI Workflows**: Deeper integration with agentic frameworks to allow AI to perform complex refactorings using the graph.
*   **CI/CD Integration**: Official GitHub Actions and GitLab CI components for automated graph building.
*   **Cloud Synchronization**: Optional encrypted cloud storage for syncing code graphs across your development machines.
*   **Alternative MCP Transports**: Support for HTTP/SSE and WebSocket transports for remote MCP hosting.

---

> [!NOTE]
> **Have a feature request?**
> We value community feedback. Please open an issue on our [GitHub repository](https://github.com/CodeGraphContext/CodeGraphContext/issues) to suggest new features or report bugs.
