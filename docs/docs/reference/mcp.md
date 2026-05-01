# MCP Tool Reference

When CodeGraphContext is running as an MCP server, it exposes a set of tools that AI agents can use to explore and understand your codebase.

## Code Search & Discovery

### `find_code`
Find relevant code snippets related to a keyword or phrase.
*   **Parameters**: `query` (string), `fuzzy_search` (boolean), `repo_path` (optional).

### `list_indexed_repositories`
List all repositories that are currently available in the graph database.

---

## Relationship Analysis

### `analyze_code_relationships`
The primary tool for deep architectural analysis.
*   **Parameters**:
    *   `query_type`: `find_callers`, `find_callees`, `class_hierarchy`, `module_deps`, `dead_code`, etc.
    *   `target`: The function, class, or module to analyze.
    *   `repo_path`: (Optional) Restrict search to a specific repo.

### `calculate_cyclomatic_complexity`
Get the complexity score of a specific function.
*   **Parameters**: `function_name` (string), `path` (optional).

### `find_most_complex_functions`
Identify technical debt by listing the most complex functions in the codebase.
*   **Parameters**: `limit` (default: 10).

---

## Graph Management

### `add_code_to_graph`
Instruct the agent to index a new directory or file.
*   **Parameters**: `path` (string), `is_dependency` (boolean).

### `watch_directory`
Start monitoring a directory for real-time updates.
*   **Parameters**: `path` (string).

### `switch_context`
Switch the server's focus to a different indexed project.
*   **Parameters**: `context_path` (string).

---

## Advanced Querying

### `execute_cypher_query`
A "power user" tool that allows the AI to run raw Cypher queries against the graph.
*   **Parameters**: `cypher_query` (string).
*   **Schema**: Nodes include `Repository`, `File`, `Module`, `Class`, `Function`. Relationships include `CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS`.

### `visualize_graph_query`
Generates a visualization URL for a specific Cypher query.
*   **Parameters**: `cypher_query` (string).

---

## Bundle Operations

### `load_bundle`
Load a portable `.cgc` bundle into the session.
*   **Parameters**: `bundle_name` (string).

### `search_registry_bundles`
Search for available bundles in the remote registry.
*   **Parameters**: `query` (string).
