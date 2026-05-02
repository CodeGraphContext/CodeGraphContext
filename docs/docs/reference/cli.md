# CLI Reference

The `cgc` command-line interface provides a suite of tools for indexing, querying, and managing your code graph.

## Core Commands

### `index`
Index a repository or directory.

*   **Usage**: `cgc index [PATH]`
*   **Options**:
    *   `--dependency`: Mark the indexed code as a dependency.
    *   `--deep`: Perform a deeper analysis of relationships.
    *   `--force`: Re-index all files even if they haven't changed.

### `watch`
Monitor a directory for changes and update the graph in real-time.

*   **Usage**: `cgc watch [PATH]`

### `stats`
Display statistics about the current indexed repository.

*   **Usage**: `cgc stats [--all]`

---

## Querying the Graph

### `query`
Execute relationship-based queries.

*   **Usage**: `cgc query [TYPE] [TARGET]`
*   **Types**:
    *   `callers`: Find functions that call the target.
    *   `callees`: Find functions called by the target.
    *   `hierarchy`: Show class inheritance for the target.
    *   `dead-code`: Identify potentially unused functions.

### `find`
Search for code symbols (functions, classes, etc.) by name or content.

*   **Usage**: `cgc find [QUERY]`
*   **Options**:
    *   `--fuzzy`: Use fuzzy matching for the search query.

### `visualize`
Generate a visual graph of the codebase or a specific query.

*   **Usage**: `cgc visualize [--query Q]`

---

## Bundle Management

### `bundle create`
Export the current index to a `.cgc` bundle file.

*   **Usage**: `cgc bundle create --name NAME`

### `bundle load`
Load a local bundle or download one from the registry.

*   **Usage**: `cgc bundle load [PATH|NAME]`

### `bundle search`
Search the CGC bundle registry.

*   **Usage**: `cgc bundle search [QUERY]`

---

## System & Configuration

### `config`
Manage global configuration settings.

*   **Subcommands**:
    *   `set-db [kuzudb|falkordb|neo4j]`: Set the default database backend.
    *   `list`: Show all current configuration values.

### `doctor`
Run diagnostics to verify installation and backend connectivity.

*   **Usage**: `cgc doctor`

### `mcp`
Start the Model Context Protocol (MCP) server. This command is typically invoked by AI assistants, not directly by users.

*   **Usage**: `cgc mcp`

---

## Global Options

*   `--database`: Override the default database for a single command.
*   `--verbose`: Enable detailed logging for debugging.
*   `--version`: Display the version of CodeGraphContext.
