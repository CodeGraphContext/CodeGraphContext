from typing import Dict, Any, List
from ...utils.debug_log import debug_log


def analyze_performance(code_finder, **args) -> Dict[str, Any]:
    """Analyze code performance including complexity, bottlenecks, and optimization opportunities."""
    function_name = args.get("function_name")
    repo_path = args.get("repo_path")

    try:
        if function_name:
            query = f"""
            MATCH (f:Function {{name: '{function_name}'}})
            OPTIONAL MATCH (f)-[:DEFINED_IN]->(file:File)
            RETURN f.name as name, f.cyclomatic_complexity as complexity, 
                   f.start_line as start_line, f.end_line as end_line,
                   file.path as path
            """
        else:
            if repo_path:
                query = f"""
                MATCH (f:Function)-[:DEFINED_IN]->(file:File)
                WHERE file.path CONTAINS '{repo_path}'
                RETURN f.name as name, f.cyclomatic_complexity as complexity,
                       f.start_line as start_line, f.end_line as end_line,
                       file.path as path
                ORDER BY f.cyclomatic_complexity DESC
                LIMIT 20
                """
            else:
                query = """
                MATCH (f:Function)
                WHERE f.cyclomatic_complexity IS NOT NULL
                RETURN f.name as name, f.cyclomatic_complexity as complexity,
                       f.start_line as start_line, f.end_line as end_line,
                       f.path as path
                ORDER BY f.cyclomatic_complexity DESC
                LIMIT 20
                """

        results = code_finder.execute_cypher_query(query)

        if not results.get("success"):
            return {"error": "Failed to analyze performance"}

        functions = results.get("results", [])

        metrics = {
            "total_functions": len(functions),
            "high_complexity": len(
                [f for f in functions if f.get("complexity", 0) > 10]
            ),
            "medium_complexity": len(
                [f for f in functions if 5 <= f.get("complexity", 0) <= 10]
            ),
            "low_complexity": len([f for f in functions if f.get("complexity", 0) < 5]),
        }

        suggestions = _generate_performance_suggestions(functions)

        result = {
            "success": True,
            "metrics": metrics,
            "functions": functions[:20],
            "optimization_suggestions": suggestions,
        }

        debug_log(
            f"Performance analysis completed: {metrics['total_functions']} functions analyzed"
        )

        return result

    except Exception as e:
        debug_log(f"Error during performance analysis: {str(e)}")
        return {"error": f"Failed to analyze performance: {str(e)}"}


def find_performance_bottlenecks(code_finder, **args) -> Dict[str, Any]:
    """Identify performance bottlenecks in the codebase."""
    limit = args.get("limit", 10)

    try:
        query = f"""
        MATCH (f:Function)
        WHERE f.cyclomatic_complexity IS NOT NULL
        WITH f, f.cyclomatic_complexity as complexity
        ORDER BY complexity DESC
        LIMIT {limit}
        OPTIONAL MATCH (f)-[:DEFINED_IN]->(file:File)
        RETURN f.name as name, complexity, 
               f.start_line as start_line, f.end_line as end_line,
               file.path as path
        """

        results = code_finder.execute_cypher_query(query)

        if not results.get("success"):
            return {"error": "Failed to find performance bottlenecks"}

        bottlenecks = []
        for func in results.get("results", []):
            complexity = func.get("complexity", 0)
            bottleneck = {
                "function": func.get("name"),
                "file": func.get("path"),
                "line": func.get("start_line"),
                "cyclomatic_complexity": complexity,
                "severity": _get_bottleneck_severity(complexity),
                "recommendation": _get_optimization_recommendation(complexity),
            }
            bottlenecks.append(bottleneck)

        result = {
            "success": True,
            "bottlenecks_count": len(bottlenecks),
            "bottlenecks": bottlenecks,
        }

        debug_log(f"Found {len(bottlenecks)} performance bottlenecks")

        return result

    except Exception as e:
        debug_log(f"Error finding performance bottlenecks: {str(e)}")
        return {"error": f"Failed to find bottlenecks: {str(e)}"}


def _generate_performance_suggestions(functions: List[Dict[str, Any]]) -> List[str]:
    """Generate performance optimization suggestions."""
    suggestions = []

    high_complexity = [f for f in functions if f.get("complexity", 0) > 15]
    if high_complexity:
        suggestions.append(
            f"Found {len(high_complexity)} functions with very high complexity (>15). "
            "Consider breaking them into smaller functions."
        )

    medium_complexity = [f for f in functions if 10 <= f.get("complexity", 0) <= 15]
    if medium_complexity:
        suggestions.append(
            f"Found {len(medium_complexity)} functions with high complexity (10-15). "
            "Review for potential refactoring opportunities."
        )

    avg_complexity = (
        sum(f.get("complexity", 0) for f in functions) / len(functions)
        if functions
        else 0
    )
    if avg_complexity > 8:
        suggestions.append(
            f"Average complexity is {avg_complexity:.2f}. Consider simplifying complex functions."
        )

    suggestions.append(
        "Use memoization for expensive function calls with repeated inputs."
    )
    suggestions.append(
        "Consider using caching mechanisms for frequently accessed data."
    )
    suggestions.append("Optimize database queries by adding proper indexes.")

    return suggestions


def _get_bottleneck_severity(complexity: int) -> str:
    """Get severity level for a bottleneck."""
    if complexity > 20:
        return "critical"
    elif complexity > 15:
        return "high"
    elif complexity > 10:
        return "medium"
    else:
        return "low"


def _get_optimization_recommendation(complexity: int) -> str:
    """Get optimization recommendation based on complexity."""
    if complexity > 20:
        return "Critical: Break this function into smaller, testable functions."
    elif complexity > 15:
        return "High: Consider refactoring to reduce branching and nesting."
    elif complexity > 10:
        return "Medium: Review logic flow and simplify conditional statements."
    else:
        return "Low: Maintain current structure, consider minor optimizations."
