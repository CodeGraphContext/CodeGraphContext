# Installation



We have designed the installation to be as automatic as possible.

## Step 1: Install the Package

Open your terminal and run:

```bash
pip install codegraphcontext
```

*Tip: We recommend installing this in a virtual environment (venv) or globally via `pipx`.*

---

## Step 2: Database Setup

CGC requires a graph database backend. Choose **ONE** path below.

=== "Option A: FalkorDB (Recommended for Local)"
    
    **Platforms:** Linux, macOS, WSL.

    !!! warning "Windows Users"
        On Windows? Please Check the **[Windows Setup Guide](../windows_setup.md)** for WSL and FalkorDB/Neo4j compatibility.

    FalkorDB is an embedded, lightweight graph database.
    *   **Pros:** Requires zero configuration. Runs automatically. Persistent storage is managed for you.
    *   **Cons:** No built-in Interactive Browser (unlike Neo4j). Use `cgc visualize` for basic graphs.

    *If you are on Linux/macOS with Python 3.12+, this is the default.*

=== "Option B: Neo4j (Production / Visual)"

    **Platforms:** Windows, All OSs, Docker users.

    Neo4j is the industry-standard graph database.
    *   **Pros:** Powerful web-based Graph Browser (`localhost:7474`). Handles massive codebases better.
    *   **Cons:** Heavier resource usage. Requires Docker or a separate service.

    1.  **Run the setup wizard:**
        ```bash
        cgc neo4j setup
        ```
    2.  **Follow the prompts:**
        
        ??? info "Detailed Setup Steps"
            *   **Select Installation Type**:
                *   `Docker`: Pulls the official image and starts a container on port 7687. (Requires Docker Desktop/Engine).
                *   `Native`: Help you find your local `neo4j-admin` installation.
            *   **Configure Password**:
                *   You will be asked to set a password for the `neo4j` user.
                *   Default suggestion: `codegraphcontext`.
            *   **Start Service**:
                *   The wizard attempts to run `docker run` or `systemctl start neo4j`.

---

## Step 3: Verify Installation

Let's make sure everything is talking to each other. Run the "Doctor" command:

```bash
cgc doctor
```

**What to look for:**

*   ✅ `Database check passed`
*   ✅ `Core dependencies satisfied`

---

## Step 4: Configure AI Assistant (For MCP Users)

If you plan to use CodeGraphContext with **Cursor**, **Claude**, or **VS Code**, you must configure the MCP server.

1.  **Run the MCP wizard:**
    ```bash
    cgc mcp setup
    ```

2.  **What it does:**
    *   🔍 **Asks you to choose** your IDE from a supported list (Cursor, VS Code, Claude, Windsurf, Cline, etc.).
    *   ⚙️ **Updates** the configuration file (e.g., `mcp.json`) to invoke `cgc`.
    *   🔐 **Saves** local database credentials so the AI can connect.

    *Note: We support **any** MCP-compliant client. If your tool isn't listed, simply copy the JSON output from this command and paste it into your tool's config manually.*

3.  **Refresh your AI Tool:**
    *   Click the "Refresh" icon in the MCP/Continue panel.
    *   Verify that `CodeGraphContext` appears in your enabled tools list.
