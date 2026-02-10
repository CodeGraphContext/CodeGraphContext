# Configuration & Settings

CodeGraphContext is highly configurable through environment files and the CLI.

## `cgc config` Command

View and modify settings directly from the terminal.

### 1. View Settings
Shows the current effective configuration (merged from defaults and `.env`).

```bash
cgc config show
```

### 2. Set a Value
Update a setting permanently. This writes to `~/.codegraphcontext/.env`.

**Syntax:** `cgc config set <KEY> <VALUE>`

```bash
# Switch to Neo4j backend
cgc config set DEFAULT_BACKEND neo4j

# Increase max file size to index (MB)
cgc config set MAX_FILE_SIZE_MB 20

# Enable automatic watching after index
cgc config set ENABLE_AUTO_WATCH true
```

### 3. Quick Switch Database
A shortcut to toggle between `falkordb` and `neo4j`.

```bash
cgc config db neo4j
```

---

## Configuration Reference

Here are the available settings you can configure.

### Core Settings

| Key | Default | Description |
| :--- | :--- | :--- |
| **`DEFAULT_BACKEND`** | `falkordb` | The database engine to use (`neo4j` or `falkordb`). |
| **`ENABLE_AUTO_WATCH`** | `false` | If `true`, `cgc index` will automatically start watching for changes. |
| **`PARALLEL_WORKERS`** | `4` | Number of parallel threads to use during indexing. |
| **`CACHE_ENABLED`** | `true` | Caches file hashes to speed up re-indexing. |

### Indexing Scope

| Key | Default | Description |
| :--- | :--- | :--- |
| **`MAX_FILE_SIZE_MB`** | `5` | Files larger than this (in MB) are skipped. |
| **`IGNORE_TESTS`** | `false` | If `true`, skips folders named `tests` or `spec`. |
| **`IGNORE_HIDDEN`** | `true` | Skips hidden files (`.git`, `.vscode`). |
| **`INDEX_VARIABLES`** | `true` | Creates nodes for variables. Set to `false` for a smaller graph. |

### Database Connection (Neo4j)

| Key | Description |
| :--- | :--- |
| **`NEO4J_URI`** | Connection URI (e.g., `bolt://localhost:7687`). |
| **`NEO4J_USERNAME`** | Database user (default: `neo4j`). |
| **`NEO4J_PASSWORD`** | Database password. |

---

## Configuration Files

CodeGraphContext uses the following hierarchy:

1.  **Project Level:** `.cgcignore` in your project root (files to exclude).
2.  **User Level:** `~/.codegraphcontext/.env` (global settings).
3.  **Defaults:** Built-in application defaults.

To reset everything to defaults:
```bash
cgc config reset
```
