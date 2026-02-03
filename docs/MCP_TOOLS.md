# MCP Tools Reference

This document describes the Model Context Protocol (MCP) tools available in CodeGraphContext. These tools are exposed to AI assistants to enable them to interact with your codebase.

## 📋 Tool Categories

1. [Indexing & Management](#indexing--management)
2. [Code Search](#code-search)
3. [Analysis & Quality](#analysis--quality)
4. [Bundle Management](#bundle-management)
5. [Monitoring](#monitoring)
6. [Advanced Querying](#advanced-querying)

---

## Indexing & Management

### `add_code_to_graph`
Performs a one-time scan of a local folder to add its code to the graph. Ideal for libraries or dependencies.
- **Args**: `path` (string), `is_dependency` (boolean)
- **Returns**: Job ID

### `add_package_to_graph`
Add an external package to the graph by discovering its location.
- **Args**: `package_name` (string), `language` (string), `is_dependency` (boolean)
- **Returns**: Job ID
- **Supported Languages**: python, javascript, typescript, java, c, go, ruby, php, cpp

### `list_indexed_repositories`
List all repositories currently indexed in the graph.
- **Args**: None
- **Returns**: List of repositories with paths and stats

### `delete_repository`
Delete a repository from the graph.
- **Args**: `repo_path` (string)
- **Returns**: Success message

### `check_job_status`
Check the status of a background job (indexing, scanning).
- **Args**: `job_id` (string)
- **Returns**: Job status (running, completed, failed) and progress

### `list_jobs`
List all background jobs.
- **Args**: None
- **Returns**: List of all jobs

---

## Code Search

### `find_code`
Find code snippets related to a keyword.
- **Args**: `query` (string), `fuzzy_search` (boolean), `edit_distance` (number)
- **Returns**: Matches with file path, line number, and content

---

## Analysis & Quality

### `analyze_code_relationships`
Analyze relationships between code elements.
- **Args**:
  - `query_type` (enum): `find_callers`, `find_callees`, `class_hierarchy`, `overrides`, etc.
  - `target` (string): Function/class name
  - `context` (string): Optional file path
- **Returns**: List of related elements

### `find_dead_code`
Find potentially unused functions across the codebase.
- **Args**: `exclude_decorated_with` (list of strings)
- **Returns**: List of unused functions

### `calculate_cyclomatic_complexity`
Calculate complexity for a specific function.
- **Args**: `function_name` (string), `path` (string)
- **Returns**: Complexity score

### `find_most_complex_functions`
Find the most complex functions in the codebase.
- **Args**: `limit` (integer)
- **Returns**: List of functions sorted by complexity

### `get_repository_stats`
Get statistics about indexed repositories.
- **Args**: `repo_path` (string, optional)
- **Returns**: Counts of files, functions, classes, modules

---

## Bundle Management

### `load_bundle`
Load a pre-indexed `.cgc` bundle. Can download from registry if not found locally.
- **Args**: `bundle_name` (string), `clear_existing` (boolean)
- **Returns**: Success message and stats

### `search_registry_bundles`
Search for bundles in the registry.
- **Args**: 
  - `query` (string, optional): Search term
  - `unique_only` (boolean): Show only latest version per package
- **Returns**: List of available bundles

---

## Monitoring

### `watch_directory`
Continuously monitor a directory for changes and keep the graph updated.
- **Args**: `path` (string)
- **Returns**: Job ID for initial scan

### `list_watched_paths`
List directories being watched.
- **Args**: None
- **Returns**: List of paths

### `unwatch_directory`
Stop watching a directory.
- **Args**: `path` (string)
- **Returns**: Success message

---

## Advanced Querying

### `execute_cypher_query`
Run a direct read-only Cypher query against the graph.
- **Args**: `cypher_query` (string)
- **Returns**: Raw query results

### `visualize_graph_query`
Generate a URL to visualize query results in Neo4j Browser.
- **Args**: `cypher_query` (string)
- **Returns**: URL
