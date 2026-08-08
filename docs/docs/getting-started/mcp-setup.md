# Model Context Protocol Setup

CodeGraphContext (CGC) implements the Model Context Protocol (MCP). This enables LLM-powered applications and IDE extensions to discover and invoke tools that fetch context directly from your code graph.

---

## 1. Automated Setup (Recommended)

CGC includes an interactive wizard that detects supported IDEs and applications on your system and configures their MCP client settings automatically.

Run the wizard from your terminal:

```bash
cgc mcp setup
```

The wizard will locate configuration files for Claude Desktop, Cursor, and other compatible environments, and request permission to add CodeGraphContext as a local tool provider.

---

## 2. Manual Client Configuration

If you prefer to configure your workspace manually, refer to the client configurations below.

### Claude Desktop

To configure Claude Desktop to run the local CGC server, add a configuration entry to the `claude_desktop_config.json` file.

#### Configuration File Locations:
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### Configuration Schema:
Add the following key under the `mcpServers` object:

```json
{
  "mcpServers": {
    "codegraphcontext": {
      "command": "cgc",
      "args": ["mcp", "start"]
    }
  }
}
```

*Note: If you are running CGC in an isolated virtual environment or using `uvx`, adjust the command accordingly (e.g., using `uvx codegraphcontext mcp start`).*

---

### Cursor IDE

Cursor supports local MCP servers via direct process execution:

1. Open **Cursor Settings** (Preferences / Settings -> Features -> MCP).
2. Click **+ Add New MCP Server**.
3. Fill in the fields:
   - **Name**: `CodeGraphContext`
   - **Type**: `command`
   - **Command**: `cgc mcp start`
4. Click **Save**.

---

### OpenCode

OpenCode manages MCP in its own UI. Follow the vendor's guide at [OpenCode MCP servers](https://opencode.ai/docs/ko/mcp-servers/#_top) to register a stdio server.

Use the following configuration details:
- **Type**: `stdio`
- **Command**: `cgc`
- **Arguments**: `mcp start`

*Note: Ensure your database credentials and configurations match what `cgc mcp setup` generated (usually in `~/.codegraphcontext/.env`).*

---

### VS Code (via Continue extension)

If you use VS Code with the [Continue.dev](https://continue.dev) plugin:

1. Open your Continue configuration file (`~/.continue/config.json`).
2. Add the server details inside the `contextProviders` or `mcp` settings array:

```json
{
  "mcp": {
    "codegraphcontext": {
      "command": "cgc",
      "args": ["mcp", "start"]
    }
  }
}
```

---

## 3. Verifying Tool Connectivity

After restarting your IDE or Claude Desktop app, verify that the 21 MCP tools are active. You should see commands like:

- `find_code` (Keyword search across symbols and file contents)
- `analyze_code_relationships` (Lookup callers, callees, and inheritance paths)
- `execute_cypher_query` (Execute direct database Cypher statements)

You can verify it by prompting the assistant:
> "Analyze the call path between the `process_data` and `db_commit` functions in my current codebase."

---

## 4. Connection Troubleshooting

If the tools do not load:
1. **Command Resolution**: Verify that the `cgc` command is present in your system's global `PATH`. If you installed via a virtual environment, use the absolute path to the executable (e.g., `/usr/local/bin/cgc` or `/home/user/.local/bin/cgc`).
2. **Process Integrity**: Test starting the server manually in your shell by running `cgc mcp start`. It should listen on standard input/output (stdin/stdout) for JSON-RPC messages and not exit immediately.
3. **Database Selection**: Ensure your default database is configured and has indexed data. Run `cgc doctor` to verify configuration.
