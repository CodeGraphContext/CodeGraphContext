# Configuration Reference

CodeGraphContext (CGC) is configured using environment variables, local configuration files, and the CLI.

---

## Important defaults (read this first)

These three points are the most common sources of confusion in older docs and issue reports:

### Default database backend

| Platform | What CGC uses by default |
| :--- | :--- |
| **Unix (Linux/macOS), Python 3.12+** | **FalkorDB Lite** when `falkordblite` is installed (`DEFAULT_DATABASE=falkordb`) |
| **Windows**, or FalkorDB Lite unavailable | **KuzuDB** as the automatic fallback |
| **Any platform** | Override anytime with `cgc config db <backend>` |

KuzuDB is **not** the universal default—it is the cross-platform fallback when FalkorDB Lite cannot run.

### Neo4j username key

Use **`NEO4J_USERNAME`**, not `NEO4J_USER`. The latter is not a valid `cgc config set` key.

```bash
cgc config set NEO4J_USERNAME neo4j
```

### Project-local `.env` files

Repository `.codegraphcontext/.env` and `.env` files are loaded **only in per-repo context mode** (or when `CGC_LOAD_PROJECT_ENV=1`). In **global** or **named** mode, `~/.codegraphcontext/.env` wins so cloned repos cannot override your credentials. Set `CGC_IGNORE_PROJECT_ENV=1` to force-skip project env.

See [Project-Local Environment Files](#project-local-environment-files) below for the full precedence table.

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

Valid database backend identifiers: `kuzudb`, `ladybugdb`, `falkordb` (Lite/embedded), `falkordb-remote`, `neo4j`, and `nornic`.

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

## Project-Local Environment Files

Repository-level env files are **not** loaded in every mode:

| File | When it applies |
| :--- | :--- |
| `~/.codegraphcontext/.env` | Always (global defaults) |
| `<repo>/.codegraphcontext/.env` | **Per-repo mode only** (or when `CGC_LOAD_PROJECT_ENV=1`) |
| `<repo>/.env` | **Per-repo mode only** (searched up to 5 parent directories) |

In **global** or **named** context mode, a checked-in `.codegraphcontext/.env` inside a clone does **not** override your user config—this prevents accidental hijacking when indexing third-party repos.

Override flags:

- `CGC_IGNORE_PROJECT_ENV=1` — never load project-local env.
- `CGC_LOAD_PROJECT_ENV=1` — always load project-local env (even outside per-repo mode).

---

## Settings Precedence Levels

CGC resolves configuration keys in the following hierarchical priority (highest level overrides lower levels):

1. **CLI flag parameters** — e.g. `cgc index --db neo4j`.
2. **Runtime environment variables** — shell/CI exports and `CGC_RUNTIME_DB_TYPE`.
3. **Project-local env** — `.codegraphcontext/.env` / `.env` (per-repo mode only; see above).
4. **User global settings** — `~/.codegraphcontext/.env` (including values from `cgc config set`).
5. **System defaults** — hardcoded fallbacks in the package.
