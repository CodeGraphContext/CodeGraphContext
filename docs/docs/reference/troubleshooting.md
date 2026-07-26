# Troubleshooting Manual

This guide detail procedures for identifying, diagnosing, and resolving issues when setting up or executing CodeGraphContext.

---

## 1. Engine Installation & Compilation Issues

### KuzuDB Installation Errors (C++ Compiler Required)
KuzuDB relies on a compiled C++ engine core. If `pip install kuzu` fails:
- **Reason**: The pre-compiled wheel is not available for your system architecture/Python version, forcing a compile from source without build tools.
- **Resolution**:
  - **Linux**: Install build essentials: `sudo apt-get install build-essential python3-dev`
  - **macOS**: Install developer CLI tools: `xcode-select --install`
  - **Windows**: Install [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) via Visual Studio Installer.

### FalkorDB Lite Unix Dependencies
FalkorDB Lite only runs on Linux/macOS and requires **Python 3.12+**.
- **Reason**: Underlying shared libraries are not compiled for Windows or older Python interpreter versions.
- **Resolution**: Switch the active database context backend to `kuzudb` which is fully cross-platform.

---

## 2. Database Connection Failures

### "No database backend available"
- **Reason**: CGC is looking for KuzuDB, FalkorDB, or Neo4j, but the respective Python client packages are missing from the current virtual environment.
- **Resolution**: Verify package installations:
  ```bash
  pip install kuzu neo4j falkordb
  ```

### Neo4j Connection Refused / Auth Failures
- **Reason**: Connection parameters in configuration do not match your running Neo4j Instance.
- **Resolution**: Run `cgc config show` to check host bindings and credentials. Verify that the Neo4j instance is up and accepting TCP connections (e.g., using `telnet localhost 7687` or via Docker logs).

---

## 3. MCP Server & Daemon Failures

### IDE Assistant Fails to Load Tools
If Claude Desktop or Cursor does not show CGC tools:
- **Step 1: Process Check**: Test the server execution by running the launch command directly in your shell:
  ```bash
  cgc mcp start
  ```
  The server should wait for input on stdin/stdout. If it immediately crashes or exits, inspect the stack trace.
- **Step 2: Absolute Executable Paths**: IDEs often run in isolated shell contexts that do not inherit your user shell's `PATH`. Replace the `cgc` command with the absolute path in your IDE configuration files:
  - Find the absolute path using: `which cgc` (Linux/macOS) or `where cgc` (Windows).
  - Update `command` in JSON (e.g., `/home/username/.local/bin/cgc`).
- **Step 3: Logs Inspection**: Review the server log files. MCP server logs are written to:
  `~/.codegraphcontext/logs/mcp.log`

---

## 4. Indexing & Filesystem Watcher Failures

### Indexing is Slow or Out of Memory
- **Reason**: CGC is attempting to index massive build folders, dependencies, or compiled files (e.g., `.git/`, `node_modules/`, `venv/`).
- **Resolution**: Ensure a `.cgcignore` file is present in the repository root containing appropriate ignore rules (refer to the [Indexing Guide](../guides/indexing.md)).

### Directory Watcher Fails to Update
- **Reason**: The watchdog monitor has run out of system file handles (common on Linux with large repositories).
- **Resolution**: Increase the max user watches value:
  ```bash
  echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && sudo sysctl -p
  ```

---

## 5. HTTP API Gateway

### Gateway does not respond
- **Check**: Confirm the process is running: `cgc api start --port 8000`.
- **Health probe**: `curl http://localhost:8000/health` should return `{"status":"ok"}`.
- **Database errors on `/api/v1/status`**: Run `cgc doctor`—the gateway uses the same database configuration as the CLI.

---

## 6. System Health Check (`doctor`)

To execute a comprehensive diagnostic test of the active environment, run:

```bash
cgc doctor
```

The diagnostics engine performs the following tests:
1. **Python Version**: Confirms interpreter meets version requirements.
2. **Configuration Integrity**: Checks for syntax errors in `config.yaml`.
3. **Database Driver Availability**: Checks imports for Kuzu, FalkorDB, and Neo4j.
4. **Active Connection Health**: Attempts connection transactions to the configured database.
5. **Permissions Audit**: Verifies write capability to target log and database storage directories.