import re
import json
import urllib.parse
from pathlib import Path
import os
from datetime import datetime
from typing import Any, Dict
from neo4j.exceptions import CypherSyntaxError
from ...utils.debug_log import debug_log

def execute_cypher_query(db_manager, **args) -> Dict[str, Any]:
    """
    Tool implementation for executing a read-only Cypher query.
    
    Important: Includes a safety check to prevent any database modification
    by disallowing keywords like CREATE, MERGE, DELETE, etc.
    """
    cypher_query = args.get("cypher_query")
    if not cypher_query:
        return {"error": "Cypher query cannot be empty."}

    # Safety Check: Prevent any write operations to the database.
    # This check first removes all string literals and then checks for forbidden keywords.
    forbidden_keywords = ['CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE', 'DROP', 'CALL apoc']
    
    # Regex to match single or double quoted strings, handling escaped quotes.
    string_literal_pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    
    # Remove all string literals from the query.
    query_without_strings = re.sub(string_literal_pattern, '', cypher_query)
    
    # Now, check for forbidden keywords in the query without strings.
    for keyword in forbidden_keywords:
        if re.search(r'\b' + keyword + r'\b', query_without_strings, re.IGNORECASE):
            return {
                "error": "This tool only supports read-only queries. Prohibited keywords like CREATE, MERGE, DELETE, SET, etc., are not allowed."
            }

    try:
        debug_log(f"Executing Cypher query: {cypher_query}")
        with db_manager.get_driver().session() as session:
            result = session.run(cypher_query)
            # Convert results to a list of dictionaries for clean JSON serialization.
            records = [record.data() for record in result]
            
            return {
                "success": True,
                "query": cypher_query,
                "record_count": len(records),
                "results": records
            }
    
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
