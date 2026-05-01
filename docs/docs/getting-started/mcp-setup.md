# MCP Server Configuration

CodeGraphContext (CGC) implements the **Model Context Protocol (MCP)**, allowing it to act as a powerful context provider for AI assistants like Claude Desktop, Cursor, and VS Code.

## 1. Claude Desktop

To use CGC with the Claude Desktop app, you need to add it to your configuration file.

### Configuration Path
*   **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
*   **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### Add CGC to `mcpServers`
Add the following entry to the `mcpServers` object:

```json
{
  "mcpServers": {
    "CodeGraphContext": {
      "command": "cgc",
      "args": ["mcp"]
    }
  }
}
```

> [!TIP]
> If you installed CGC via `uvx`, you can use `"command": "uvx", "args": ["codegraphcontext", "mcp"]` instead.

## 2. Cursor

Cursor supports MCP servers natively.

1.  Open **Cursor Settings** (`Cmd+,` or `Ctrl+,`).
2.  Navigate to **Features** > **MCP**.
3.  Click **+ Add New MCP Server**.
4.  Enter the following details:
    *   **Name**: `CodeGraphContext`
    *   **Type**: `command`
    *   **Command**: `cgc mcp`

## 3. VS Code (Windsurf / Kiro)

For VS Code extensions that support MCP, use the same command: `cgc mcp`. Ensure your terminal environment has access to the `cgc` command.

---

## Verifying the Connection

Once configured, restart your AI assistant. You should see a list of tools provided by CodeGraphContext, such as:

*   `find_code`
*   `analyze_code_relationships`
*   `load_bundle`

You can now ask your AI things like:
> "Who calls the `handle_request` function?"
> "Explain the class hierarchy of the `BaseStorage` class."

---

## Troubleshooting

If the tools do not appear:
1.  Check that `cgc mcp` runs without errors in your terminal.
2.  Verify the path to the `cgc` executable in your config file.
3.  Consult the **[Troubleshooting Guide](../reference/troubleshooting.md)**.
