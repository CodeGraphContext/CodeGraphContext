---
name: codegraphcontext
description: >-
  Use CodeGraphContext (CGC) to index a repo into a graph DB and query it via CLI
  or MCP. Apply when the user wants semantic/code-graph search, call graphs,
  indexing, or configuring the codegraphcontext MCP server.
---

# CodeGraphContext (CGC)

## When to use this skill

- Indexing or re-indexing a codebase for AI or CLI queries.
- Explaining how to install and run `cgc`, choose a database backend, or wire MCP into an editor.
- Interpreting CGC tools: `codegraph_find_code`, `analyze_code_relationships`, `add_code_to_graph`, etc.

## Core workflow

1. **Install**: `pip install codegraphcontext` (or `pipx install codegraphcontext`). With **uv**, `uv tool install codegraphcontext` or `uvx codegraphcontext …` is supported; if a parser fails with `ModuleNotFoundError: tree_sitter_c_sharp`, run with an explicit extra package, e.g. `uvx --with tree-sitter-c-sharp codegraphcontext …`.
2. **Configure**: Optional `~/.codegraphcontext/.env` for `DEFAULT_DATABASE`, Neo4j URI, or Kùzu path. Run `cgc doctor` if connections fail.
3. **Index**: From the repo root, `cgc index .` (or `cgc index --force .` to rebuild). Ensure CLI and MCP use the same config so they see the same graph.
4. **Query**: CLI (`cgc find`, `cgc query`, …) or MCP tools after `cgc mcp setup` / `cgc mcp start` in the client config.

## MCP setup (short)

- Run `cgc mcp setup` and pick the editor, or add a server entry that runs `cgc` with args `mcp` `start` and the same env as the CLI.
- **OpenCode**: Follow the vendor MCP docs for registering a stdio server, then point the command at `cgc` with arguments `mcp`, `start` (same as other editors). Official OpenCode MCP overview: [OpenCode MCP servers](https://opencode.ai/docs/ko/mcp-servers/#_top).

## Agent behavior

- Prefer **indexing the workspace** before deep graph queries if the user has not indexed yet.
- For **fuzzy symbol search** on Kùzu/Falkor backends, matching is typo-tolerant (edit distance); on Neo4j, full-text fuzzy uses Lucene-style terms—preserve **original casing** in queries when fuzziness matters for camelCase symbols.
- If **`Repository.path` is missing** in the DB, that row is skipped for path checks and a **warning is logged** when repositories are listed; suggest cleaning stale `Repository` nodes (see Neo4j example in logs) if it keeps happening.

## References in this repo

- CLI entry: `codegraphcontext.cli.main`
- MCP server and tool wiring: `codegraphcontext.server`, `tool_definitions.py`
- User-facing setup detail: `docs/docs/setup_workflows.md`, `docs/docs/guides/mcp_guide.md`
- Published copy of this skill (for docs / GitHub): `docs/docs/agent_skill_codegraphcontext.md`
