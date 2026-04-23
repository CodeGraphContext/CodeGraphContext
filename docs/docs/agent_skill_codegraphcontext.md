# Agent skill: CodeGraphContext (CGC)

This is the **published copy** of the Cursor agent skill for CodeGraphContext. The same content lives under `.cursor/skills/codegraphcontext/SKILL.md` for Cursor users who clone the repo; both stay in sync when we update workflows.

---

```yaml
# YAML frontmatter (Cursor SKILL.md format)
name: codegraphcontext
description: >-
  Use CodeGraphContext (CGC) to index a repo into a graph DB and query it via CLI
  or MCP. Apply when the user wants semantic/code-graph search, call graphs,
  indexing, or configuring the codegraphcontext MCP server.
```

## When to use this skill

- Indexing or re-indexing a codebase for AI or CLI queries.
- Explaining how to install and run `cgc`, choose a database backend, or wire MCP into an editor.
- Interpreting CGC tools: `codegraph_find_code`, `analyze_code_relationships`, `add_code_to_graph`, etc.

## Core workflow

1. **Install**: `pip install codegraphcontext` (or `pipx install codegraphcontext`). With **uv**, `uv tool install codegraphcontext` or `uvx codegraphcontext …` is supported. `tree-sitter-c-sharp` is declared in this project’s `pyproject.toml`, but some **uvx** isolated environments have still failed to install it; if you see `ModuleNotFoundError: tree_sitter_c_sharp`, use e.g. `uvx --with tree-sitter-c-sharp codegraphcontext …`.
2. **Configure**: Optional `~/.codegraphcontext/.env` for `DEFAULT_DATABASE`, Neo4j URI, or LadybugDB path. Run `cgc doctor` if connections fail.
3. **Index**: From the repo root, `cgc index .` (or `cgc index --force .` to rebuild). Ensure CLI and MCP use the same config so they see the same graph.
4. **Query**: CLI (`cgc find`, `cgc query`, …) or MCP tools after `cgc mcp setup` / `cgc mcp start` in the client config.

## MCP setup (short)

- Run `cgc mcp setup` and pick your editor (including **OpenCode** for printed stdio instructions), or add a server entry that runs `cgc` with args `mcp` `start` and the same env as the CLI.
- **OpenCode**: [OpenCode MCP servers](https://opencode.ai/docs/ko/mcp-servers/#_top).

## Agent behavior

- Prefer **indexing the workspace** before deep graph queries if the user has not indexed yet.
- For **fuzzy symbol search** on LadybugDB/Falkor backends, matching is typo-tolerant (edit distance); on Neo4j, full-text fuzzy uses Lucene-style terms—preserve **original casing** in queries when fuzziness matters for camelCase symbols.
- If **`Repository.path` is missing** in the DB, those rows are skipped for path matching and a **warning is logged** when repositories are listed; clean up stale nodes if needed.

## Multi-graph support (MCP)

- One server instance can serve many isolated graphs. A **"graph"** here is a **FalkorDB named graph** or a **Neo4j database**. KùzuDB has no equivalent concept.
- Most query and indexing tools accept an optional **`graph_name`** argument that targets a specific graph per call. Omitting it falls back to `FALKORDB_GRAPH_NAME` / `NEO4J_DATABASE` env defaults, so single-graph use is unchanged.
- Use **`list_graphs`** for discovery when an agent needs to pick a graph (FalkorDB → `GRAPH.LIST`, Neo4j → `SHOW DATABASES`, Kùzu → empty list).
- **Multi-turn continuity:** once a user has established a target graph in the conversation, keep passing that same `graph_name` to subsequent tool calls until they explicitly change graphs. If unsure which graph applies, call `list_graphs` and ask rather than silently falling back to the default.
- **"graph" ≠ "repository" ≠ "cgc context."** `graph_name` addresses a backend namespace; `list_indexed_repositories` enumerates `Repository` nodes *inside* a graph; `discover_codegraph_contexts` / `switch_context` operate on filesystem `.codegraphcontext/` workspaces and are unrelated to backend graph selection.

## References in this repo

- CLI entry: `codegraphcontext.cli.main`
- MCP server and tool wiring: `codegraphcontext.server`, `tool_definitions.py`
- User-facing setup: [Setup workflows](setup_workflows.md), [MCP guide](guides/mcp_guide.md)
