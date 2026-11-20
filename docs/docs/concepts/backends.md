# Database Backends

CGC can keep a code graph in a local engine or connect to a graph server. Choose based on your environment, ownership model and workload. Query features and operational requirements vary by backend.

## Supported backends

| Backend | CGC identifier | Deployment | Practical notes |
| --- | --- | --- | --- |
| FalkorDB Lite | `falkordb` | Local engine managed by CGC | Unix, Python 3.12+; requires a usable native worker. |
| KuzuDB | `kuzudb` | Native in-process property graph | Driver availability depends on Python and platform. CGC excludes Kuzu on macOS/Windows with Python 3.14+. |
| LadybugDB | `ladybugdb` | Native in-process property graph | Embedded alternative when a compatible native library is available; use CGC's declared package bounds. |
| FalkorDB Remote | `falkordb-remote` | Redis-compatible graph server | Configure `FALKORDB_HOST` and connection settings. |
| Neo4j | `neo4j` | Bolt graph server | Configure URI, username and password, or use `cgc neo4j setup`. |
| Nornic DB | `nornic` | Neo4j-compatible Bolt server | CGC connects through the Neo4j Python driver using `NORNIC_*` settings. |

Performance and graph size depend on repository structure, query shape, memory, disk and server configuration. Measure latency and capacity with your repository and target resources. See [MCP operating notes](../reference/mcp-operating-notes.md) for measured examples and limitations.

## Installation and dependency bounds

Install CGC so the package resolver applies the project's driver constraints:

```bash
pip install codegraphcontext
cgc version
cgc doctor
```

The declared bounds and environment markers in [pyproject.toml](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/pyproject.toml) are authoritative. A separately released driver version is not automatically supported by CGC. Ladybug's current upper bound is deliberate; [issue #1708](https://github.com/CodeGraphContext/CodeGraphContext/issues/1708) tracks the native Python 3.14 validation gate.

Native grammars may download on first use. For offline use, follow the [grammar cache instructions](../reference/mcp-operating-notes.md#first-use-grammars-and-offline-work).

## Local engines and process ownership

KuzuDB and LadybugDB are native graph engines. Ladybug uses a property graph model, Cypher and columnar storage. See the [Ladybug documentation](https://docs.ladybugdb.com/) for its engine model.

Use one owner for an embedded store. Multiple connections within an owning process differ from independent processes opening the same on-disk database. A running gateway or watcher can own the database lock. See [Ladybug's concurrency model](https://docs.ladybugdb.com/concurrency/) and CGC's [ownership guidance](../reference/mcp-operating-notes.md#memory-response-limits-and-ownership).

CGC can delegate supported read-only `list`/`stats` commands to an authoritative local gateway. This does not provide general write delegation for `cgc update`; [issue #1683](https://github.com/CodeGraphContext/CodeGraphContext/issues/1683) remains open for that workflow.

Storage locations depend on the active configuration context and database path. See [Configuration Contexts](../guides/contexts.md) before changing paths or moving stores.

Select one local backend:

```bash
cgc config db falkordb
# Or, when the corresponding native driver is available:
cgc config db kuzudb
cgc config db ladybugdb
```

## Server connections

Server backends use a network connection, even when the server runs on the same machine.

For FalkorDB Remote:

```bash
cgc config db falkordb-remote
cgc config set FALKORDB_HOST 127.0.0.1
cgc config set FALKORDB_PORT 6379
```

For Neo4j, run the interactive setup or configure an existing server:

```bash
cgc neo4j setup
# Alternatively:
cgc config db neo4j
cgc config set NEO4J_URI bolt://localhost:7687
cgc config set NEO4J_USERNAME neo4j
cgc config set NEO4J_PASSWORD <password>
```

For an existing Nornic server:

```bash
cgc config db nornic
cgc config set NORNIC_URI bolt://localhost:7687
cgc config set NORNIC_USERNAME nornic
cgc config set NORNIC_PASSWORD <password>
```

Use the appropriate authentication and transport settings for your deployment. See the [Configuration Reference](../reference/config.md) for supported keys.

## Selection and fallback order

1. `CGC_RUNTIME_DB_TYPE` selects a per-invocation backend, including CLI `--database` choices.
2. `DEFAULT_DATABASE` selects the configured default (`cgc config db`).
3. Without either override, `FALKORDB_HOST` selects remote FalkorDB.
4. Otherwise CGC tries usable FalkorDB Lite, available KuzuDB, available LadybugDB, configured Neo4j, then configured Nornic.

This follows `get_database_manager` in [the backend selector](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/src/codegraphcontext/core/__init__.py). Some explicit selections can also fall back when their backend is unavailable. A requested backend name does not prove that it supplied the results: inspect startup diagnostics and `cgc doctor` when validating backend behavior.
