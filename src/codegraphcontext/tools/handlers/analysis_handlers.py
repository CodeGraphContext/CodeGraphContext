# src/codegraphcontext/tools/handlers/analysis_handlers.py
from typing import Any, Dict
from ..code_finder import CodeFinder
from ...utils.debug_log import debug_log
from ...utils.tool_limits import get_tool_result_limit


def find_dead_code(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Tool to find potentially dead code across the entire project."""
    exclude_decorated_with = args.get("exclude_decorated_with", [])
    repo_path = args.get("repo_path")
    try:
        debug_log(f"Finding dead code. repo_path={repo_path}")
        results = code_finder.find_dead_code(exclude_decorated_with=exclude_decorated_with, repo_path=repo_path)

        limit = get_tool_result_limit("find_dead_code")
        unused = results.get("potentially_unused_functions", [])
        truncated = False
        if limit and len(unused) > limit:
            unused = unused[:limit]
            truncated = True

        return {
            "success": True,
            "query_type": "dead_code",
            "results": {**results, "potentially_unused_functions": unused},
            **({"result_limit": limit, "truncated": truncated} if truncated else {}),
        }
    except Exception as e:
        debug_log(f"Error finding dead code: {str(e)}")
        return {"error": f"Failed to find dead code: {str(e)}"}


def calculate_cyclomatic_complexity(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Tool to calculate cyclomatic complexity for a given function."""
    function_name = args.get("function_name")
    path = args.get("path")
    repo_path = args.get("repo_path")

    try:
        debug_log(f"Calculating cyclomatic complexity for function: {function_name}, repo_path={repo_path}")
        results = code_finder.get_cyclomatic_complexity(function_name, path, repo_path=repo_path)

        response = {
            "success": True,
            "function_name": function_name,
            "results": results
        }
        if path:
            response["path"] = path

        return response
    except Exception as e:
        debug_log(f"Error calculating cyclomatic complexity: {str(e)}")
        return {"error": f"Failed to calculate cyclomatic complexity: {str(e)}"}


def find_most_complex_functions(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Tool to find the most complex functions."""
    limit = get_tool_result_limit("find_most_complex_functions", default=args.get("limit", 10))
    repo_path = args.get("repo_path")
    try:
        debug_log(f"Finding the top {limit} most complex functions. repo_path={repo_path}")
        results = code_finder.find_most_complex_functions(limit, repo_path=repo_path)
        return {
            "success": True,
            "limit": limit,
            "results": results
        }
    except Exception as e:
        debug_log(f"Error finding most complex functions: {str(e)}")
        return {"error": f"Failed to find most complex functions: {str(e)}"}


def analyze_code_relationships(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Tool to analyze code relationships"""
    query_type = args.get("query_type")
    target = args.get("target")
    context = args.get("context")
    repo_path = args.get("repo_path")

    if not query_type or not target:
        return {
            "error": "Both 'query_type' and 'target' are required",
            "supported_query_types": [
                "find_callers", "find_callees", "find_all_callers", "find_all_callees", "find_importers", "who_modifies",
                "class_hierarchy", "overrides", "dead_code", "call_chain",
                "module_deps", "variable_scope", "find_complexity", "find_functions_by_argument", "find_functions_by_decorator"
            ]
        }

    try:
        depth = args.get("depth")
        if depth is not None:
            try:
                depth = max(1, min(int(depth), 20))
            except (TypeError, ValueError):
                return {"error": f"Invalid 'depth' value: {depth!r}. Must be an integer between 1 and 20."}
        debug_log(f"Analyzing relationships: {query_type} for {target}, repo_path={repo_path}, depth={depth}")
        results = code_finder.analyze_code_relationships(query_type, target, context, repo_path=repo_path, depth=depth)

        # Apply per-query-type limit (falls back to tool-level limit)
        limit = get_tool_result_limit(query_type) or get_tool_result_limit("analyze_code_relationships")
        truncated = False
        if limit and isinstance(results, list) and len(results) > limit:
            results = results[:limit]
            truncated = True

        response = {
            "success": True, "query_type": query_type, "target": target,
            "context": context, "results": results,
        }
        if truncated:
            response["result_limit"] = limit
            response["truncated"] = True
        return response

    except Exception as e:
        debug_log(f"Error analyzing relationships: {str(e)}")
        return {"error": f"Failed to analyze relationships: {str(e)}"}


def find_code(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Tool to find relevant code snippets"""
    query = args.get("query")
    DEFAULT_EDIT_DISTANCE = 2
    DEFAULT_FUZZY_SEARCH = False

    fuzzy_search = args.get("fuzzy_search", DEFAULT_FUZZY_SEARCH)
    edit_distance = args.get("edit_distance", DEFAULT_EDIT_DISTANCE)
    repo_path = args.get("repo_path")

    if fuzzy_search:
        # For Lucene backends the replace('_', ' ') improves token splitting.
        # For portable (Kùzu/FalkorDB) backends _find_by_name_fuzzy_portable
        # handles normalisation internally, so we leave the query as-is here.
        pass  # transformation deferred to find_related_code / _find_by_name_fuzzy_portable

    try:
        debug_log(f"Finding code for query: {query} with fuzzy_search={fuzzy_search}, edit_distance={edit_distance}, repo_path={repo_path}")
        results = code_finder.find_related_code(query, fuzzy_search, edit_distance, repo_path=repo_path)

        limit = get_tool_result_limit("find_code")
        ranked = results.get("ranked_results", [])
        truncated = False
        if limit and len(ranked) > limit:
            ranked = ranked[:limit]
            truncated = True

        response = {"success": True, "query": query, "results": {**results, "ranked_results": ranked}}
        if truncated:
            response["result_limit"] = limit
            response["truncated"] = True
        return response

    except Exception as e:
        debug_log(f"Error finding code: {str(e)}")
        return {"error": f"Failed to find code: {str(e)}"}


# ── Spring-aware handlers (#887 / #889) ───────────────────────────────────────

def find_java_spring_endpoints(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Return all Spring HTTP endpoint functions, optionally filtered by method or path."""
    http_method = args.get("http_method")
    path_pattern = args.get("path_pattern")
    repo_path = args.get("repo_path")

    conditions = ["fn.http_method IS NOT NULL"]
    params: Dict[str, Any] = {}

    if http_method:
        conditions.append("fn.http_method = $http_method")
        params["http_method"] = http_method.upper()

    if path_pattern:
        conditions.append("fn.http_path CONTAINS $path_pattern")
        params["path_pattern"] = path_pattern

    if repo_path:
        conditions.append("fn.path CONTAINS $repo_path")
        params["repo_path"] = repo_path

    where_clause = " AND ".join(conditions)
    query = f"""
        MATCH (fn:Function)
        WHERE {where_clause}
        RETURN fn.http_method AS method, fn.http_path AS path,
               fn.name AS handler, fn.path AS file, fn.line_number AS line_number
        ORDER BY fn.http_path, fn.http_method
        LIMIT 100
    """

    try:
        with code_finder.driver.session() as session:
            result = session.run(query, **params)
            rows = [dict(r) for r in result]
        return {"success": True, "endpoints": rows, "count": len(rows)}
    except Exception as exc:
        debug_log(f"Error finding Spring endpoints: {exc}")
        return {"error": str(exc)}


def find_java_spring_beans(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Return Spring bean classes, optionally filtered by stereotype."""
    stereotype = args.get("stereotype")
    repo_path = args.get("repo_path")

    conditions = ["c.spring_stereotype IS NOT NULL"]
    params: Dict[str, Any] = {}

    if stereotype:
        conditions.append("c.spring_stereotype = $stereotype")
        params["stereotype"] = stereotype.upper()

    if repo_path:
        conditions.append("c.path CONTAINS $repo_path")
        params["repo_path"] = repo_path

    where_clause = " AND ".join(conditions)
    query = f"""
        MATCH (c:Class)
        WHERE {where_clause}
        OPTIONAL MATCH ()-[:INJECTS]->(c)
        WITH c, count(*) AS injection_count
        RETURN c.name AS name, c.spring_stereotype AS stereotype,
               c.path AS file, c.line_number AS line_number, injection_count
        ORDER BY stereotype, name
        LIMIT 100
    """

    try:
        with code_finder.driver.session() as session:
            result = session.run(query, **params)
            rows = [dict(r) for r in result]
        return {"success": True, "beans": rows, "count": len(rows)}
    except Exception as exc:
        debug_log(f"Error finding Spring beans: {exc}")
        return {"error": str(exc)}


def find_datasource_nodes(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Return Datasource nodes and their tables / key-patterns from the code graph (#843)."""
    kind = args.get("kind")
    name_filter = args.get("name")
    include_columns = args.get("include_columns", False)

    ds_conditions = []
    params: Dict[str, Any] = {}

    if kind:
        ds_conditions.append("d.kind = $kind")
        params["kind"] = kind

    if name_filter:
        ds_conditions.append("d.name CONTAINS $name_filter")
        params["name_filter"] = name_filter

    where_clause = ("WHERE " + " AND ".join(ds_conditions)) if ds_conditions else ""

    # Base datasource + table query
    table_query = f"""
        MATCH (d:Datasource)
        {where_clause}
        OPTIONAL MATCH (tbl:DbTable)-[:STORED_IN]->(d)
        RETURN d.name AS datasource, d.kind AS kind, d.host AS host, d.env AS env,
               collect(tbl.fqn) AS tables
        ORDER BY d.kind, d.name
    """

    # Redis key patterns
    kp_conditions = list(ds_conditions)
    kp_conditions.append("d.kind = 'redis'")
    kp_where = ("WHERE " + " AND ".join(kp_conditions)) if kp_conditions else "WHERE d.kind = 'redis'"
    kp_query = f"""
        MATCH (d:Datasource)
        {kp_where}
        OPTIONAL MATCH (kp:RedisKeyPattern)-[:STORED_IN]->(d)
        RETURN d.name AS datasource,
               collect({{pattern: kp.pattern, key_type: kp.key_type, count: kp.count}}) AS key_patterns
    """

    try:
        with code_finder.driver.session() as session:
            ds_rows = [dict(r) for r in session.run(table_query, **params)]

        redis_kp: Dict[str, Any] = {}
        try:
            with code_finder.driver.session() as session:
                for r in session.run(kp_query, **params):
                    redis_kp[r["datasource"]] = r["key_patterns"]
        except Exception:
            pass  # Redis key-pattern query is best-effort

        # Optionally attach columns
        columns_by_table: Dict[str, Any] = {}
        if include_columns:
            col_query = f"""
                MATCH (d:Datasource) {where_clause}
                MATCH (tbl:DbTable)-[:STORED_IN]->(d)
                MATCH (tbl)-[:HAS_COLUMN]->(col:DbColumn)
                RETURN tbl.fqn AS table_fqn, col.name AS col_name, col.type AS col_type,
                       col.nullable AS nullable, col.is_primary_key AS is_pk
                ORDER BY table_fqn, col_name
            """
            try:
                with code_finder.driver.session() as session:
                    for r in session.run(col_query, **params):
                        fqn = r["table_fqn"]
                        columns_by_table.setdefault(fqn, []).append({
                            "name": r["col_name"],
                            "type": r["col_type"],
                            "nullable": r["nullable"],
                            "is_primary_key": r["is_pk"],
                        })
            except Exception:
                pass

        # Merge into response
        for row in ds_rows:
            ds_name = row["datasource"]
            if ds_name in redis_kp:
                row["key_patterns"] = redis_kp[ds_name]
            if include_columns:
                for tbl_fqn in row.get("tables", []):
                    if tbl_fqn in columns_by_table:
                        row.setdefault("columns", {})[tbl_fqn] = columns_by_table[tbl_fqn]

        return {"success": True, "datasources": ds_rows, "count": len(ds_rows)}
    except Exception as exc:
        debug_log(f"Error finding datasource nodes: {exc}")
        return {"error": str(exc)}

