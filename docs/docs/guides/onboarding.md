# Onboarding Guide

Welcome to the CodeGraphContext source code! This guide is designed to help new contributors and maintainers understand exactly what each folder and file in the repository does. This detailed breakdown ensures you know where to look when debugging or adding new features to the core engine, CLI, or UI.

## Root Directory Structure

The root directory contains important configuration files for packaging, testing, and Docker:

- `.cgcignore` - The internal tool exclusion file (acts like `.gitignore`) which skips un-indexable items.
- `.env.example` - Template for environment variables (like Neo4j credentials, debug modes).
- `CONTRIBUTING.md` - Guidelines for how to contribute to the repository.
- `docker-compose.yml` - Sets up Neo4j for testing and debugging.
- `Dockerfile` - Builds the primary containerized application image.
- `pyproject.toml` - The primary Python packaging and configuration file, defining dependencies, tools, and the CLI entry point (`cgc`).
- `cgc_entry.py` - Root entry point script mapped within pyproject.toml to execute CLI commands.

---

## Detailed Directory Breakdown

### `src/codegraphcontext/`
This is the **Core Engine** containing all the Python logic to index, watch, and query code contexts.
- **`cli/`**: Directory housing the command-line interface logic using `click` or `typer` frameworks. All commands like `cgc index`, `cgc list`, and `cgc clean` live here.
- **`db/`**: The Database Abstraction Layer. Contains drivers and query execution logic for connecting to **KùzuDB** (our embedded default) and **Neo4j** (for enterprise-scale usages).
- **`parsers/`**: Collection of language-specific Tree-sitter implementations. Each script corresponds to a language (e.g., `python.py`, `javascript.py`) responsible for translating syntax ASTs into standard nodes/edges.
- **`utils/`**: Shared helpers across the project (logging, environment validation).
- **`graph_builder.py`**: The heavy-lifter file. Coordinates parsing across files, batches nodes and edges, and commits them to the DB.
- **`server.py`**: The main Model Context Protocol (MCP) server. Used by tools like Cursor or Claude Desktop to natively talk to this tool.
- **`watchdog/`**: Code that leverages `watchdog` to continuously monitor files for changes and instantly trigger an incremental index.

### `docs/`
Contains the knowledge base you are currently reading!
- **`mkdocs.yml`**: Structure configuration for the static site generator.
- **`docs/`**: Source markdown assets for all guides, reference manuals, and cookbooks.
- **`docs/images/`**: Assets for architectural flowcharts and interface snapshots.

### `tests/`
The testing suite. It ensures no PR breaks the engine.
- **`unit/`**: Isolated testing for small functions (such as specific parsers returning the right class name).
- **`integration/`**: Ensuring connections to local KùzuDB/Neo4j successfully write and read complex relationships.
- **`fixtures/`**: Mocked codebase folders (small fake python or typescript projects) used to validate parsers.

### `k8s/`
Kubernetes manifests for enterprise, scaled-out deployments.
- **`deployment.yaml` & `service.yaml`**: The descriptors that orchestrate running CGC within a Kubernetes cluster.
- **`neo4j-deployment.yaml`**: Standalone persistence layer setups.

### `website/`
A self-contained React project responsible for generating the visual, exploratory graph view.
- **`src/components/CodeGraphViewer.tsx`**: The main frontend react component utilizing `react-force-graph` to draw 3D/2D nodes dynamically.
- **`api/`**: Interaction endpoints allowing the UI to ping a running `cgc visualize` host.

### `scripts/`
A suite of bash and python automations for maintainers.
- **`create-bundle.sh`**: Scripts to pre-package indexes for known large repositories (like Django or React) so users can download them ready to go.
- **`update_language_parsers.py`**: A maintainer script to pull down new tree-sitter libraries.
- **`test_all_parsers.py`**: Validation scripts testing new Tree-sitter bindings.

### `organizer/`
A directory used for tracking the core team's research goals, roadmap notes, and experimental drafts before they are formalized into documentation or core repository features.

---

## Where to start modifying?

- **Want to add a new Language?** Look in `src/codegraphcontext/parsers/`. You'll need to define a new parser class and write Tree-sitter queries.
- **Want to add a new MCP Action?** Head to `src/codegraphcontext/server.py`. The `@app.tool` decorators expose new commands to Claude/Cursor.
- **Want to change Database connections?** Modify `src/codegraphcontext/db/`.
- **UI Tweaks on the Visualizer?** Change `website/src/components/CodeGraphViewer.tsx` and run `npm run dev` in that folder.

Enjoy contributing to CodeGraphContext! 
