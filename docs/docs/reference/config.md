# Configuration Reference

CodeGraphContext (CGC) is configured using environment variables, local configuration files, and the CLI.

---

## The `cgc config` CLI Utility

Use the `config` command group to inspect and modify settings from your terminal.

### 1. Inspect Effective Settings
Prints the merged configuration values (resolving defaults, global `.env`, and local workspaces):

```bash
cgc config show
```

### 2. Set Configuration Values
Persists key-value settings to the global environment configuration file:

```bash
# Set default database engine
cgc config set DEFAULT_DATABASE falkordb

# Change file size threshold (in MB)
cgc config set MAX_FILE_SIZE_MB 25
```

`DEFAULT_DATABASE` is the supported configuration key for selecting the database backend. `DEFAULT_BACKEND` is not a valid `cgc config` key.

### 3. Database Selection Shortcut
Quickly updates the `DEFAULT_DATABASE` key:

```bash
cgc config db falkordb
```

Valid database backend identifiers: `kuzudb`, `ladybugdb`, `falkordb` (Lite/embedded), `falkordb-remote`, and `neo4j`.

### 4. Reset to Defaults
Restores all keys to factory configurations:

```bash
cgc config reset
```

---

## Configuration Variable Reference

### Core Engine Settings

| Config Key | Default | Description |
| :--- | :--- | :--- |
| **`DEFAULT_DATABASE`** | `falkordb` | Active database engine. Options: `kuzudb`, `ladybugdb`, `falkordb`, `falkordb-remote`, `neo4j`. |
| **`ENABLE_AUTO_WATCH`** | `false` | When `true`, indexing a project automatically initializes a directory watcher. |
| **`PARALLEL_WORKERS`** | `4` | Max thread pool size for parsing code files concurrently. |
| **`CACHE_ENABLED`** | `true` | Caches file hashes to support fast incremental scans. |

### Indexing Scope Configurations

| Config Key | Default | Description |
| :--- | :--- | :--- |
| **`MAX_FILE_SIZE_MB`** | `10` | Skips source files exceeding this size limit (in Megabytes). |
| **`IGNORE_TEST_FILES`** | `false` | When `true`, skips files containing test keywords or directories like `tests/`. |
| **`IGNORE_HIDDEN_FILES`** | `true` | When `true`, skips dotfiles and hidden folders (e.g., `.github/`). |
| **`INDEX_VARIABLES`** | `true` | Extracts variable assignments into the graph. Set to `false` for smaller graph database sizes. |
| **`INDEX_SOURCE`** | `true` | Stores raw source snippets in node attributes. Set to `false` for a lighter graph. |
| **`SKIP_EXTERNAL_RESOLUTION`** | `false` | Skips looking up external Java dependencies. |

### Optional SCIP Indexer Configurations

| Config Key | Default | Description |
| :--- | :--- | :--- |
| **`SCIP_INDEXER`** | `false` | When `true`, enables SCIP-based symbol resolution. |
| **`SCIP_LANGUAGES`** | `python,typescript,go,rust,java` | List of target languages to process via SCIP. |

---

## Database Connection Configurations

### Neo4j Connection Properties
Required when `DEFAULT_DATABASE` is set to `neo4j`.

| Config Key | Default | Description |
| :--- | :--- | :--- |
| **`NEO4J_URI`** | `bolt://localhost:7687` | Server connection URI. |
| **`NEO4J_USERNAME`** | `neo4j` | Database user name. |
| **`NEO4J_PASSWORD`** | None | Database connection password. |
| **`NEO4J_DATABASE`** | `neo4j` | Logical database partition name. |

### Nornic Connection Properties
Required when `DEFAULT_DATABASE` is set to `nornic`.

| Config Key | Default | Description |
| :--- | :--- | :--- |
| **`NORNIC_URI`** | `bolt://localhost:7687` | Server connection URI (supports `nornic://` and `bolt://` schemes). |
| **`NORNIC_USERNAME`** | `nornic` | Database user name. |
| **`NORNIC_PASSWORD`** | None | Database connection password. |
| **`NORNIC_DATABASE`** | None | Logical database partition name. |

### FalkorDB Remote Connection Properties
Required when `DEFAULT_DATABASE` is set to `falkordb-remote`.

| Config Key | Default | Description |
| :--- | :--- | :--- |
| **`FALKORDB_HOST`** | `127.0.0.1` | Remote host address. |
| **`FALKORDB_PORT`** | `6379` | TCP Port. |
| **`FALKORDB_PASSWORD`** | None | Authentication password. |
| **`FALKORDB_SSL`** | `false` | Enables SSL/TLS connection socket. |
| **`FALKORDB_GRAPH_NAME`** | `codegraph` | Target graph namespace. |

### Embedded Database Directories (KuzuDB / LadybugDB / FalkorDB Lite)
Local embedded database instances are stored on disk. Use the settings below to redirect them:

| Config Key | Default | Description |
| :--- | :--- | :--- |
| **`KUZUDB_PATH`** | `~/.codegraphcontext/global/db/kuzudb/` | Root storage directory for KuzuDB files. |
| **`LADYBUGDB_PATH`** | `~/.codegraphcontext/global/db/ladybugdb/` | Root storage directory for LadybugDB files. |
| **`FALKORDB_PATH`** | `~/.codegraphcontext/global/db/falkordb/` | Storage path for FalkorDB Lite database. |

---

## Settings Precedence Levels

CGC resolves configuration keys in the following hierarchical priority (highest level overrides lower levels):

1. **CLI Flag Parameters**: Overrides passed during execution (e.g., `cgc index --db falkordb`).
2. **Runtime Environment Variables**: System environment variables (shell/CI, e.g., `export DEFAULT_DATABASE=neo4j`).
3. **Local Project Variables**: Values defined in `.codegraphcontext/.env` and `.env` in the current project directory.
4. **User Global Settings**: Configurations stored in `~/.codegraphcontext/.env` (including settings persisted by `cgc config set`).
5. **System Defaults**: Hardcoded fallback values defined within the Python package.
