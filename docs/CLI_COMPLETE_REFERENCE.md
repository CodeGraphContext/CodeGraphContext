# Complete CLI Command Reference

**All CodeGraphContext CLI Commands - Comprehensive List**

---

## 📋 **Table of Contents**

1. [Project Management](#1-project-management)
2. [Watching & Monitoring](#2-watching--monitoring)
3. [Code Analysis](#3-code-analysis)
4. [Discovery & Search](#4-discovery--search)
5. [Configuration & Setup](#5-configuration--setup)
6. [Bundle Management](#6-bundle-management)
7. [Bundle Registry](#7-bundle-registry)
8. [Utilities & Runtime](#8-utilities--runtime)
9. [Global Options](#global-options)
10. [Shortcuts](#shortcuts)

---

## 1. Project Management

| Command | Arguments | Description |
|---------|-----------|-------------|
| `cgc index` | `[path]` `--force` | Index a repository. Default: current directory. Use `--force` to re-index. *(Alias: `cgc i`)* |
| `cgc list` | None | List all indexed repositories. *(Alias: `cgc ls`)* |
| `cgc delete` | `[path]` `--all` | Delete a repository from the graph. Use `--all` to wipe everything. *(Alias: `cgc rm`)* |
| `cgc stats` | `[path]` | Show indexing statistics for DB or specific repo. |
| `cgc clean` | None | Remove orphaned nodes and clean up the database. |
| `cgc add-package` | `<name> <lang>` | Manually add an external package node. |

---

## 2. Watching & Monitoring

| Command | Arguments | Description |
|---------|-----------|-------------|
| `cgc watch` | `[path]` | Watch directory for changes and auto-reindex. *(Alias: `cgc w`)* |
| `cgc unwatch` | `<path>` | Stop watching a directory. |
| `cgc watching` | None | List all watched directories. |

---

## 3. Code Analysis

| Command | Arguments | Description |
|---------|-----------|-------------|
| `cgc analyze calls` | `<func>` `--file` | Show outgoing calls: what does this function call? |
| `cgc analyze callers` | `<func>` `--file` | Show incoming calls: who calls this function? |
| `cgc analyze chain` | `<start> <end>` `--depth` | Find call path between two functions. Default depth: 5. |
| `cgc analyze deps` | `<module>` `--no-external` | Inspect dependencies (imports/importers) for a module. |
| `cgc analyze tree` | `<class>` `--file` | Visualize class inheritance hierarchy. |
| `cgc analyze complexity` | `[path]` `--threshold` `--limit` | List functions with high cyclomatic complexity. Default threshold: 10. |
| `cgc analyze dead-code` | `--exclude` | Find potentially unused functions (0 callers). |
| `cgc analyze overrides` | `<class>` `--file` | Show methods that override parent class methods. |
| `cgc analyze variable` | `<var_name>` `--file` | Analyze variable usage and assignments. |

---

## 4. Discovery & Search

| Command | Arguments | Description |
|---------|-----------|-------------|
| `cgc find name` | `<name>` `--type` | Find code elements by exact name. |
| `cgc find pattern` | `<pattern>` `--case-sensitive` | Find elements using fuzzy substring matching. |
| `cgc find type` | `<type>` `--limit` | List all nodes of a specific type (function, class, module). |
| `cgc find variable` | `<name>` `--file` | Find variables by name across the codebase. |
| `cgc find content` | `<text>` `--case-sensitive` | Search for text content within code (docstrings, comments). |
| `cgc find decorator` | `<name>` | Find all functions/classes with a specific decorator. |
| `cgc find argument` | `<name>` | Find all functions that have a specific argument name. |

---

## 5. Configuration & Setup

| Command | Arguments | Description |
|---------|-----------|-------------|
| `cgc mcp setup` | None | Configure IDE/MCP Client. Creates `mcp.json`. *(Alias: `cgc m`)* |
| `cgc mcp start` | None | Start the MCP Server (used by IDEs). |
| `cgc mcp tools` | None | List all available MCP tools. |
| `cgc neo4j setup` | None | Configure Neo4j database connection. *(Alias: `cgc n`)* |
| `cgc config show` | None | Display current configuration values. |
| `cgc config set` | `<key> <value>` | Set a configuration value. |
| `cgc config reset` | None | Reset configuration to defaults. |
| `cgc config db` | `<backend>` | Quick switch between `neo4j` and `falkordb`. |

---

## 6. Bundle Management

| Command | Arguments | Description |
|---------|-----------|-------------|
| `cgc bundle export` | `<output.cgc>` `--repo` `--no-stats` | Export graph to portable .cgc bundle. *(Alias: `cgc export`)* |
| `cgc bundle import` | `<bundle.cgc>` `--clear` | Import a .cgc bundle into database. |
| `cgc bundle load` | `<name>` `--clear` | Load bundle (downloads from registry if needed). *(Alias: `cgc load`)* |

---

## 7. Bundle Registry

| Command | Arguments | Description |
|---------|-----------|-------------|
| `cgc registry list` | `--verbose` `-v` `--unique` `-u` | List all available bundles in the registry. Use `--unique` to show only most recent version per package. |
| `cgc registry search` | `<query>` | Search for bundles by name/repo/description. |
| `cgc registry download` | `<name>` `--output` `-o` `--load` `-l` | Download bundle from registry. |
| `cgc registry request` | `<github-url>` `--wait` | Request on-demand bundle generation. |

---

## 8. Utilities & Runtime

| Command | Arguments | Description |
|---------|-----------|-------------|
| `cgc doctor` | None | Run system diagnostics (DB, dependencies, permissions). |
| `cgc visualize` | `[query]` | Generate link to Neo4j Browser. *(Alias: `cgc v`)* |
| `cgc query` | `<query>` | Execute raw Cypher query against DB. |
| `cgc help` | None | Show main help message with all commands. |
| `cgc version` | None | Show application version. |
| `cgc start` | None | **Deprecated**. Use `cgc mcp start` instead. |

---

## Global Options

These work with any command:

| Option | Short | Description |
|--------|-------|-------------|
| `--database` | `-db` | Override database backend (`falkordb` or `neo4j`). |
| `--visual` / `--viz` | `-V` | Show results as interactive graph visualization. |
| `--help` | `-h` | Show help for any command. |
| `--version` | `-v` | Show version (root level only). |

---

## Shortcuts

Quick aliases for common commands:

| Shortcut | Full Command | Description |
|----------|--------------|-------------|
| `cgc m` | `cgc mcp setup` | MCP client setup |
| `cgc n` | `cgc neo4j setup` | Neo4j database setup |
| `cgc i` | `cgc index` | Index repository |
| `cgc ls` | `cgc list` | List repositories |
| `cgc rm` | `cgc delete` | Delete repository |
| `cgc v` | `cgc visualize` | Visualize graph |
| `cgc w` | `cgc watch` | Watch directory |
| `cgc export` | `cgc bundle export` | Export bundle |
| `cgc load` | `cgc bundle load` | Load bundle |

---

## Quick Examples

### Basic Workflow
```bash
cgc index .                          # Index current directory
cgc list                             # List indexed repos
cgc find name MyFunction             # Find a function
cgc analyze callers MyFunction       # See who calls it
```

### Bundle Workflow
```bash
cgc bundle export my-project.cgc --repo .  # Export graph
cgc registry list                          # Browse bundles
cgc load flask                             # Download & load
cgc registry search web                    # Search bundles
```

### Advanced Analysis
```bash
cgc analyze complexity --threshold 15      # Find complex code
cgc analyze chain start end --depth 10     # Find call path
cgc analyze tree MyClass --visual          # Visualize in browser
```

### Configuration
```bash
cgc config show                      # View config
cgc config set DEFAULT_DATABASE neo4j  # Switch to Neo4j
cgc config db falkordb               # Quick switch to FalkorDB
cgc doctor                           # Check system health
```

---

## Command Count Summary

**Total Commands: 55**

- Project Management: 6 commands
- Watching & Monitoring: 3 commands
- Code Analysis: 9 commands (added 2 new)
- Discovery & Search: 7 commands (added 4 new)
- Configuration & Setup: 8 commands
- Bundle Management: 3 commands
- Bundle Registry: 4 commands
- Utilities & Runtime: 6 commands
- Global Options: 4 options
- Shortcuts: 9 aliases

---

**All commands documented!** ✅

**Newly Added Commands:**
- `cgc analyze overrides` - Show method overrides
- `cgc analyze variable` - Analyze variable usage
- `cgc find variable` - Find variables by name
- `cgc find content` - Search text in code
- `cgc find decorator` - Find by decorator
- `cgc find argument` - Find by argument name
- Hidden: `cgc cypher` (deprecated, use `cgc query`)
