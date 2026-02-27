import re
import json
import os
from typing import Dict, Any, List
from pathlib import Path
from ...utils.debug_log import debug_log


def generate_call_graph(db_manager, **args) -> Dict[str, Any]:
    """Generate a call graph visualization."""
    function_name = args.get("function_name")
    depth = args.get("depth", 3)

    try:
        if function_name:
            cypher = f"""
            MATCH (f1:Function {{name: '{function_name}'}})
            CALL apoc.path.subgraphAll(f1, {{
                maxLevel: {depth},
                relationshipFilter: 'CALLS',
                labelFilter: 'Function'
            }})
            YIELD nodes, relationships
            RETURN nodes, relationships
            LIMIT 100
            """
        else:
            cypher = f"""
            MATCH (f1:Function)-[r:CALLS]->(f2:Function)
            RETURN f1, r, f2
            LIMIT 100
            """

        with db_manager.get_driver().session() as session:
            result = session.run(cypher)

            nodes = []
            edges = []
            seen_nodes = set()

            for record in result:
                for val in record.values():
                    if hasattr(val, "labels"):
                        nid = val.id if hasattr(val, "id") else str(val.get("name", ""))
                        if nid not in seen_nodes:
                            seen_nodes.add(nid)
                            props = getattr(val, "properties", {}) or {}
                            nodes.append(
                                {
                                    "id": nid,
                                    "label": props.get("name", "Function"),
                                    "group": "Function",
                                    "color": "#ffffba",
                                }
                            )

                    if hasattr(val, "relation") or hasattr(val, "type"):
                        src = getattr(val, "src_node", None) or getattr(
                            val, "start_node", None
                        )
                        dst = getattr(val, "dest_node", None) or getattr(
                            val, "end_node", None
                        )

                        if src and dst:
                            edges.append(
                                {
                                    "from": src
                                    if isinstance(src, (int, str))
                                    else src.id
                                    if hasattr(src, "id")
                                    else str(src.get("name", "")),
                                    "to": dst
                                    if isinstance(dst, (int, str))
                                    else dst.id
                                    if hasattr(dst, "id")
                                    else str(dst.get("name", "")),
                                    "label": "CALLS",
                                    "arrows": "to",
                                }
                            )

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <title>Call Graph Visualization</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style type="text/css">
    #mynetwork {{ width: 100%; height: 100vh; border: 1px solid lightgray; }}
  </style>
</head>
<body>
  <div id="mynetwork"></div>
  <script type="text/javascript">
    var nodes = new vis.DataSet({json.dumps(nodes)});
    var edges = new vis.DataSet({json.dumps(edges)});
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
            filename = f"call_graph.html"
            out_path = Path(os.getcwd()) / filename
            with open(out_path, "w") as f:
                f.write(html_content)

            debug_log(f"Generated call graph: {out_path}")

            return {
                "success": True,
                "visualization_url": f"file://{out_path}",
                "message": f"Call graph generated at {out_path}",
            }

    except Exception as e:
        debug_log(f"Error generating call graph: {str(e)}")
        return {"error": f"Failed to generate call graph: {str(e)}"}


def generate_class_diagram(db_manager, **args) -> Dict[str, Any]:
    """Generate a class diagram visualization."""
    class_name = args.get("class_name")
    repo_path = args.get("repo_path")

    try:
        if class_name:
            cypher = f"""
            MATCH (c1:Class {{name: '{class_name}'}})
            OPTIONAL MATCH (c1)-[:INHERITS]->(c2:Class)
            OPTIONAL MATCH (c3:Class)-[:INHERITS]->(c1)
            RETURN c1, c2, c3
            LIMIT 100
            """
        else:
            if repo_path:
                cypher = f"""
                MATCH (c:Class)
                WHERE c.path CONTAINS '{repo_path}'
                RETURN c
                LIMIT 100
                """
            else:
                cypher = """
                MATCH (c1:Class)-[:INHERITS]->(c2:Class)
                RETURN c1, c2
                LIMIT 100
                """

        with db_manager.get_driver().session() as session:
            result = session.run(cypher)

            nodes = []
            edges = []
            seen_nodes = set()

            for record in result:
                for val in record.values():
                    if val and hasattr(val, "labels") and "Class" in val.labels:
                        nid = val.id if hasattr(val, "id") else str(val.get("name", ""))
                        if nid not in seen_nodes:
                            seen_nodes.add(nid)
                            props = getattr(val, "properties", {}) or {}
                            nodes.append(
                                {
                                    "id": nid,
                                    "label": props.get("name", "Class"),
                                    "group": "Class",
                                    "color": "#bae1ff",
                                }
                            )

            if class_name:
                cypher = f"""
                MATCH (c1:Class {{name: '{class_name}'}})-[:INHERITS]->(c2:Class)
                RETURN c1, c2
                UNION
                MATCH (c3:Class)-[:INHERITS]->(c4:Class {{name: '{class_name}'}})
                RETURN c3, c4
                """
            else:
                cypher = """
                MATCH (c1:Class)-[:INHERITS]->(c2:Class)
                RETURN c1, c2
                LIMIT 100
                """

            result = session.run(cypher)
            for record in result:
                if record["c1"] and record["c2"]:
                    src_id = (
                        record["c1"].id
                        if hasattr(record["c1"], "id")
                        else str(record["c1"].get("name", ""))
                    )
                    dst_id = (
                        record["c2"].id
                        if hasattr(record["c2"], "id")
                        else str(record["c2"].get("name", ""))
                    )
                    edges.append(
                        {
                            "from": src_id,
                            "to": dst_id,
                            "label": "INHERITS",
                            "arrows": "to",
                            "dashes": True,
                        }
                    )

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <title>Class Diagram Visualization</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style type="text/css">
    #mynetwork {{ width: 100%; height: 100vh; border: 1px solid lightgray; }}
  </style>
