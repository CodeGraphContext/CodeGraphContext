# CLI: System & Configuration

Commands to manage the CodeGraphContext engine itself.

## `cgc doctor`

Self-diagnostic tool. Runs a health check on your installation.

**Checks performed:**

*   Database connectivity (Neo4j / FalkorDB).
*   Python version compatibility.
*   Required dependencies.

**Usage:**
```bash
cgc doctor
```

---

## `cgc mcp setup`

The interactive wizard for configuring AI clients.

**What it does:**

1.  Detects installed AI Clients (Cursor, VS Code, Claude).
2.  Creates the necessary config files (e.g., `mcp.json`).
3.  Generates a `.env` file with database credentials.

**Usage:**
```bash
cgc mcp setup
```

---

## `cgc neo4j setup`

The interactive wizard for configuring the graph database backend.

**What it does:**

*   **Docker:** Pulls and runs the official Neo4j image.
*   **Local:** Helps locate a local installation.
*   **Remote:** Configures credentials for AuraDB.

**Usage:**
```bash
cgc neo4j setup
```

---

## `cgc config` Commands

Directly modify settings without editing text files.

*   `cgc config show`: Print current configuration.
*   `cgc config set <key> <value>`: Update a setting.
    *   Example: `cgc config set DEFAULT_DATABASE neo4j`
*   `cgc config db <backend>`: Switch backends (shortcut).
    *   Example: `cgc config db falkordb`
