# Database Backends

CodeGraphContext (CGC) implements a pluggable database architecture. A common interface abstracts graph creation, updates, and traversals, allowing you to choose the database engine that best fits your scale, operating system, and visualization needs.

---

## Backend Comparison Matrix

| Feature / Metric | FalkorDB (Lite, Default) | LadybugDB | KuzuDB (Legacy) | FalkorDB (Remote) | Neo4j |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Type** | Embedded In-Memory | Embedded Property Graph | Embedded Property Graph | Remote Client | Remote Client |
| **Operating System** | Linux / macOS | Cross-Platform | Wheel-dependent | Cross-Platform | Cross-Platform |
| **Setup Overhead** | None | None | None | Low (Docker) | Medium (Docker/Aura) |
| **Read Latency** | Extremely Low | Very Low | Low | Low | Medium |
| **Max Capacity** | RAM-Bounded | Large | Medium | Unlimited | Unlimited |
| **Visualization** | CLI / Custom Web UI | CLI / Custom Web UI | CLI / Custom Web UI | Neo4j Client (via Cypher) | Neo4j Browser Console |

---

## 1. LadybugDB (maintained embedded backend)

LadybugDB is the maintained Kuzu fork used for embedded CGC operation. It uses the same CGC adapter and query dialect,
but it has its own storage format. A Kuzu directory must be migrated rather than opened directly.

- **Zero configuration**: Runs in process and stores data in the local `.codegraphcontext/` directory.
- **Maintained packaging**: Publishes current wheels across supported CGC platforms.
- **Version floor**: CGC requires `ladybug>=0.19,<0.20` because older and newer releases have known native failures.

### Setup

```bash
cgc config db ladybugdb
```

---

## 2. KuzuDB (legacy opt-in)

KuzuDB is archived upstream and 0.11.3 is its final release. CGC keeps explicit runtime compatibility during the
migration window, but normal installs and implicit backend selection do not use it.

### Version Compatibility

| Package | Declared bounds (`pyproject.toml`) | Versions |
| :--- | :--- | :--- |
| `kuzu` | Optional extra with platform marker | `0.11.3` (final upstream release) |

### Setup
Install the legacy extra only when an existing deployment still needs it:
```bash
pip install "codegraphcontext[kuzu]"
```
Explicitly select KuzuDB only while completing the migration:
```bash
cgc config db kuzudb
```

To leave the archived engine, follow [Migrating Legacy KuzuDB Data](../guides/migrate-from-kuzudb.md). Reusing the
same directory is unsafe because Ladybug rejects Kuzu's on-disk format.

---

## 3. FalkorDB (Lite & Remote)

FalkorDB is a low-latency, high-performance graph database. It supports two execution modes.

### FalkorDB Lite
An embedded, in-memory graph engine that uses local shared memory drivers.
- **Limitation**: Unix-only (Linux and macOS) and requires Python 3.12+.
- **Speed**: Optimal traversal latency due to in-memory index layouts.
- **Content search**: `cgc find content` uses portable substring matching on `source` and `docstring` fields (no Neo4j Lucene index required).

### FalkorDB Remote
Connects to an external Redis-compatible FalkorDB server instance running in a Docker container or network host.

### Version Compatibility

| Package | Declared bounds (`pyproject.toml`) | Versions |
| :--- | :--- | :--- |
| `falkordblite` | `>=0.7, <0.10` | `0.7.0`, `0.8.0`, `0.9.0` |
| `falkordb` | `>=1.0, <1.6` | `1.5.0` |
| `redis` | `>=5, <6` | `5.3.1` |

### Setup
Install the target drivers:
```bash
# For FalkorDB Lite
pip install falkordblite

# For FalkorDB Remote
pip install falkordb
```
Configure FalkorDB:
```bash
# Switch default database
cgc config db falkordb

# For Remote: configure connections
cgc config set FALKORDB_HOST 127.0.0.1
cgc config set FALKORDB_PORT 6379
```

---

## 4. Neo4j (Enterprise & Shared)

Neo4j is the enterprise standard for graph database clustering, management, and analysis.

- **Neo4j Browser**: Connect to `http://localhost:7474` to visualize and interact with your code graph using Neo4j's query visualizer.
- **Scale**: Handles repositories containing millions of lines of code.

### Version Compatibility

| Package | Declared bounds (`pyproject.toml`) | Versions |
| :--- | :--- | :--- |
| `neo4j` | `>=5.15.0` | `6.2.0` |

### Setup
Start a Neo4j server (e.g., using Docker):
```bash
docker run -d --name neo4j-cgc -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
```
Install the Neo4j client library:
```bash
pip install neo4j
```
Configure CGC to connect to Neo4j:
```bash
cgc config db neo4j
cgc config set NEO4J_URI bolt://localhost:7687
cgc config set NEO4J_USERNAME neo4j
cgc config set NEO4J_PASSWORD password
```

Or run the interactive wizard: `cgc neo4j setup`.

---

## 5. Nornic DB

Nornic is a Neo4j-compatible embedded graph driver. Configure it when you want Bolt/Cypher semantics without a standalone Neo4j server.

```bash
cgc config db nornic
cgc config set NORNIC_URI bolt://localhost:7687
cgc config set NORNIC_USERNAME nornic
cgc config set NORNIC_PASSWORD <password>
```

Connection keys mirror the Neo4j section in [Configuration Reference](../reference/config.md).

---

## Backend Selection Logic

When executing commands, CGC automatically resolves the active database connection using the following precedence:

1. **CLI Flag Override**: Explicitly set using `--database` or `-db` (e.g., `cgc index --database neo4j`).
2. **Environment Variable**: Resolves via `CGC_RUNTIME_DB_TYPE` settings.
3. **Global Config File**: Reads the value set via `cgc config db`.
4. **Fallback Auto-Detection**:
   - If `FALKORDB_HOST` env is present, connects to FalkorDB Remote.
   - On Unix: Tries FalkorDB Lite, then LadybugDB, then configured Neo4j or Nornic.
   - On Windows: Tries LadybugDB, then configured Neo4j or Nornic.
   - KuzuDB is never selected implicitly.
