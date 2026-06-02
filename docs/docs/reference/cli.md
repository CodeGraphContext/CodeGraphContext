# CLI Command Reference

The `cgc` command-line interface provides the entry point for indexing code, starting processes, executing queries, and administering graph databases.

---

## Global Options

These flags can be appended to any `cgc` command to override runtime behavior:

| Option | Shorthand | Description |
| :--- | :--- | :--- |
| `--database` | `-db` | Temporarily overrides the default database backend for the execution (`falkordb`, `ladybugdb`, `neo4j`, or `kuzudb`). |
| `--path` | `--db-path` | Temporarily overrides the storage directory path for local embedded engines (KuzuDB/LadybugDB). |
| `--visual` | `-V` | Renders results using the interactive React graph visualization browser window. |
| `--version` | `-v` | Display CLI package version and exit. (Root option only) |
| `--help` | `-h` | Display CLI help prompt and exit. (Root option only) |

---

## Command Suite

### Core Index & Lifecycle Commands

#### `index`
Scans and parses files to add or update symbols in the graph.
- **Usage**: `cgc index [PATH] [OPTIONS]` (Or shortcut `cgc i`)
- **Options**:
  - `--dependency`: Registers the code in the target path as an external dependency library.
  - `--force`: Discards hash cache and forces a full re-parse of all files.

#### `clean`
Purges orphaned nodes, links, and unreferenced schemas from the database.
- **Usage**: `cgc clean`

#### `stats`
Displays statistics detailing active repository contents in the graph.
- **Usage**: `cgc stats`

#### `delete`
Removes an indexed repository and all its code nodes from the graph.
- **Usage**: `cgc delete <repo_path>` (Or shortcut `cgc rm`)

#### `list`
Lists all repositories currently indexed in the active database.
- **Usage**: `cgc list` (Or shortcut `cgc ls`)

#### `add-package`
Downloads (if needed) and indexes a third-party package.
- **Usage**: `cgc add-package <name> <language>`
- **Parameters**:
  - `name`: Package identifier (e.g., `requests`, `lodash`).
  - `language`: Programming language syntax parser (e.g., `python`, `typescript`).

---

### Analysis & Search Commands

#### `find`
Locates code symbols or contents matching a query pattern.
- **Usage**: `cgc find <subcommand> [args]`
- **Subcommands**:
  - `find content <text>`: Searches source file contents for matching text strings.
  - `find decorator <name>`: Finds functions decorated with the target decorator (e.g., `@app.route`).
  - `find argument <name>`: Finds functions declaring the specified parameter name.
  - `find variable <name>`: Finds variable references.

#### `analyze`
Executes semantic graph queries to map relationships.
- **Usage**: `cgc analyze <subcommand> [args]`
- **Subcommands**:
  - `analyze callers <function>`: Lists direct caller functions.
  - `analyze calls <function>`: Lists direct functions called by the target.
  - `analyze chain <source> <target>`: Traces the call path between two functions.
  - `analyze overrides <class>`: Lists classes overriding target class methods.
  - `analyze variable <name>`: Traces variable scopes and writes.

#### `query`
Executes a raw read-only Cypher query against the active database.
- **Usage**: `cgc query "<CYPHER_STATEMENT>"`

#### `report`
Generates a `CGC_REPORT.md` file auditing codebase quality, god nodes, complex methods, and cross-module couplings.
- **Usage**: `cgc report [OPTIONS]`
- **Options**:
  - `--include-java`: Appends Spring endpoints and bean metrics to the report.

#### `visualize`
Launches the FastAPI web server to serve the React force-directed graph UI.
- **Usage**: `cgc visualize [OPTIONS]` (Or shortcut `cgc v`)
- **Options**:
  - `--repo <path>`: Filters the visualization to the specified repository.
  - `--port <integer>`: Port to bind the server on (Default: 8000).

---

### Context Workspaces Group

#### `context`
Manage logical database contexts and isolation levels.
- **Usage**: `cgc context <subcommand> [args]`
- **Subcommands**:
  - `context list`: Lists all contexts and modes.
  - `context mode <global|per-repo|named>`: Switches active context isolation mode.
  - `context create <name>`: Creates a named context.
    - **Options**:
      - `--database`, `--db`, `-db`, `-d`: Specify the database backend engine (`falkordb`, `ladybugdb`, `neo4j`, or `kuzudb`).
      - `--db-path`: Custom database file storage location path.
  - `context delete <name>`: Deletes a named context from registry.
  - `context default <name>`: Sets the default named context workspace.

---

### External Datasources Group

#### `datasource`
Ingests database and cache schemas.
- **Usage**: `cgc datasource <subcommand> [args]`
- **Subcommands**:
  - `datasource mysql`: Imports tables and columns from MySQL database.
  - `datasource cassandra`: Imports tables and schemas from Cassandra cluster.
  - `datasource redis`: Scans and registers Redis cache key schemas.

---

### Portable Bundles Group

#### `bundle`
Serializes and shares graphs as `.cgc` archive bundles.
- **Usage**: `cgc bundle <subcommand> [args]`
- **Subcommands**:
  - `bundle export <output.cgc>`: Exports active graph to a portable bundle file. (Shortcut: `cgc export`)
  - `bundle import <input.cgc>`: Imports a bundle file into the database.
  - `bundle load <name>`: Downloads (if remote) and imports a registry bundle. (Shortcut: `cgc load`)

#### `registry`
Interacts with the remote CGC bundle server.
- **Usage**: `cgc registry <subcommand> [args]`
- **Subcommands**:
  - `registry list`: Lists all packages in the registry.
  - `registry search <query>`: Searches for packages.
  - `registry download <name>`: Downloads a package bundle.
  - `registry request <github_url>`: Submits a package generation request.

---

### Real-Time Monitoring Group

#### `watch`
Starts a filesystem watcher to incrementally update the graph.
- **Usage**: `cgc watch [PATH]` (Or shortcut `cgc w`)

#### `unwatch`
Terminates monitoring on a specified directory path.
- **Usage**: `cgc unwatch <PATH>`

#### `watching`
Lists all directories currently monitored by watchers.
- **Usage**: `cgc watching`

---

### System Diagnostics

#### `doctor`
Executes health checks on the CLI execution path, configuration files, write permissions, and database drivers.
- **Usage**: `cgc doctor`
