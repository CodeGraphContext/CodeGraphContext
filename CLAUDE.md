# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in dev mode (editable)
pip install -e ".[dev]"

# Run all tests (unit + integration, no E2E)
./tests/run_tests.sh fast

# Run only unit tests
./tests/run_tests.sh unit

# Run only integration tests
pytest tests/integration/

# Run a single test file
pytest tests/unit/core/test_skip_external_resolution.py -v

# Run a single test by name
pytest tests/unit/tools/test_indexing_tuning_controls.py::test_name -v

# Run E2E tests (slow, requires no live DB)
./tests/run_tests.sh e2e

# Lint / format
black src/ tests/
```

The `cgc` CLI entry point maps to `codegraphcontext.cli.main:app` (also aliased as `codegraphcontext`).

## Architecture

### Layers

```
cli/main.py          — Typer commands; thin wrappers that call cli_helpers.py
cli/cli_helpers.py   — Orchestration: instantiate services, call tools, format output
core/                — Database managers + JobManager + FileWatcher
tools/               — GraphBuilder (indexing facade), CodeFinder, handlers for MCP tools
server.py            — MCP server: routes tool calls to tools/handlers/*
```

### Database abstraction (`core/`)

`get_database_manager()` in `core/__init__.py` is a factory that selects among four backends at runtime:

| Backend | Class | Selection |
|---|---|---|
| FalkorDB Lite (embedded) | `FalkorDBManager` | Default on Unix Python 3.12+; `CGC_RUNTIME_DB_TYPE=falkordb` |
| KùzuDB (embedded) | `KuzuDBManager` | Default on Windows / Unix Python < 3.12; `CGC_RUNTIME_DB_TYPE=kuzudb` |
| FalkorDB remote | `FalkorDBRemoteManager` | `FALKORDB_HOST` set or `CGC_RUNTIME_DB_TYPE=falkordb-remote` |
| Neo4j | `DatabaseManager` | `CGC_RUNTIME_DB_TYPE=neo4j`; requires `NEO4J_URI/USERNAME/PASSWORD` |

All backends share the same Cypher-compatible session interface, so `GraphBuilder` and `CodeFinder` are backend-agnostic.

### Indexing pipeline (`tools/indexing/`)

`GraphBuilder` is a facade; the real work is:

1. **`discovery.py`** — walk the repo, apply ignore rules (`.cgcignore`, `IGNORE_DIRS`)
2. **`pre_scan.py`** — first pass to resolve imports before the main parse
3. **`pipeline.py`** — parallel Tree-sitter parse across `ProcessPoolExecutor` / `ThreadPoolExecutor`; each file produces a `definitions` dict
4. **`scip_pipeline.py`** — alternative SCIP-based parse path (opt-in via `SCIP_INDEXER=true`)
5. **`resolution/calls.py`** and **`resolution/inheritance.py`** — post-parse relationship resolution
6. **`persistence/writer.py`** (`GraphWriter`) — batched Cypher MERGE writes to the database

### MCP server (`server.py` + `tools/handlers/`)

`MCPServer` dispatches incoming tool calls to five handler modules under `tools/handlers/`. Tool schemas are declared separately in `tool_definitions.py`. The server is launched via `cgc mcp start`.

### Configuration (`cli/config_manager.py`)

User config lives in `~/.codegraphcontext/.env` (key=value). `DEFAULT_DATABASE` and other tunables are read from there. Per-project contexts (logical workspaces) are stored in `~/.codegraphcontext/config.yaml`. The `CGC_RUNTIME_DB_TYPE` env var is a per-invocation override that takes priority over `DEFAULT_DATABASE`.

### CLI command groups

| Group | Purpose |
|---|---|
| `cgc mcp` | Start/configure the MCP server |
| `cgc index` | Index a repo into the graph |
| `cgc find` | Search by name, type, decorator, content, etc. |
| `cgc analyze` | Call chains, deps, complexity, dead code, overrides |
| `cgc query` | Raw Cypher pass-through |
| `cgc bundle` | Export / import portable `.cgc` graph bundles |
| `cgc context` | Manage named workspace contexts |
| `cgc config` | Read/write config values and set default database |
| `cgc neo4j` | Neo4j setup wizard and memory tuning |
| `cgc watch` | File-watcher for auto re-indexing |

## Testing conventions

- Unit tests heavily mock the database layer (no live DB needed).
- Integration CLI tests use `typer.testing.CliRunner`.
- Add new parser tests under `tests/unit/parsers/test_<lang>_parser.py` using the `get_tree_sitter_manager()` singleton.
- `tests/fixtures/` contains sample projects used as parse inputs; `norecursedirs` excludes them from test discovery.
- Mark slow tests with `@pytest.mark.slow`, integration tests with `@pytest.mark.integration`.
