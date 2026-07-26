# src/codegraphcontext/tools/handlers/query_handlers.py
import urllib.parse
from typing import Any, Dict

try:
    from neo4j.exceptions import CypherSyntaxError
except ImportError:  # neo4j driver not installed (FalkorDB/Kuzu-only setups)
    CypherSyntaxError = type("CypherSyntaxError", (Exception,), {})

from ...utils.cypher_readonly import is_read_only_cypher, read_only_rejection_message
from ...utils.debug_log import debug_log
from ...utils.tool_limits import get_tool_result_limit


def execute_cypher_query(db_manager, **args) -> Dict[str, Any]:
    """
    Tool implementation for executing a read-only Cypher query.

    Write protection uses keyword validation on every backend. Neo4j sessions
    also request READ access mode at the protocol layer.
    """
    cypher_query = args.get("cypher_query")
    if not cypher_query:
        return {"error": "Cypher query cannot be empty."}

    params = args.get("params") or args.get("parameters") or {}
    if not isinstance(params, dict):
        return {"error": "Query parameters must be an object/dictionary."}

    if not is_read_only_cypher(cypher_query):
        return {"error": read_only_rejection_message()}

    backend = getattr(db_manager, "get_backend_type", lambda: "neo4j")()
    session_kwargs: Dict[str, Any] = {}
    if backend == "neo4j":
        session_kwargs["default_access_mode"] = "READ"

    try:
        debug_log(f"Executing Cypher query: {cypher_query}")
        with db_manager.get_driver().session(**session_kwargs) as session:
            # Unpack as kwargs: Neo4j accepts them, and the FalkorDB/Kuzu
            # session shims only accept parameters via **kwargs.
            result = session.run(cypher_query, **params)
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
            "query": cypher_query,
        }
    except Exception as e:
        debug_log(f"Error executing Cypher query: {str(e)}")
        # FalkorDB/Kuzu raise their own exception types for malformed Cypher;
        # surface those as structured syntax errors like the Neo4j path does.
        message = str(e)
        if "syntax" in message.lower() or "parser" in message.lower():
            return {
                "error": "Cypher syntax error.",
                "details": message,
                "query": cypher_query,
            }
        return {
            "error": "An unexpected error occurred while executing the query.",
            "details": message,
        }


def visualize_graph_query(db_manager, **args) -> Dict[str, Any]:
    """Tool to generate a visualization URL for the local Playground UI."""
    cypher_query = args.get("cypher_query")
    if not cypher_query:
        return {"error": "Cypher query cannot be empty."}

    if not is_read_only_cypher(cypher_query):
        return {"error": read_only_rejection_message()}

    try:
        port = 8000
        encoded_query = urllib.parse.quote(cypher_query)
        visualization_url = f"http://localhost:{port}/index.html?cypher_query={encoded_query}"

        return {
            "success": True,
            "visualization_url": visualization_url,
            "message": "Click the URL to visualize this specific query in the Playground UI. (Ensure 'cgc visualize' is running)",
        }
    except Exception as e:
        debug_log(f"Error generating visualization URL: {str(e)}")
        return {"error": f"Failed to generate visualization URL: {str(e)}"}
