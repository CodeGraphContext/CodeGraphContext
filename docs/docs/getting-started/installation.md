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

=== "Option A: KùzuDB (Recommended & Default)"
    
    **Platforms:** Linux, macOS, Windows (WSL & Native).

    **KùzuDB** is an embedded, lightweight graph database written in C++. It is the default for CodeGraphContext because it is extremely fast and requires no external services.
    *   **Pros:** Requires zero configuration. Runs automatically in-memory or on-disk. No Docker needed.
    *   **Cons:** No built-in Interactive Browser (unlike Neo4j). Use `cgc visualize` for graph views.

    *This is the default out-of-the-box experience. You don't need to do anything else!*

=== "Option B: Neo4j (Enterprise / Visual)"

    **Platforms:** Windows, macOS, Linux, Docker.

    Neo4j is the industry-standard enterprise graph database.
    *   **Pros:** Powerful web-based Graph Browser (`localhost:7474`). Handles massive codebases perfectly.
    *   **Cons:** Heavier resource usage. Requires Docker or a separate service running in the background.

    1.  **Configure environment for Neo4j:**
        Create a `.env` file or export `CGC_GRAPH_BACKEND=neo4j` and `NEO4J_URI=bolt://localhost:7687` along with `NEO4J_USER` and `NEO4J_PASSWORD`.
    2.  **Start Neo4j via Docker:**
        ```bash
        docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
        ```

---

## Step 3: Verify Installation

Let's make sure everything is talking to each other. Run the "Doctor" command (coming soon) or check the CLI help:

```bash
cgc --help
```

You should see all the commands available for CodeGraphContext.

---

## Step 4: Configure AI Assistant (For MCP Users)

If you plan to use CodeGraphContext with **Cursor**, **Claude**, **Windsurf**, or **Kiro**, you must configure the MCP server.

1.  **Understand MCP Integration:**
    *   CodeGraphContext runs as an MCP server. This means it provides "Tools" to your LLM.
    *   To install it in Claude Desktop, for example, add it to your `claude_desktop_config.json`:
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

2.  **Using cursor:**
    *   Go to Cursor Settings > Features > MCP.
    *   Add a new server: type `command`, name it `CodeGraphContext`, and command `cgc mcp`.

3.  **Refresh your AI Tool:**
    *   Restart your IDE / Claude Desktop.
    *   Verify that tools like `analyze_code_relationships` or `find_code` are now available for the AI to use.
