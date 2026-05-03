CodeGraphContext (CGC) implements the **Model Context Protocol (MCP)**, allowing it to act as a powerful context provider for AI assistants like Claude Desktop, Cursor, and VS Code.

## 🚀 Smart Setup (Recommended)

The easiest way to configure CGC for your AI assistant is to use the interactive setup wizard. This tool will automatically detect your installed IDEs and apps and offer to configure them for you.

### Using `uvx` (No Installation Required)
If you have [uv](https://github.com/astral-sh/uv) installed, run:
```bash
uvx codegraphcontext mcp setup
```

### Using Local CLI
If you have already installed CGC, run:
```bash
codegraphcontext mcp setup
```

---

## Manual Configuration
If the automated setup doesn't work for your environment, you can configure your client manually.

## 1. Claude Desktop

To use CGC with the Claude Desktop app, you need to add it to your configuration file.

### Configuration Path
*   **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
*   **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
*   **Linux**: `~/.config/Claude/claude_desktop_config.json`

### Add CGC to `mcpServers`
Add the following entry to the `mcpServers` object:

```json
{
  "mcpServers": {
    "CodeGraphContext": {
      "command": "codegraphcontext",
      "args": ["mcp", "start"]
    }
  }
}
```

> [!TIP]
> If you installed CGC via `uvx`, you can use `"command": "uvx", "args": ["codegraphcontext", "mcp", "start"]` instead.

## 2. Cursor

Cursor supports MCP servers natively.

1.  Open **Cursor Settings** (`Cmd+,` or `Ctrl+,`).
2.  Navigate to **Features** > **MCP**.
3.  Click **+ Add New MCP Server**.
4.  Enter the following details:
    *   **Name**: `CodeGraphContext`
    *   **Type**: `command`
    *   **Command**: `codegraphcontext mcp`

## 3. VS Code (Windsurf / Kiro)

For VS Code extensions that support MCP, use the same command: `codegraphcontext mcp`. Ensure your terminal environment has access to the `codegraphcontext` command.

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
1.  Check that `codegraphcontext mcp` runs without errors in your terminal.
2.  Verify the path to the `codegraphcontext` executable in your config file.
3.  Consult the **[Troubleshooting Guide](../reference/troubleshooting.md)**.
