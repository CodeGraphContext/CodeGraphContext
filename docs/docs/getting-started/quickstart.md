# Quickstart Guide

Get up and running with CodeGraphContext in under 5 minutes. This guide covers indexing a repository and performing your first semantic query.

## 1. Index a Repository

Navigate to any local codebase and run the `index` command. This will scan your files and build the initial code graph.

```bash
cd /path/to/your/project
cgc index
```

CGC will automatically detect the programming languages in your project and use the appropriate Tree-sitter parsers.

## 2. Verify the Index

Once indexing is complete, you can check the statistics of your code graph:

```bash
cgc stats
```

You should see counts for files, functions, classes, and relationships that were successfully extracted.

## 3. Perform Your First Query

Now you can query the graph directly from your terminal. For example, to find all callers of a specific function:

```bash
cgc query callers "your_function_name"
```

To see a visual representation of your code structure:

```bash
cgc visualize
```

## 4. Live Updates

If you are actively developing, use the `watch` command. CGC will monitor your file system and incrementally update the graph as you save changes.

```bash
cgc watch
```

---

## What's Next?

*   **[MCP Setup](mcp-setup.md)**: Connect this graph to Claude or Cursor.
*   **[Indexing Guide](../guides/indexing.md)**: Learn about deep scans and dependency indexing.
*   **[CLI Reference](../reference/cli.md)**: Explore all available commands.
