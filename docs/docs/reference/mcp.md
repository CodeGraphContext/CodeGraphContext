# MCP Tool Reference

When running the CodeGraphContext (CGC) MCP server, it registers a suite of **25 JSON-RPC tools** that AI assistants can use to analyze and query the code graph.

---

## Code Ingestion & System Control

### `add_code_to_graph`
Indexes a local directory or file into the active database context.
- **Parameters**:
  - `path` (string, required): Absolute filesystem path.
  - `is_dependency` (boolean, optional): Marks the code as an external library.

### `add_package_to_graph`
Discovers, downloads (if needed), and indexes a third-party package.
- **Parameters**:
  - `package_name` (string, required): Name of the package (e.g., `requests`, `express`).
  - `language` (string, required): Language syntax parser (`python`, `javascript`, `typescript`, `java`, `c`, `go`, `ruby`, `php`, `cpp`).
  - `is_dependency` (boolean, optional): Marks the package as an external library (default: true).

### `watch_directory`
Launches a directory watcher for incremental updates.
- **Parameters**:
  - `path` (string, required): Directory path to watch.

### `unwatch_directory`
Stops file monitoring on a folder path.
- **Parameters**:
  - `path` (string, required): Directory path.

### `list_watched_paths`
Lists all directories currently monitored by watchers.

### `delete_repository`
Removes a repository's code structures from the graph.
- **Parameters**:
  - `repo_path` (string, required): Repository path.

### `list_indexed_repositories`
Returns a list of all repositories stored in the active database.

### `get_repository_stats`
Retrieves ingestion metrics (counts of files, functions, classes, modules).
- **Parameters**:
  - `repo_path` (string, optional): Restricts stats to a specific repository.

---

## Background Job Controller

Some operations (like indexing large codebases) execute as background tasks. Use these tools to monitor task states:

### `list_jobs`
Lists all background jobs and their execution states.

### `check_job_status`
Queries progress and logs for a specific job.
- **Parameters**:
  - `job_id` (string, required): Target job ID.

---

## Code Search & Relationship Analysis

### `find_code`
Searches symbol definitions, file names, or source code for keyword matches.
- **Parameters**:
  - `query` (string, required): Target keyword or pattern.
  - `fuzzy_search` (boolean, optional): Enables fuzzy matching.
  - `edit_distance` (number, optional): Levenshtein distance limit (0-2).
  - `repo_path` (string, optional): Restricts search scope.

### `analyze_code_relationships`
The primary tool for traversing structural relationships in the graph.
- **Parameters**:
  - `query_type` (string, required): The traversal type. Must be one of:
    - `find_callers`: Find immediate caller functions.
    - `find_callees`: Find immediate functions called by target.
    - `find_all_callers`: Deep search up the invocation chain.
    - `find_all_callees`: Deep search down the execution path.
    - `find_importers`: Find files importing the target symbol/module.
    - `who_modifies`: Trace variables or structures written to.
    - `class_hierarchy`: Resolves superclass and subclass trees.
    - `overrides`: Finds functions overriding parent methods.
    - `dead_code`: Scans context for unused subroutines.
    - `call_chain`: Traces invocation chains between source and destination.
    - `module_deps`: Identifies dependencies between modules.
    - `variable_scope`: Tracks variable bindings.
    - `find_complexity`: Returns cyclomatic complexity score.
    - `find_functions_by_argument`: Searches for functions declaring target parameter.
    - `find_functions_by_decorator`: Searches for functions decorated with target.
  - `target` (string, required): The identifier name to analyze.
  - `context` (string, optional): Specific file path to resolve target namespace conflicts.
  - `repo_path` (string, optional): Restricts search scope.

### `calculate_cyclomatic_complexity`
Computes the complexity score of a function.
- **Parameters**:
  - `function_name` (string, required): Function identifier.
  - `path` (string, optional): File path containing definition.
  - `repo_path` (string, optional): Restricts search scope.

### `find_most_complex_functions`
Returns methods with the highest cyclomatic complexity scores.
- **Parameters**:
  - `limit` (integer, optional): Maximum rows to return (default: 10).
  - `repo_path` (string, optional): Restricts search scope.

### `find_dead_code`
Scans for unreferenced code declarations.
- **Parameters**:
  - `exclude_decorated_with` (array of strings, optional): Excludes functions carrying specified decorator annotations (e.g., `@app.route`).
  - `repo_path` (string, optional): Restricts search scope.

---

## Workspace Context Management

### `discover_codegraph_contexts`
Scans subdirectories for existing `.codegraphcontext/` directories.
- **Parameters**:
  - `path` (string, optional): Scan root directory.
  - `max_depth` (integer, optional): Folder depth limit (default: 1).

### `switch_context`
Reconnects the MCP session to a different graph database.
- **Parameters**:
  - `context_path` (string, required): Path to the target repository root containing `.codegraphcontext/`.
  - `save` (boolean, optional): Persists configuration mapping (default: true).

---

## Advanced Querying & Reporting

### `execute_cypher_query`
Executes raw Cypher queries directly against the graph database.
- **Parameters**:
  - `cypher_query` (string, required): Cypher statement.

### `visualize_graph_query`
Generates a Neo4j visualization link.
- **Parameters**:
  - `cypher_query` (string, required): Cypher statement to render.

### `generate_report`
Compiles a markdown quality report (`CGC_REPORT.md`).
- **Parameters**:
  - `output_path` (string, optional): Output report path.
  - `include_java` (boolean, optional): Appends Spring endpoints and bean tables.
  - `god_node_limit` (integer, optional): Limit for high fan-in symbol rows.
  - `complexity_limit` (integer, optional): Limit for complex method rows.
  - `cross_module_limit` (integer, optional): Limit for module coupling rows.

---

## Portability & Registries

### `load_bundle`
Imports a portable `.cgc` file, downloading it from the registry if needed.
- **Parameters**:
  - `bundle_name` (string, required): Package name (e.g., `requests`) or file name.
  - `clear_existing` (boolean, optional): Purges active context before loading.

### `search_registry_bundles`
Searches the public CGC bundle server database.
- **Parameters**:
  - `query` (string, optional): Name or description keywords.
  - `unique_only` (boolean, optional): Returns only the latest version of packages.

---

## Frameworks & Datasource Extensions

### `find_java_spring_endpoints`
Searches Spring controller REST mappings.
- **Parameters**:
  - `http_method` (string, optional): Method filter (`GET`, `POST`, etc.).
  - `path_pattern` (string, optional): URL path substring.
  - `repo_path` (string, optional): Restricts search scope.

### `find_java_spring_beans`
Returns registered Spring stereotype beans.
- **Parameters**:
  - `stereotype` (string, optional): Stereotype filter (`SERVICE`, `REPOSITORY`, etc.).
  - `repo_path` (string, optional): Restricts search scope.

### `find_datasource_nodes`
Returns ingested MySQL, Cassandra, or Redis schema nodes.
- **Parameters**:
  - `kind` (string, optional): Datasource kind (`mysql`, `cassandra`, `redis`).
  - `name` (string, optional): Substring filter for names.
  - `include_columns` (boolean, optional): Appends table columns/key patterns (default: false).