</head>
<body>
  <div id="mynetwork"></div>
  <script type="text/javascript">
    var nodes = new vis.DataSet({json.dumps(nodes)});
    var edges = new vis.DataSet({json.dumps(edges)});
    var container = document.getElementById('mynetwork');
    var data = {{ nodes: nodes, edges: edges }};
    var options = {{
        nodes: {{ shape: 'box', size: 20 }},
        physics: {{ stabilization: false }},
        layout: {{ improvedLayout: false }}
    }};
    var network = new vis.Network(container, data, options);
  </script>
</body>
</html>
"""
            filename = f"class_diagram.html"
            out_path = Path(os.getcwd()) / filename
            with open(out_path, "w") as f:
                f.write(html_content)

            debug_log(f"Generated class diagram: {out_path}")

            return {
                "success": True,
                "visualization_url": f"file://{out_path}",
                "message": f"Class diagram generated at {out_path}",
            }

    except Exception as e:
        debug_log(f"Error generating class diagram: {str(e)}")
        return {"error": f"Failed to generate class diagram: {str(e)}"}


def generate_dependency_tree(db_manager, **args) -> Dict[str, Any]:
    """Generate a dependency tree visualization."""
    module_name = args.get("module_name")
    repo_path = args.get("repo_path")

    try:
        if repo_path:
            cypher = f"""
            MATCH (f1:File)-[:IMPORTS]->(f2:File)
            WHERE f1.path CONTAINS '{repo_path}' AND f2.path CONTAINS '{repo_path}'
            RETURN f1, f2
            LIMIT 200
            """
        elif module_name:
            cypher = f"""
            MATCH (f1:File)-[:IMPORTS]->(f2:File)
            WHERE f1.path CONTAINS '{module_name}' OR f2.path CONTAINS '{module_name}'
            RETURN f1, f2
            LIMIT 200
            """
        else:
            cypher = """
            MATCH (f1:File)-[:IMPORTS]->(f2:File)
            RETURN f1, f2
            LIMIT 200
            """

        with db_manager.get_driver().session() as session:
            result = session.run(cypher)

            nodes = []
            edges = []
            seen_nodes = set()

            for record in result:
                for val in record.values():
                    if val and hasattr(val, "labels") and "File" in val.labels:
                        nid = val.id if hasattr(val, "id") else str(val.get("path", ""))
                        if nid not in seen_nodes:
                            seen_nodes.add(nid)
                            props = getattr(val, "properties", {}) or {}
                            nodes.append(
                                {
                                    "id": nid,
                                    "label": props.get(
                                        "name", props.get("path", "File")
                                    ),
                                    "group": "File",
                                    "color": "#baffc9",
                                }
                            )

            result = session.run(cypher)
            for record in result:
                if record["f1"] and record["f2"]:
                    src_id = (
                        record["f1"].id
                        if hasattr(record["f1"], "id")
                        else str(record["f1"].get("path", ""))
                    )
                    dst_id = (
                        record["f2"].id
                        if hasattr(record["f2"], "id")
                        else str(record["f2"].get("path", ""))
                    )
                    edges.append(
                        {
                            "from": src_id,
                            "to": dst_id,
                            "label": "IMPORTS",
                            "arrows": "to",
                        }
                    )

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <title>Dependency Tree Visualization</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style type="text/css">
    #mynetwork {{ width: 100%; height: 100vh; border: 1px solid lightgray; }}
  </style>
</head>
<body>
  <div id="mynetwork"></div>
  <script type="text/javascript">
    var nodes = new vis.DataSet({json.dumps(nodes)});
    var edges = new vis.DataSet({json.dumps(edges)});
    var container = document.getElementById('mynetwork');
    var data = {{ nodes: nodes, edges: edges }};
    var options = {{
        nodes: {{ shape: 'diamond', size: 12 }},
        physics: {{ stabilization: false }},
        layout: {{ hierarchical: {{ direction: 'UD', sortMethod: 'directed' }} }}
    }};
    var network = new vis.Network(container, data, options);
  </script>
</body>
</html>
"""
            filename = f"dependency_tree.html"
            out_path = Path(os.getcwd()) / filename
            with open(out_path, "w") as f:
                f.write(html_content)

            debug_log(f"Generated dependency tree: {out_path}")

            return {
                "success": True,
                "visualization_url": f"file://{out_path}",
                "message": f"Dependency tree generated at {out_path}",
            }

    except Exception as e:
        debug_log(f"Error generating dependency tree: {str(e)}")
        return {"error": f"Failed to generate dependency tree: {str(e)}"}
