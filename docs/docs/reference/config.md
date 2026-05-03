# Configuration

CodeGraphContext (CGC) can be configured via environment variables, a global config file, or project-specific `.cgcignore` files.

## Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DEFAULT_DATABASE` | Sets the default backend (`kuzudb`, `falkordb`, `neo4j`). | `kuzudb` |
| `FALKORDB_HOST` | Hostname for remote FalkorDB instance. | `localhost` |
| `NEO4J_URI` | URI for Neo4j connection. | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | Username for Neo4j authentication. | `neo4j` |
| `NEO4J_PASSWORD` | Password for Neo4j authentication. | - |
| `CGC_LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). | `INFO` |

---

## The `cgc config` Command

You can manage persistent settings using the CLI:

```bash
# Set the default database
cgc config set-db neo4j

# View all current settings
cgc config list
```

---

## Ignoring Files (`.cgcignore`)

To prevent specific files or directories from being indexed, create a `.cgcignore` file in your repository root. CGC follows standard glob patterns similar to `.gitignore`.

### Common Patterns
```text
# Exclude build artifacts
dist/
build/
*.egg-info

# Exclude dependencies (if you don't want them in the graph)
node_modules/
venv/
.venv/

# Exclude large data files
*.json
*.csv
```

---

## Advanced: Performance Tuning

For large-scale indexing, you can adjust the following internal parameters (via env vars):

*   **`CGC_MAX_THREADS`**: Number of concurrent workers for parsing files.
*   **`CGC_CHUNK_SIZE`**: Number of nodes to batch before committing to the database.
*   **`CGC_PARSER_TIMEOUT`**: Timeout in seconds for individual file parsing.
