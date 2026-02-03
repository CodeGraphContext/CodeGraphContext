# Setup Deep Dive: Neo4j Wizard

This guide explains exactly what the `cgc neo4j setup` wizard does behind the scenes.

## 🪄 `cgc neo4j setup`

**Purpose:** Configures the *Storage* backend.

**What it does (Docker Mode):**

1.  Checks if `docker` is available.
2.  Runs `docker pull neo4j:latest`.
3.  Runs a container mapping ports `7474` (HTTP) and `7687` (Bolt).
4.  Sets a default password (`codegraphcontext`).

**What it does (Native Mode):**

1.  Checks for `apt` (Debian/Ubuntu).
2.  Adds the Neo4j repository keys.
3.  Runs `apt install neo4j`.

**Failure Modes:**

*   **Port Conflict:** If port 7687 is already used, the container will exit.
*   **No Docker:** Steps will fail immediately.
