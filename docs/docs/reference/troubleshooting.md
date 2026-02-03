# Troubleshooting

## Common Issues

### 1. "cgc: command not found"
**Cause:** The folder where `pip` installs scripts is not in your system PATH.
**Fix:**
*   **Linux/Mac:** Add `export PATH="$HOME/.local/bin:$PATH"` to your `.bashrc` or `.zshrc`.
*   **Windows:** Reinstall Python and check "Add to PATH".

### 2. "Connection Refused" (Neo4j)
**Cause:** The Neo4j container is not running.
**Fix:**
```bash
docker start cgc-neo4j
```

### 3. "Import Error: FalkorDB"
**Cause:** You are trying to use FalkorDB on Windows, or heavily outdated Python.
**Fix:** Switch to Neo4j, or upgrade to Python 3.12+ (WSL).

---

## Getting Help

If these didn't solve it, please open an issue on [GitHub](https://github.com/CodeGraphContext/CodeGraphContext/issues) with the output of `cgc doctor`.
