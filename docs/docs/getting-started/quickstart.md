# Quickstart (5 Minutes)

Let's index a project and run your first analysis.

## 1. Index Code

Pick a small folder to start with (e.g., this project's own directory).

!!! tip "Tip: Ignore Files First"
    You can create a `.cgcignore` file (like `.gitignore`) to skip folders like `node_modules` or `venv`.
    [📄 Configure .cgcignore](../reference/cgcignore.md)

```bash
cgc index .
```
*You will see the tool parsing files and creating nodes in the database.*

## 2. Lists Repos

Confirm it was added to the graph.

```bash
cgc list
```

## 3. Run Your First Analysis

Let's ask the graph a question. "Find all callers of a function".
*Replace `my_function` with a real function name from your code.*

```bash
cgc analyze callers my_function
```

## 4. (Optional) Visualize

If you have a browser available, seeing is believing.

```bash
cgc visualize
```
*This command generates a link. Click it to open the Graph Browser.*

---

## What's Next?

You have two paths forward:

1.  **I want to code with AI:**
    *   [👉 Setup AI Assistant (MCP)](../guides/mcp_guide.md)
    *   [👉 Explore Natural Language Queries](../reference/mcp_master.md)
    *   [⚙️ Customize Settings](../reference/configuration.md)
2.  **I want to use the Terminal:**
    *   [👉 Explore CLI Commands](../reference/cli_indexing.md)
    *   [⚙️ Customize Settings](../reference/configuration.md)
