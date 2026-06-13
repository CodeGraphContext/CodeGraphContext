# CLI Command Reference

The `cgc` command-line interface is the entry point for indexing code, running graph queries, managing contexts, and administering database backends.

Run `cgc --help` or `cgc help` for the live command tree on your installed version.

---

## Global Options

These flags apply to most subcommands:

| Option | Shorthand | Description |
| :--- | :--- | :--- |
| `--database` | `--db`, `-db` | Override the active backend for this invocation (`neo4j`, `falkordb`, `falkordb-remote`, `kuzudb`, `nornic`, `ladybugdb`). |
| `--db-path` | | Override the on-disk storage directory for embedded engines. |
| `--context` | `-c` | Target a named context workspace. |
| `--visual` | `--viz`, `-V` | Open results in the interactive graph visualization UI. |
| `--version` | `-v` | Print package version and exit. |
| `--help` | `-h` | Show help and exit. |

Use `cgc version` (or `cgc --version`) to print the installed release (currently **0.5.0**).

---

## Core Index & Lifecycle

| Command | Usage | Notes |
| :--- | :--- | :--- |
| **`index`** | `cgc index [PATH] [--force] [--dependency]` | Shortcut: `cgc i`. Incremental by default; `--force` rebuilds from scratch. |
| **`clean`** | `cgc clean` | Purges orphaned nodes and dangling relationships. |
| **`stats`** | `cgc stats` | Repository and node counts for the active context. |
| **`delete`** | `cgc delete <repo_path>` | Shortcut: `cgc rm`. Removes one indexed repository. |
| **`list`** | `cgc list` | Shortcut: `cgc ls`. Lists indexed repositories. |
| **`add-package`** | `cgc add-package <name> <language>` | Indexes an installed third-party package as a dependency graph. |

---

## Search (`find`)

```bash
cgc find <subcommand> [args] [options]
```

| Subcommand | Description |
| :--- | :--- |
| `find name <symbol>` | Search by symbol name. Options: `--type function\|class\|file\|module`, `--fuzzy` / `--no-fuzzy`. |
| `find pattern <regex>` | Regex search across indexed source. |
| `find type <node_type>` | List nodes of a given label (e.g. `Function`, `Class`). |
| `find content <text>` | Full-text / substring search in source and docstrings. Neo4j uses Lucene; embedded backends use portable substring matching. |
| `find decorator <name>` | Functions with a given decorator. |
| `find argument <name>` | Functions declaring a parameter name. |
| `find variable <name>` | Variable references and assignments. |

---

## Analysis (`analyze`)

```bash
cgc analyze <subcommand> [args] [options]
```

| Subcommand | Description |
| :--- | :--- |
| `analyze callers <function>` | Direct callers of a function. |
| `analyze calls <function>` | Direct callees of a function. |
| `analyze chain <source> <target>` | Shortest call path between two symbols. |
| `analyze deps <module>` | Module import dependencies. |
| `analyze tree <class>` | Class inheritance tree. |
| `analyze complexity <function>` | Cyclomatic complexity for one function. |
| `analyze dead-code` | Unreferenced functions/files (with optional filters). |
| `analyze overrides <class>` | Methods overridden in subclasses. |
| `analyze variable <name>` | Variable scope and modification sites. |
| `analyze kotlin-call-audit` | Kotlin-specific call resolution audit. |

---

## Querying & Reports

#### `query`
Execute a read-only Cypher query.

```bash
cgc query "MATCH (f:Function) RETURN f.name LIMIT 10"
cgc query "MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50" --visual
```

`cgc cypher` still works as a hidden alias but prints a deprecation warning—prefer `cgc query`.

#### `report`
Generate `CGC_REPORT.md` with god-node, complexity, and coupling metrics.

```bash
cgc report [--include-java]
```

#### `visualize`
Launch the React force-directed graph UI (shortcut: `cgc v`).

```bash
cgc visualize [--repo <path>] [--port 8000]
```

---

## Context Workspaces (`context`)

Manage isolation modes and named workspaces. See [Configuration Contexts](../guides/contexts.md).

```bash
cgc context list
cgc context mode <global|per-repo|named>
cgc context create <name> [--database kuzudb] [--db-path /path]
cgc context delete <name>
cgc context default <name>
```

---

## Configuration (`config`)

```bash
cgc config show
cgc config set <KEY> <VALUE>
cgc config db <backend>
cgc config reset
```

Valid backends: `kuzudb`, `ladybugdb`, `falkordb`, `falkordb-remote`, `neo4j`, `nornic`. See [Configuration Reference](config.md).

---

## MCP & Neo4j Setup

```bash
cgc mcp setup          # Interactive IDE wizard (shortcut: cgc m)
cgc mcp start          # Start stdio MCP server
cgc mcp tools          # List registered MCP tools

cgc neo4j setup        # Neo4j connection wizard (shortcut: cgc n)
```

---

## Portable Bundles (`bundle`)

```bash
cgc bundle export <output.cgc> [--repo PATH] [--no-stats] [--context NAME]
cgc bundle import <file.cgc> [--clear] [--yes|-y] [--context NAME]
cgc bundle load <name> [--clear] [--yes|-y]

# Shortcuts
cgc export my-project.cgc --repo /path/to/project
cgc load numpy
```

Use `--yes` / `-y` with `--clear` to skip the destructive-import confirmation (required in CI/non-interactive shells).

#### `registry`
Browse and download pre-indexed bundles.

```bash
cgc registry list [--verbose] [--unique]
cgc registry search <query>
cgc registry download <name> [--output DIR] [--load]
cgc registry request <github_url>
```

---

## Real-Time Watchers

```bash
cgc watch [PATH]          # Shortcut: cgc w
cgc unwatch <PATH>
cgc watching
```

On startup, watchers reconcile the graph with the filesystem (add missing files, remove deleted paths) before monitoring changes.

---

## Git Hooks (`hook`)

Keep the graph in sync on commit:

```bash
cgc hook install [PATH] [--force]
cgc hook uninstall [PATH]
cgc hook status [PATH]
```

---

## HTTP API Gateway (`api`)

```bash
cgc api start [--host 0.0.0.0] [--port 8000] [--reload]
```

Exposes REST endpoints under `/api/v1` and a liveness probe at `GET /health`. See [HTTP API Reference](api.md).

---

## External Datasources (`datasource`)

```bash
cgc datasource mysql
cgc datasource cassandra
cgc datasource redis
```

---

## SCIP Setup

```bash
cgc setup-scip
```

Installs or verifies external SCIP indexers when `SCIP_INDEXER=true`. C/C++ require `compile_commands.json`; see the README SCIP section.

---

## System Diagnostics

```bash
cgc doctor
```

Checks configuration, database connectivity, Tree-sitter parsers, dependencies, and file permissions.

---

## Command Shortcuts

| Shortcut | Full command |
| :--- | :--- |
| `cgc i` | `cgc index` |
| `cgc ls` | `cgc list` |
| `cgc rm` | `cgc delete` |
| `cgc v` | `cgc visualize` |
| `cgc w` | `cgc watch` |
| `cgc m` | `cgc mcp` |
| `cgc n` | `cgc neo4j` |
| `cgc export` | `cgc bundle export` |
| `cgc load` | `cgc bundle load` |
