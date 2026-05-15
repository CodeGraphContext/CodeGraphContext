# CLI: System & Configuration

Commands to manage the CodeGraphContext engine, contexts, and global settings.

## `cgc doctor`

Self-diagnostic: validates the installation and default **graph backend** (FalkorDB Lite, FalkorDB Remote, KuzuDB, or Neo4j), Python version, and core dependencies.

**Usage:**

```bash
cgc doctor
```

---

## `cgc mcp setup`

Interactive wizard for AI client integration.

**What it does:**

1. Detects installed clients (Cursor, VS Code, Claude, and others).
2. Writes MCP config fragments (for example `mcp.json`).
3. Prepares environment variables for `DEFAULT_DATABASE` and backend credentials.

**Usage:**

```bash
cgc mcp setup
```

---

## `cgc neo4j setup`

Wizard for the Neo4j server backend (Docker, local install, or Aura-style remote).

**Usage:**

```bash
cgc neo4j setup
```

---

## `cgc config` commands

Inspect and change settings without editing `.env` by hand. Persistent values are stored under `~/.codegraphcontext/.env` unless a project-local `.codegraphcontext/.env` overrides them.

- **`cgc config show`** — Print merged configuration.
- **`cgc config set <key> <value>`** — Set a key (for example `DEFAULT_DATABASE`, `SCIP_INDEXER`, `INDEX_SOURCE`).
- **`cgc config db <backend>`** — Shortcut for `cgc config set DEFAULT_DATABASE <backend>`.
- **`cgc config reset`** — Restore defaults (with confirmation).

**`DEFAULT_DATABASE` quick switch** — valid values: `falkordb`, `falkordb-remote`, `kuzudb`, `neo4j`.

```bash
cgc config set DEFAULT_DATABASE falkordb-remote
cgc config db falkordb
cgc config db falkordb-remote
cgc config db kuzudb
cgc config db neo4j
```

---

## `cgc context` commands

Named and per-repo **contexts** isolate databases and ignore rules. Configuration lives in `~/.codegraphcontext/config.yaml` plus optional per-repo `.codegraphcontext/`.

- **`cgc context list`** — Show mode (`global` / `per-repo` / `named`), default named context, and all registered contexts with database type and paths.
- **`cgc context create <name>`** — Create a named context. Optional `--database` / `-d` (`falkordb`, `kuzudb`, `neo4j`; defaults to `DEFAULT_DATABASE`). Optional `--db-path` for a custom on-disk location.
- **`cgc context delete <name>`** — Remove a context from the registry (database files remain on disk unless you delete them manually).
- **`cgc context mode <global|per-repo|named>`** — Set how the CLI resolves which graph to use.
- **`cgc context default <name>`** — Default named context when mode is `named` and no `--context` flag is passed.

**Examples:**

```bash
cgc context list
cgc context create MyMonolith --database kuzudb
cgc context mode per-repo
cgc context default MyMonolith
cgc context delete OldProject
```

Index or query with a specific named context using `--context` / `-c` on commands that support it (for example `cgc index . --context MyMonolith`).

---

## Query and search entry points

- **Graph queries:** use **`cgc query`** for read-only Cypher. The hidden alias `cgc cypher` remains for backward compatibility but prints a deprecation notice—prefer `cgc query`.
- **Structured search:** use the **`cgc find`** command group (`cgc find name`, `cgc find pattern`, and other subcommands), not a legacy `cgc search` command.

```bash
cgc query "MATCH (f:Function) RETURN f.name LIMIT 10"
cgc find name MyClass
```

---

## Related documentation

- [Configuration reference](configuration.md) — `DEFAULT_DATABASE`, SCIP flags, `INDEX_SOURCE`, and backend connection variables.
- [MCP tool overview](mcp_master.md) — Tools exposed to IDEs, including `discover_codegraph_contexts` and `switch_context`.
