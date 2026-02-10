# MCP Reference & Natural Language Queries

This page lists all available **MCP Tools** that your AI assistant (Cursor, Claude, VS Code) can use.

When you ask a question in natural language, the AI selects one of these tools behind the scenes.

!!! tip "File Exclusion"
    You can control what gets indexed using `.cgcignore`.
    [**📄 Read the Guide**](cgcignore.md)

## Core Analysis Tools

These are the most commonly used tools for understanding code.

| Tool Name | Description | Natural Language Example |
| :--- | :--- | :--- |
| **`find_code`** | Search for code by name or fuzzy text. | "Where is the `User` class defined?" |
| **`analyze_code_relationships`** | The swiss-army knife for call graphs and dependencies. | "Find all callers of `process_payment`." |
| **`calculate_cyclomatic_complexity`** | Measure function complexity. | "What is the complexity of `main`?" |
| **`find_most_complex_functions`** | List the hardest-to-maintain functions. | "Show me the 5 most complex functions." |
| **`find_dead_code`** | Identify unused functions. | "Find dead code, but ignore `@route`." |

## System & Management

Tools for managing the graph and background jobs.

| Tool Name | Description | Natural Language Example |
| :--- | :--- | :--- |
| **`monitor_directory`** | Start monitoring a folder (Alias: `watch_directory`)| "Watch the `src` folder." |
| **`list_watched_paths`** | See what is being monitored. | "What directories are being watched?" |
| **`unwatch_directory`** | Stop monitoring a folder. | "Stop watching `src`." |
| **`list_indexed_repositories`** | Show what projects are currently indexed. | "What repos are indexed?" |
| **`get_repository_stats`** | Show counts of files, classes, LOC. | "Show stats for the backend repo." |
| **`delete_repository`** | Remove a repo from the graph. | "Remove the frontend repo." |
| **`add_code_to_graph`** | Manually add a specific path. | "Add the `lib` folder." |
| **`add_package_to_graph`** | Index an external library/package. | "Add the `requests` library." |

## Job Control

| Tool Name | Description | Natural Language Example |
| :--- | :--- | :--- |
| **`list_jobs`** | View all background tasks. | "Show me active jobs." |
| **`check_job_status`** | Check if a specific job is done. | "Is job `xyz` finished?" |

## Bundles & Registry

| Tool Name | Description | Natural Language Example |
| :--- | :--- | :--- |
| **`search_registry_bundles`** | Find shared graphs in the cloud. | "Search for a `flask` bundle." |
| **`load_bundle`** | Install a graph bundle. | "Load the `flask` bundle." |

## Advanced Querying

For complex questions that standard tools can't answer.

| Tool Name | Description | Natural Language Example |
| :--- | :--- | :--- |
| **`execute_cypher_query`** | Run a raw read-only database query. | "Find all recursive functions." |
| **`visualize_graph_query`** | Generate a Neo4j Browser link for a query. | "Visualize the class hierarchy of `BaseModel`." |

---

## Example Queries (Cookbook)

For a deep dive into exactly how to phrase questions and what JSON arguments look like, check out the Cookbook.

[📖 View the MCP Cookbook](../cookbook.md)
