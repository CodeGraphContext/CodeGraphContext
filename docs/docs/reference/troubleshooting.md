# Troubleshooting

This guide provides solutions for common issues encountered while installing or using CodeGraphContext.

## 1. Installation Issues

### `uvx` or `pipx` command not found
*   **Solution**: Ensure that your Python environment is correctly set up and that the installation directory for `pipx` or `uv` is in your system's `PATH`.
*   **Verification**: Run `python -m pip install --user pipx` followed by `pipx ensurepath`.

### Failed to install `real_ladybug` (KùzuDB)
*   **Cause**: KùzuDB requires C++ build tools on some platforms during installation.
*   **Solution**:
    *   **Windows**: Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
    *   **macOS**: Run `xcode-select --install`.
    *   **Linux**: Install `build-essential` and `python3-dev`.

---

## 2. Database Connectivity

### "No database backend available"
*   **Cause**: No supported database is installed or configured.
*   **Solution**: Install KùzuDB (recommended): `pip install real_ladybug`.

### Neo4j: "Authentication failed"
*   **Cause**: Incorrect credentials in environment variables or `.env` file.
*   **Solution**: Verify `NEO4J_USERNAME` and `NEO4J_PASSWORD`. Run `cgc config list` to check current settings.

---

## 3. MCP Integration

### Tools do not appear in Claude/Cursor
*   **Check 1**: Ensure the MCP server is running correctly. Run `cgc mcp` in your terminal. It should wait for input without exiting immediately.
*   **Check 2**: Verify the path to the `cgc` executable in your configuration file. Use absolute paths if necessary.
*   **Check 3**: Look at the logs. CGC logs to `~/.codegraphcontext/logs/mcp.log` by default.

### "Connection refused" in MCP
*   **Cause**: The database backend is not reachable by the MCP server.
*   **Solution**: Ensure your database (e.g., Neo4j Docker container) is running before starting the MCP server.

---

## 4. Indexing Issues

### Indexing is slow
*   **Tip**: Use the `watch` command for incremental updates instead of full re-indexes.
*   **Tip**: Exclude large, irrelevant directories (like `node_modules` or `dist`) using a `.cgcignore` file.

### "Tree-sitter parser not found"
*   **Cause**: The parser for a specific language failed to load or is not supported.
*   **Solution**: Ensure you are using a recent version of `codegraphcontext`. Run `pip install --upgrade codegraphcontext`.

---

## 5. Diagnostic Command

If you are still having trouble, run the built-in diagnostic tool:

```bash
cgc doctor
```

This command checks for:
*   Python version compatibility.
*   Installed database backends.
*   Active configuration settings.
*   Write permissions for log and data directories.