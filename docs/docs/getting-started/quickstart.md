# Quickstart Guide

This guide describes how to index a local repository and run your first code structure analysis queries.

---

## 1. Index the Repository

Navigate to the root directory of the codebase you want to index. Run the `index` command to scan the codebase and populate the code graph.

```bash
cd /path/to/your/repository
cgc index
```

CGC scans your files, respects your `.gitignore` and `.cgcignore` configurations, runs Tree-sitter parsers to extract code elements, and links relationships.

---

## 2. Inspect Ingestion Statistics

Verify the indexed code structure by viewing database statistics:

```bash
cgc stats
```

The command returns metrics showing:
- Total number of files parsed
- Count of code nodes (functions, classes, modules)
- Count of resolved relationships (Containment, Invocations, Imports, Variables)

---

## 3. Query Symbol Relationships

Query the ingested graph relationships from the terminal. For example, to identify all callers of a function named `handle_request`:

```bash
cgc analyze callers handle_request
```

To see what other functions `handle_request` calls:

```bash
cgc analyze calls handle_request
```

To find a call chain/path between two functions (e.g., from `main` to `save_record`):

```bash
cgc analyze chain main save_record
```

---

## 4. Enable Real-Time Watchers

To keep your code graph updated as you write code, start a directory watcher in the background. The watcher monitors file writes and incrementally updates the graph database.

```bash
cgc watch
```

To stop a watcher, use `cgc unwatch <path>`.

---

## Next Steps

- **[MCP Server Setup](mcp-setup.md)**: Connect CodeGraphContext to your AI assistant.
- **[Indexing Guide](../guides/indexing.md)**: Learn about ignore files and deep scans.
- **[CLI Reference](../reference/cli.md)**: Full command reference manual.
