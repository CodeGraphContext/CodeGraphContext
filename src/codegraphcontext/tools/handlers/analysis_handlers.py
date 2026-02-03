from typing import Any, Dict
from ..code_finder import CodeFinder
from ...utils.debug_log import debug_log

def find_dead_code(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Tool to find potentially dead code across the entire project."""
    exclude_decorated_with = args.get("exclude_decorated_with", [])
    try:
        debug_log("Finding dead code.")
        results = code_finder.find_dead_code(exclude_decorated_with=exclude_decorated_with)
        
        return {
            "success": True,
            "query_type": "dead_code",
            "results": results
        }
    except Exception as e:
        debug_log(f"Error finding dead code: {str(e)}")
        return {"error": f"Failed to find dead code: {str(e)}"}

def calculate_cyclomatic_complexity(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Tool to calculate cyclomatic complexity for a given function."""
    function_name = args.get("function_name")
    path = args.get("path")

    try:
        debug_log(f"Calculating cyclomatic complexity for function: {function_name}")
        results = code_finder.get_cyclomatic_complexity(function_name, path)
        
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
    limit = args.get("limit", 10)
    try:
        debug_log(f"Finding the top {limit} most complex functions.")
        results = code_finder.find_most_complex_functions(limit)
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

    if not query_type or not target:
        return {
            "error": "Both 'query_type' and 'target' are required",
            "supported_query_types": [
                "find_callers", "find_callees", "find_importers", "who_modifies",
                "class_hierarchy", "overrides", "dead_code", "call_chain",
                "module_deps", "variable_scope", "find_complexity"
            ]
        }
    
    try:
        debug_log(f"Analyzing relationships: {query_type} for {target}")
        results = code_finder.analyze_code_relationships(query_type, target, context)
        
        return {
            "success": True, "query_type": query_type, "target": target,
            "context": context, "results": results
        }
    
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

    if fuzzy_search:
        # Assuming minimal normalization is fine here if not method available
        query = query.lower().replace("_", " ").strip()
        
    try:
        debug_log(f"Finding code for query: {query} with fuzzy_search={fuzzy_search}, edit_distance={edit_distance}")
        results = code_finder.find_related_code(query, fuzzy_search, edit_distance)

        return {"success": True, "query": query, "results": results}
    
    except Exception as e:
        debug_log(f"Error finding code: {str(e)}")
        return {"error": f"Failed to find code: {str(e)}"}
