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

A standard CGC installation resolves the drivers permitted by its Python and platform dependency markers. Avoid independently upgrading native drivers past CGC's declared bounds; [pyproject.toml](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/pyproject.toml) is authoritative.

On Unix with Python 3.12+, CGC tries available FalkorDB Lite first. It then considers available KuzuDB and LadybugDB engines before configured graph servers. Kuzu is excluded from CGC installs on macOS/Windows with Python 3.14+, where Ladybug provides an embedded alternative. An explicit configuration can change this selection. See [Database Backends](../concepts/backends.md) and run `cgc doctor` to verify the actual engine.

Native parser grammars can require a first-use download. Prepare them before an offline demo using the [grammar cache guidance](../reference/mcp-operating-notes.md#first-use-grammars-and-offline-work).

---

## 3. Configuring the Default Backend

Set your preferred default database backend in the global configuration:

```bash
cgc config db falkordb          # FalkorDB Lite (default on Unix when falkordblite is installed)
cgc config db kuzudb          # KuzuDB (where a compatible driver is available)
cgc config db ladybugdb       # LadybugDB
cgc config db falkordb-remote # Remote FalkorDB server
cgc config db neo4j           # Neo4j
cgc config db nornic          # Nornic (Neo4j-compatible)
```

For server databases (FalkorDB Remote, Neo4j, Nornic), refer to the database connection properties in the [Configuration Reference](../reference/config.md).

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
