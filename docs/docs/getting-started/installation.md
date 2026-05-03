# Installation

CodeGraphContext (CGC) is distributed as a Python package. You can install it using several methods depending on your workflow.

## 1. Install the CLI

### Recommended: Using `uvx` (Fastest)
If you use [uv](https://github.com/astral-sh/uv), you can run CGC instantly without manual installation:

```bash
uvx codegraphcontext --help
```

### Using `pipx` (Isolated)
For a persistent global installation in an isolated environment:

```bash
pipx install codegraphcontext
```

### Using `pip`
```bash
pip install codegraphcontext
```

---

## 2. Database Backend Selection

CGC requires a graph database to store the indexed code. You can choose the backend that best fits your needs.

### Option A: LadybugDB (Default & Recommended)
LadybugDB is an embedded, extremely fast graph database. It requires zero configuration and runs directly within the CGC process.

*   **Installation**: `pip install real_ladybug`
*   **Best for**: Local development, individual projects, and zero-ops setups.
*   **Pros**: No external services, portable database files.

### Option B: FalkorDB (High Performance)
FalkorDB is a low-latency graph database. CGC supports both local (embedded) and remote instances.

*   **Installation**: `pip install falkordblite` (Linux/macOS only)
*   **Best for**: Large codebases and performance-critical queries.
*   **Pros**: Industry-leading query performance.
*   **Note**: We use `falkordblite` for supported devices (Python 3.12+ on Unix), and LadybugDB (kuzudb) for the rest. We have largely shifted to LadybugDB as the primary embedded engine.

### Option C: Neo4j (Enterprise)
Neo4j is the industry standard for graph databases, offering powerful visualization and management tools.

*   **Best for**: Teams, massive repositories, and deep visual analysis via the Neo4j Browser.
*   **Setup**: Requires a running Neo4j instance (Docker or Cloud).
    ```bash
    codegraphcontext config set-db neo4j
    ```

---

## 3. Verify Installation

To ensure everything is configured correctly, run the version check:

```bash
codegraphcontext --version
```

You can also run the diagnostic command to check backend connectivity:

```bash
codegraphcontext doctor
```

---

## 4. Next Steps

Now that CGC is installed, you are ready to index your first repository.

**[Proceed to Quickstart →](quickstart.md)**
