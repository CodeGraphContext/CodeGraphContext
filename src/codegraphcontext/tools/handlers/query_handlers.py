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
    """Tool to generate a visualization URL (Neo4j URL or FalkorDB HTML file)."""
    cypher_query = args.get("cypher_query")
    if not cypher_query:
        return {"error": "Cypher query cannot be empty."}

    # Check DB Type: FalkorDBManager vs DatabaseManager
    is_falkor = "FalkorDB" in db_manager.__class__.__name__

    if is_falkor:
        try:
            data_nodes = []
            data_edges = []
            seen_nodes = set()

            with db_manager.get_driver().session() as session:
                result = session.run(cypher_query)
                for record in result:
                    # Iterate all values in the record to find Nodes and Relationships
                    # record is a FalkorDBRecord (dict-like), values() works
                    for val in record.values():
                        # Process Node
                        if hasattr(val, 'labels') and hasattr(val, 'id'):
                            nid = val.id
                            if nid not in seen_nodes:
                                seen_nodes.add(nid)
                                lbl = list(val.labels)[0] if val.labels else "Node"
                                props = getattr(val, 'properties', {}) or {}
                                name = props.get('name', str(nid))
                                
                                color = "#97c2fc"
                                if "Repository" in val.labels: color = "#ffb3ba"
                                elif "File" in val.labels: color = "#baffc9"
                                elif "Class" in val.labels: color = "#bae1ff"
                                elif "Function" in val.labels: color = "#ffffba"
                                
                                data_nodes.append({
                                    "id": nid, "label": name, "group": lbl, 
                                    "title": str(props), "color": color
                                })
                        
                        # Process Relationship
                        src = getattr(val, 'src_node', None)
                        if src is None: src = getattr(val, 'start_node', None)
                        
                        dst = getattr(val, 'dest_node', None)
                        if dst is None: dst = getattr(val, 'end_node', None)

                        if src is not None and dst is not None:
                            lbl = getattr(val, 'relation', None) or getattr(val, 'type', 'REL')
                            data_edges.append({
                                "from": src,
                                "to": dst,
                                "label": lbl,
                                "arrows": "to"
                            })

            # Generate HTML
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <title>CodeGraphContext Visualization</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style type="text/css">
    #mynetwork {{ width: 100%; height: 100vh; border: 1px solid lightgray; }}
  </style>
</head>
<body>
  <div id="mynetwork"></div>
  <script type="text/javascript">
    var nodes = new vis.DataSet({json.dumps(data_nodes)});
    var edges = new vis.DataSet({json.dumps(data_edges)});
    var container = document.getElementById('mynetwork');
    var data = {{ nodes: nodes, edges: edges }};
    var options = {{
        nodes: {{ shape: 'dot', size: 16 }},
        physics: {{ stabilization: false }},
        layout: {{ improvedLayout: false }}
    }};
    var network = new vis.Network(container, data, options);
  </script>
</body>
</html>
"""
            filename = f"codegraph_viz.html"
            out_path = Path(os.getcwd()) / filename
            with open(out_path, "w") as f:
                f.write(html_content)
            
            return {
                "success": True,
                "visualization_url": f"file://{out_path}",
                "message": f"Visualization generated at {out_path}. Open this file in your browser."
            }

        except Exception as e:
            debug_log(f"Error generating FalkorDB visualization: {str(e)}")
            return {"error": f"Failed to generate visualization: {str(e)}"}

    else:
        # Neo4j fallback
        try:
            encoded_query = urllib.parse.quote(cypher_query)
            visualization_url = f"http://localhost:7474/browser/?cmd=edit&arg={encoded_query}"
            
            return {
                "success": True,
                "visualization_url": visualization_url,
                "message": "Open the URL in your browser to visualize the graph query. The query will be pre-filled for editing."
            }
        except Exception as e:
            debug_log(f"Error generating visualization URL: {str(e)}")
            return {"error": f"Failed to generate visualization URL: {str(e)}"}
