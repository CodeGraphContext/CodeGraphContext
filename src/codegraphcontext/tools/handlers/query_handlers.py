import re
import urllib.parse
from typing import Any, Dict
from neo4j.exceptions import CypherSyntaxError
from ...utils.debug_log import debug_log
from ...utils.tool_limits import get_tool_result_limit

_STRING_LITERAL_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.DOTALL)
_COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
_READONLY_START_RE = re.compile(r"^\s*(OPTIONAL\s+MATCH|MATCH|WITH|UNWIND|RETURN)\b", re.IGNORECASE)
_FORBIDDEN_CLAUSE_PATTERNS = [
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bDELETE\b",
    r"\bDETACH\s+DELETE\b",
    r"\bSET\b",
    r"\bREMOVE\b",
    r"\bDROP\b",
    r"\bLOAD\s+CSV\b",
    r"\bFOREACH\b",
    r"\bCALL\b",
    r"\bSTART\b",
    r"\bALTER\b",
    r"\bRENAME\b",
    r"\bGRANT\b",
    r"\bDENY\b",
    r"\bREVOKE\b",
    r"\bTERMINATE\b",
]


def _strip_literals_and_comments(query: str) -> str:
    without_strings = _STRING_LITERAL_RE.sub("", query)
    return _COMMENT_RE.sub("", without_strings)


def _validate_read_only_query(cypher_query: str) -> str | None:
    stripped = _strip_literals_and_comments(cypher_query)
    if ";" in stripped:
        return "Only a single Cypher statement is allowed."
    if not _READONLY_START_RE.search(stripped):
        return (
            "Read-only query must start with MATCH, OPTIONAL MATCH, WITH, "
            "UNWIND, or RETURN."
        )
    for pattern in _FORBIDDEN_CLAUSE_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE):
            return "This tool only supports read-only Cypher queries."
    return None


def execute_cypher_query(db_manager, **args) -> Dict[str, Any]:
    """
    Tool implementation for executing a read-only Cypher query.
    
    Important: Includes a safety check to prevent any database modification
    by disallowing keywords like CREATE, MERGE, DELETE, etc.
    """
    cypher_query = args.get("cypher_query")
    if not cypher_query:
        return {"error": "Cypher query cannot be empty."}

    validation_error = _validate_read_only_query(cypher_query)
    if validation_error:
        return {"error": validation_error}

    try:
        debug_log(f"Executing Cypher query: {cypher_query}")
        with db_manager.get_driver().session() as session:
            result = session.run(cypher_query)
            records = [record.data() for record in result]

            limit = get_tool_result_limit("execute_cypher_query")
            truncated = False
            if limit and len(records) > limit:
                records = records[:limit]
                truncated = True

            response = {
                "success": True,
                "query": cypher_query,
                "record_count": len(records),
                "results": records,
            }
            if truncated:
                response["result_limit"] = limit
                response["truncated"] = True
            return response
    
    except CypherSyntaxError as e:
        debug_log(f"Cypher syntax error: {str(e)}")
        return {
            "error": "Cypher syntax error.",
            "details": str(e),
            "query": cypher_query
        }
    except Exception as e:
        debug_log(f"Error executing Cypher query: {str(e)}")
        return {
            "error": "An unexpected error occurred while executing the query.",
            "details": str(e)
        }

def visualize_graph_query(db_manager, **args) -> Dict[str, Any]:
    """Tool to generate a visualization URL for the local Playground UI."""
    cypher_query = args.get("cypher_query")
    if not cypher_query:
        return {"error": "Cypher query cannot be empty."}

    try:
        # We point to the local server started by 'cgc visualize'
        # By default it runs on port 8000
        port = 8000
        encoded_query = urllib.parse.quote(cypher_query)
        visualization_url = f"http://localhost:{port}/index.html?cypher_query={encoded_query}"
        
        return {
            "success": True,
            "visualization_url": visualization_url,
            "message": "Click the URL to visualize this specific query in the Playground UI. (Ensure 'cgc visualize' is running)"
        }
    except Exception as e:
        debug_log(f"Error generating visualization URL: {str(e)}")
        return {"error": f"Failed to generate visualization URL: {str(e)}"}
