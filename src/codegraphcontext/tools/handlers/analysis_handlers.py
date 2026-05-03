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
        debug_log(f"Analyzing relationships: {query_type} for {target}, repo_path={repo_path}")
        results = code_finder.analyze_code_relationships(query_type, target, context, repo_path=repo_path)

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
