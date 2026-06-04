# Ingesting & Installing CodeGraphContext

CodeGraphContext (CGC) is packaged as a standard Python utility. The CLI and server components are installed using Python package managers.

---

## 1. CLI Installation

### Method A: Execution via `uvx` (Recommended)
If you use [uv](https://github.com/astral-sh/uv), you can run the CGC CLI on demand without installing it globally:

```bash
uvx codegraphcontext --help
```

### Method B: Isolated Global Installation via `pipx`
To install the CLI in an isolated Python environment and make it globally available:

```bash
pipx install codegraphcontext
```

### Method C: Standard Package Installation via `pip`
To install CGC in your active Python or virtual environment:

```bash
pip install codegraphcontext
```

---

## 2. Database Driver Setup

CGC requires Python driver bindings for your selected database backend. FalkorDB Lite is configured by default.

### Installing KuzuDB Drivers
KuzuDB is embedded and runs directly inside the Python process.
```bash
pip install kuzu
```

### Installing FalkorDB Drivers (Optional)
If using the FalkorDB backend:
- **Embedded Lite** (Unix and Python 3.12+ only):
  ```bash
  pip install falkordblite
  ```
- **Remote Server Client**:
  ```bash
  pip install falkordb
  ```

### Installing Neo4j Drivers (Optional)
If connecting to a standalone Neo4j instance:
```bash
pip install neo4j
```

---

## 3. Configuring the Default Backend

Set your preferred default database backend in the global configuration:

```bash
cgc config db falkordb     # Configure FalkorDB Lite / Remote (Default)
cgc config db kuzudb       # Configure KuzuDB
cgc config db ladybugdb    # Configure LadybugDB
cgc config db neo4j        # Configure Neo4j
```

For remote databases (FalkorDB Remote, Neo4j), refer to the database connection properties in the [Configuration Reference](../reference/config.md).

---

## 4. Validating the Installation

Verify that the CLI and its database bindings are correctly loaded using the diagnostics tool:

```bash
# Verify the installed CLI version
cgc version

# Run the system diagnostics check
cgc doctor
```

The `doctor` command executes self-tests on the configuration, tests database drivers, and confirms directory permissions.

---

## 5. Next Steps

Once the CLI is verified, continue to index your project workspace.

**[Proceed to Quickstart →](quickstart.md)**
