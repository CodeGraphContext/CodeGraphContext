# Developer Onboarding & Code Tour

Welcome to the CodeGraphContext (CGC) developer portal. This guide details the structural layout of the repository to help new contributors navigate the codebase, understand the interactions between components, and locate files when debugging or extending features.

---

## Repository Directory Layout

The root workspace contains the following directories:

```text
CodeGraphContext/
├── src/                    <-- Core Python application source code
│   └── codegraphcontext/   <-- Primary package namespace
├── website/                <-- React-based force-directed graph visualizer UI
├── docs/                   <-- MkDocs documentation source files and themes
├── tests/                  <-- Unit, integration, and parser test suites
├── scripts/                <-- Maintainer scripts, build helpers, and language updates
├── k8s/                    <-- Kubernetes deployment descriptors and manifests
└── organizer/              <-- Research drafts, roadmaps, and feature experiments
```

---

## Codebase Component Tour

### 1. The Core Engine (`src/codegraphcontext/`)

This directory houses the engine execution layers:

- **`cli/`**: Contains the Typer-based command-line definition files. Subcommands like `cgc index`, `cgc watch`, and `cgc analyze` map their arguments here.
- **`core/`**: Houses the database abstraction layers. Database files like `database_kuzu.py`, `database_ladybug.py`, `database_falkor.py`, and `database_neo4j.py` inherit from a unified database driver interface class.
- **`tools/languages/`**: Standardizes language parsing classes. Contains Tree-sitter tag query files (e.g., `queries/python/tags.scm`) and logic to parse classes, functions, and inheritances.
- **`tools/handlers/`**: Implements individual handler logics for each Model Context Protocol (MCP) tool. The main server file (`server.py`) delegates incoming JSON-RPC calls to these specialized handler modules.
- **`core/watcher.py`**: Integrates the `watchdog` monitoring library to schedule incremental index re-scans.
- **`graph_builder.py`**: Coordinates multi-threaded ingestion, links call references, and batches insertions to the active database backend.

### 2. The Interactive Visualizer UI (`website/`)

A self-contained React project that runs the graphical visualization console.

- **`src/components/CodeGraphViewer.tsx`**: Uses `react-force-graph` to render nodes and relationships in a 2D/3D interface.
- **`api/`**: Connection layers to retrieve graph data from the FastAPI backend served by the `cgc api start` process.

### 3. Verification Test Suite (`tests/`)

The test suite ensures reliability across backends and language parsers:

- **`unit/`**: Validates isolated logic blocks, such as specific regex matches, configuration expansions, or parser AST collections.
- **`integration/`**: Verifies graph operations against actual database instances (KuzuDB, Neo4j, FalkorDB).
- **`fixtures/`**: Minimal test codebases (e.g., mock Python classes or Javascript files) used by integration tests to check parser outputs.

### 4. Enterprise Deployments (`k8s/`)

Contains Kubernetes descriptors:
- **`deployment.yaml` & `service.yaml`**: Manifests to deploy the FastAPI gateway and MCP server in cluster environments.
- **`neo4j-deployment.yaml`**: Persistent volume claims and stateful sets for Neo4j database containers.

---

## Entry Points for Extension

### Adding Support for a New Language
1. Create a language module under `src/codegraphcontext/tools/languages/` inheriting from the base parser.
2. Define AST query patterns in `queries/<language>/tags.scm`.
3. Add the parser registration in `parser_factory.py`.
4. Run language tests via `scripts/test_all_parsers.py`.

### Implementing a New MCP Tool
1. Register the tool schema definition in `src/codegraphcontext/tool_definitions.py`.
2. Add a matching tool handler module in `src/codegraphcontext/tools/handlers/`.
3. Map the tool handler execution path inside `src/codegraphcontext/server.py`.

### Debugging Database Drivers
- Database implementations are isolated in `src/codegraphcontext/core/`. Modify queries or connection parameters inside the respective driver wrapper file.
