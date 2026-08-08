# CodeGraphContext Troubleshooting Guide

**Note:** If you use **FalkorDB** or **KuzuDB** as your backend, you may not need Neo4j at all—skip Neo4j-specific setup and configure `DEFAULT_DATABASE` and the corresponding connection settings for your chosen engine instead.

Use this checklist whenever `cgc neo4j setup` or `cgc mcp start` doesn’t behave as expected. It keeps the happy path short, but includes the fallback steps when something goes wrong.

## 1. Prerequisites at a glance

- **Windows + PowerShell** commands below assume the `py` launcher. Adapt to `python3` if you’re on macOS/Linux.
- **Python 3.10+** (3.12+ recommended for FalkorDB Lite). Run `py -3.11 --version` (or `python3 --version` on macOS/Linux) to confirm.
- **Git** for cloning the repository.
- **Docker Desktop** installed *and running* before you launch `cgc neo4j setup` if you want the wizard to spin up a local Neo4j for you.
- **Neo4j account** (only required if you prefer Neo4j AuraDB instead of Docker).

> **Tip:** If Docker isn’t running, the setup wizard will fail when it tries to install Neo4j locally.

## 2. Create and activate a virtual environment

From the repository root (`CodeGraphContext/`):

```powershell
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
```

- On Windows, Neo4j driver 6.x can crash with `AttributeError: socket.EAI_ADDRFAMILY`. If you see that, run:
  ```powershell
  .\venv\Scripts\python.exe -m pip install "neo4j<6"
  ```

## 3. Run the Neo4j setup wizard (preferred)

Launch the wizard:

```powershell
.\venv\Scripts\cgc.exe neo4j setup
```

What happens next:

- The wizard checks for Docker. If it’s running, it can auto-provision a local Neo4j instance for you.
- Alternatively, you can supply credentials for an existing Neo4j AuraDB database.
- At the end, it generates:
  - `mcp.json` in your project directory (stores the MCP server command + env vars).
  - `~/.codegraphcontext/.env` containing `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`.

Make sure the Docker container (or remote Neo4j) is still running before you start the server.

## 4. Start the MCP server

Once the wizard completes successfully:

```powershell
.\venv\Scripts\cgc.exe mcp start
```

Expected output includes:

```text
Starting CodeGraphContext Server...
...
MCP Server is running. Waiting for requests...
```

If you instead see:

```text
Configuration Error: Neo4j credentials must be set via environment variables
```

then either no credentials were saved, or the wizard was skipped—see the manual alternative below.

## 5. Manual credential setup (fallback)

If you prefer not to use the wizard or need to fix a broken configuration:

1. Create a `mcp.json` (or edit the one that exists) in the repository root:

   ```json
   {
     "mcpServers": {
       "CodeGraphContext": {
         "command": "cgc",
         "args": ["mcp", "start"],
         "env": {
           "NEO4J_URI": "neo4j+s://YOUR-HOSTNAME:7687",
           "NEO4J_USERNAME": "neo4j",
           "NEO4J_PASSWORD": "super-secret-password"
         }
       }
     }
   }
   ```

2. (Optional) Also create `%USERPROFILE%\.codegraphcontext\.env` with the same key/value pairs. The CLI loads that file automatically.

3. Re-run:

   ```powershell
   .\venv\Scripts\cgc.exe mcp start
   ```

## 6. Common issues & fixes

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `Configuration Error: Neo4j credentials must be set…` | `mcp.json`/`.env` missing or empty | Run `cgc neo4j setup` again **with Docker running**, or create the files manually (section 5). |
| `AttributeError: socket.EAI_ADDRFAMILY` | Neo4j 6.x bug on Windows | Install the 5.x driver: `.\venv\Scripts\python.exe -m pip install "neo4j<6"` and retry. |
| Setup wizard fails while pulling Docker image | Docker Desktop not running or Docker permissions missing | Start Docker Desktop, wait for it to report “Running”, then rerun `cgc neo4j setup`. |
| Server exits immediately with no log | Neo4j instance is offline | Check Docker container status or AuraDB dashboard; restart Neo4j and call `cgc mcp start` again. |

## 7. After the server is running

- Keep the virtual environment active whenever you run `cgc` commands.
- Use `pytest` from the same env to run tests:

  ```powershell
  .\venv\Scripts\pytest
  ```

- Front-end website lives under `website/` if you need to run `npm run dev`.

When in doubt, re-run the wizard with Docker active—it regenerates the configuration files without touching your code. Let me know if any section needs clarifying! :)
