# Configuration & Settings

CodeGraphContext **0.4.6** is configurable through environment variables, `~/.codegraphcontext/.env`, per-project `.codegraphcontext/.env`, and the `cgc config` CLI.

## `cgc config` Command

View and modify settings from the terminal.

### 1. View Settings

Shows the current effective configuration (merged from defaults and `.env`).

```bash
cgc config show
```

### 2. Set a Value

Update a setting permanently. This writes to `~/.codegraphcontext/.env`.

**Syntax:** `cgc config set <KEY> <VALUE>`

```bash
# Switch default graph database
cgc config set DEFAULT_DATABASE neo4j

# Increase max file size to index (MB)
cgc config set MAX_FILE_SIZE_MB 20

# Enable automatic watching after index
cgc config set ENABLE_AUTO_WATCH true

# Opt in to SCIP-based indexing (requires scip-<lang> binaries)
cgc config set SCIP_INDEXER true

# Limit which languages use SCIP when SCIP_INDEXER=true
cgc config set SCIP_LANGUAGES python,typescript,go,rust,java

# Store full source text in the graph (true) vs lighter graph (false)
cgc config set INDEX_SOURCE true
```

### 3. Quick Switch Database

Shortcut for `cgc config set DEFAULT_DATABASE <backend>`. Valid backends: **`falkordb`**, **`falkordb-remote`**, **`kuzudb`**, **`neo4j`**.

```bash
cgc config db falkordb
cgc config db falkordb-remote
cgc config db kuzudb
cgc config db neo4j
```

---

## Configuration Reference

### Core settings

| Key | Default | Description |
| :--- | :--- | :--- |
| **`DEFAULT_DATABASE`** | `falkordb` | Active database: `falkordb` (FalkorDB Lite), `falkordb-remote`, `kuzudb`, or `neo4j`. On Unix with Python 3.12+, FalkorDB Lite is the typical default; LadybugDB is the common embedded fallback (including Windows). |
| **`ENABLE_AUTO_WATCH`** | `false` | If `true`, `cgc index` can automatically start watching for changes. |
| **`PARALLEL_WORKERS`** | `4` | Parallel workers during indexing. |
| **`CACHE_ENABLED`** | `true` | Cache file hashes to speed up re-indexing. |

### Indexing scope

| Key | Default | Description |
| :--- | :--- | :--- |
| **`MAX_FILE_SIZE_MB`** | `10` | Files larger than this (in MB) are skipped. |
| **`IGNORE_TEST_FILES`** | `false` | If `true`, skips test-oriented files during indexing. |
| **`IGNORE_HIDDEN_FILES`** | `true` | Skips hidden files and directories. |
| **`IGNORE_DIRS`** | Common dirs such as `node_modules`, `venv`, `.git`, `dist`, `build`, … | Comma-separated directory names to skip during indexing. |
| **`INDEX_VARIABLES`** | `true` | Creates variable nodes; set `false` for a smaller graph. |
| **`INDEX_SOURCE`** | `true` | When `true`, stores full source in the graph; set `false` for a lighter index. |
| **`SKIP_EXTERNAL_RESOLUTION`** | `false` | Skip resolving external library calls (useful for very large Java/Spring trees). |

### Optional SCIP indexing

SCIP is **opt-in**. Tree-sitter remains the default across **19** language parsers.

| Key | Default | Description |
| :--- | :--- | :--- |
| **`SCIP_INDEXER`** | `false` | When `true`, uses SCIP where supported for richer call/inheritance resolution. Requires `scip-<language>` tooling for each language you enable. |
| **`SCIP_LANGUAGES`** | `python,typescript,go,rust,java` | Comma-separated list of languages to index via SCIP when `SCIP_INDEXER=true`. |

### Database connection — Neo4j

| Key | Description |
| :--- | :--- |
| **`NEO4J_URI`** | Bolt URI (e.g. `bolt://localhost:7687`). |
| **`NEO4J_USERNAME`** | Database user (often `neo4j`). |
| **`NEO4J_PASSWORD`** | Database password. |
| **`NEO4J_DATABASE`** | Optional Neo4j 4+ database name. |

### Database connection — FalkorDB Lite (embedded)

| Key | Description |
| :--- | :--- |
| **`FALKORDB_PATH`** | Path to the FalkorDB Lite database files. |
| **`FALKORDB_SOCKET_PATH`** | Unix socket path used by the embedded FalkorDB Lite process. |

### Database connection — FalkorDB Remote

Set `DEFAULT_DATABASE=falkordb-remote` **or** rely on auto-detection when **`FALKORDB_HOST`** is set.

| Key | Description |
| :--- | :--- |
| **`FALKORDB_HOST`** | Remote FalkorDB hostname or IP (required for remote mode). |
| **`FALKORDB_PORT`** | TCP port (commonly `6379`). |
| **`FALKORDB_PASSWORD`** | Password when the server requires authentication. |
| **`FALKORDB_USERNAME`** | Username if required by the deployment. |
| **`FALKORDB_SSL`** | `true` / `false` for TLS to the remote endpoint. |
| **`FALKORDB_GRAPH_NAME`** | Logical graph name (default often `codegraph`). |

### Database path — LadybugDB (embedded)

LadybugDB is an embedded database (no separate server process). The on-disk location is controlled by:

| Key / mechanism | Description |
| :--- | :--- |
| **`KUZUDB_PATH`** | Filesystem path for the LadybugDB database directory/file. If unset, defaults under `~/.codegraphcontext/global/kuzudb` (or the path resolved for the active **context**). |
| **Named contexts** | `cgc context create …` stores each context’s database under `~/.codegraphcontext/contexts/<name>/db/…` unless you pass `--db-path`. |

Install the Python package with `pip install real_ladybug` when using `DEFAULT_DATABASE=kuzudb`.

---

## Configuration files

CodeGraphContext merges settings in this order (later overrides earlier where applicable):

1. **Project:** `.cgcignore` at the repo root (indexing exclusions).
2. **Project:** `.codegraphcontext/.env` when present (per-repo overrides).
3. **User:** `~/.codegraphcontext/.env` (global defaults for keys managed by `cgc config set`).
4. **Built-in defaults** in the application.

To reset managed keys to defaults:

```bash
cgc config reset
```
