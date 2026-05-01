# MCP Reference & Natural Language Queries

This page lists the **complete MCP tool catalog** for CodeGraphContext **0.4.5** (**21** tools returned by MCP `tools/list`)—every tool your AI assistant (Cursor, Claude, VS Code, and other MCP clients) can invoke.

When you ask a question in natural language, the assistant selects one of these tools behind the scenes.

!!! tip "File exclusion"
    Control what gets indexed with `.cgcignore`.
    [**Read the guide**](cgcignore.md)

## Context management

Use these when the workspace root has no graph, but child projects contain `.codegraphcontext/` folders, or when you need to point the session at a different database.

| Tool name | Description | Natural language example |
| :--- | :--- | :--- |
| **`discover_codegraph_contexts`** | Scan a path (default: server cwd) for child directories that contain `.codegraphcontext/` and an indexed database. | "Find CodeGraphContext projects under this monorepo root." |
| **`switch_context`** | Attach the MCP session to another `.codegraphcontext` database (repo root or `.codegraphcontext/` path); optionally persist the mapping for restarts. | "Use the graph for `./services/api` instead of the parent folder." |

## Core analysis tools

| Tool name | Description | Natural language example |
| :--- | :--- | :--- |
| **`find_code`** | Search for code by name or fuzzy text. | "Where is the `User` class defined?" |
| **`analyze_code_relationships`** | Call graphs, imports, hierarchy, and related queries. | "Find all callers of `process_payment`." |
| **`calculate_cyclomatic_complexity`** | Measure function complexity. | "What is the complexity of `main`?" |
| **`find_most_complex_functions`** | List the most complex functions. | "Show me the five most complex functions." |
| **`find_dead_code`** | Identify unused functions (with optional decorator exclusions). | "Find dead code, but ignore `@route`." |

## Indexing & graph management

| Tool name | Description | Natural language example |
| :--- | :--- | :--- |
| **`add_code_to_graph`** | One-time scan of a local path into the graph. | "Index the `lib` folder." |
| **`add_package_to_graph`** | Resolve and index an external package. | "Add the `requests` package for Python." |
| **`list_indexed_repositories`** | List projects present in the graph. | "What repos are indexed?" |
| **`delete_repository`** | Remove a repository from the graph. | "Remove the frontend repo." |
| **`get_repository_stats`** | File / class / function counts for a repo or the whole graph. | "Show stats for the backend repo." |

## Watching & live updates

| Tool name | Description | Natural language example |
| :--- | :--- | :--- |
| **`watch_directory`** | Initial scan plus continuous file watching to keep the graph updated. | "Watch the `src` directory." |
| **`list_watched_paths`** | List directories currently watched. | "What directories are being watched?" |
| **`unwatch_directory`** | Stop watching a path. | "Stop watching `src`." |

## Job control

| Tool name | Description | Natural language example |
| :--- | :--- | :--- |
| **`list_jobs`** | List background jobs. | "Show active jobs." |
| **`check_job_status`** | Poll a specific job by id. | "Is job `xyz` finished?" |

## Bundles & registry

| Tool name | Description | Natural language example |
| :--- | :--- | :--- |
| **`search_registry_bundles`** | Search shared `.cgc` bundles in the registry. | "Search for a `flask` bundle." |
| **`load_bundle`** | Load a bundle into the current database. | "Load the `flask` bundle." |

## Advanced querying

| Tool name | Description | Natural language example |
| :--- | :--- | :--- |
| **`execute_cypher_query`** | Read-only Cypher against the active backend’s graph view. | "Find all recursive functions." |
| **`visualize_graph_query`** | Produce a Neo4j Browser URL for a query (when applicable to your setup). | "Visualize the class hierarchy of `BaseModel`." |

---

## Example queries (cookbook)

For phrasing patterns and example JSON arguments, see the cookbook.

[View the MCP cookbook](../cookbook.md)
