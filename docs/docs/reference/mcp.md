# MCP workflows and result interpretation

CodeGraphContext's MCP server is an interface to the same Python package used
by the CLI. It accepts tool calls, schedules indexing jobs, and delegates
parsing, graph writes and queries to shared components. It is not a CSV model
training or forecasting service. Source repositories and portable graph
bundles are its primary inputs.

## Discover the installed contract

Use `tools/list` on the running server. The [generated catalog](mcp-catalog.md)
is rebuilt from the complete source registry on every documentation build and
shows the source package version, all tools, every input property, required
arguments, defaults, enums and nested constraints. It replaces manually
maintained tool counts and old version labels. The connected server remains
authoritative for its installed version and `disabledTools` configuration.

See [MCP setup](../getting-started/mcp-setup.md) for client configuration and
[operating notes](mcp-operating-notes.md) for backend, memory, offline and
lifecycle limitations.

## Index, wait, query, watch

1. Start the server with `cgc start` from your workspace. Verify the actual
   backend in server diagnostics; a requested engine can fall back.
2. Discover `tools/list` and use its exact argument names.
3. Call `add_code_to_graph` with `repo_path`. A job ID means accepted work,
   not completed indexing.
4. Poll `check_job_status` with that ID until completed or failed. Inspect
   `errors`, `error_type` and `traceback` on failure. Jobs are held in memory;
   they are not durable across server restarts.
5. Call `find_code`, then `analyze_code_relationships`, with an explicit
   `repo_path` when multiple repositories have matching symbol names.
6. Call `watch_directory` with `repo_path` for ongoing updates. Allow for the
   two-second debounce. Check actual query convergence after edits.
7. Call `unwatch_directory` before managing the store externally. Its successful
   result is a message; it does not promise a `success` boolean.

Example tool arguments (MCP clients supply the JSON-RPC envelope):

```json
{"name":"add_code_to_graph","arguments":{"repo_path":"/work/demo"}}
```

```json
{"name":"check_job_status","arguments":{"job_id":"<returned job_id>"}}
```

```json
{"name":"analyze_code_relationships","arguments":{"query_type":"call_chain","target":"entry->normalize","context":"4","repo_path":"/work/demo"}}
```

Check returned path rows against source. An echoed target or a successful empty
collection is not proof that the expected path was found. Results can carry
truncation and result-limit metadata. Backend errors and input errors must be
treated as failures, including on older versions that wrap an inner error in
an outer success object.

## Relationship analysis

The generated schema enumerates all supported modes. `context` here is
query-specific: for a call chain it is a depth string; for other modes it can
be a class/module disambiguator. It is not a database-context switch.

| Mode family | Target and interpretation |
| --- | --- |
| Direct callers/callees | A symbol name; inspect returned paths and source lines. |
| Transitive callers/callees | A symbol name plus bounded `depth`; recursive queries require more memory. |
| Call chain | `start_function->end_function`; results contain ordered functions and call-site data. |
| Class hierarchy/overrides | A class or method with its class context. |
| Importers/module dependencies | A module name, with repository scope when needed. |
| Argument/decorator lookup | Stored argument/decorator text; decorators use forms such as `@route`. Exact annotation membership differs from dead-code substring exclusions. |
| `who_modifies` | Legacy name for stored variable bindings and their containing scopes. It does not perform general write-site, alias or dataflow analysis. |
| Complexity | Stored per-function scores and rankings; inspect the language's decision model. |
| Dead code | A heuristic candidate list with confidence/reason, not permission to delete a function. Dynamic/framework/external uses can be missing. |

## Other tool families

- **Jobs and lifecycle:** `list_jobs`, `list_watched_paths`,
  `list_indexed_repositories`, `delete_repository`. Deletion is destructive,
  requires explicit server opt-in, and should be scoped to the intended repo.
- **Dependencies and portability:** `add_package_to_graph`, `load_bundle`,
  `search_registry_bundles`. Package discovery depends on the language resolver
  and installed tooling. A registry search can legitimately return no match.
  Test a known bundle identifier before claiming registry download success.
- **Contexts:** `discover_codegraph_contexts`, `switch_context`, `list_graphs`.
  `repo_path` filters data in the active store; it does not select another
  store. `list_graphs` can return an explicit unsupported message on a
  single-graph engine. Context switching is blocked while indexing is active.
- **Reports and visualization:** `get_repository_stats`, `generate_report`,
  `visualize_graph_query`. A generated Playground URL does not establish that
  a visualization server is running. Reports inherit stored graph omissions
  and metric limitations; report output paths obey the root policy.
- **Java and datasources:** `find_java_spring_endpoints`,
  `find_java_spring_beans`, `find_datasource_nodes`. These query stored graph
  metadata. They do not establish live MySQL/Cassandra/Redis connectivity.
  Spring query rows have a cap and expose truncation metadata. The current
  parser uses one route literal per mapping; array/composed-annotation and
  general dependency-injection semantics are not complete.
- **Architecture:** `simulate_metrics`, `simulate_architectural_change`,
  `analyze_architectural_evolution`. Metrics are implementation-defined.
  Simulations use in-memory graph copies. Inspect mutation match/change counts;
  missing or ambiguous references need explicit IDs. Use `switch_context`
  explicitly before a simulation rather than relying on an ignored optional
  `context` argument in older versions. Evolution requires a real Git history;
  commit counts do not establish merge/churn semantics for every workflow.

## Errors and output size

Current input schemas are the client contract. Missing required fields,
incorrect types and unknown enum values must be corrected before retrying.
MCP tool failures use `isError`; JSON-RPC parsing/request failures are a
separate protocol layer. Older releases have transport-specific envelopes,
so inspect error payloads as well as the outer status.

The serialized-budget fix in [PR #1836](https://github.com/CodeGraphContext/CodeGraphContext/pull/1836) makes `MAX_PROMPT_CHARS` include its wrapper and escaping. Earlier versions can exceed the configured maximum. `MAX_TOOL_RESPONSE_TOKENS`
uses a four-characters-per-token approximation; it is not an exact tokenizer
budget. The stricter nonzero value wins. A truncated preview is not the full
result; narrow the query or increase the configured budget. Optional GCF
encoding applies to stdio, while HTTP returns JSON. Size savings vary with
response shape; no fixed token reduction or model-accuracy benefit is implied.
