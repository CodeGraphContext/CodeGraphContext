import os
import json
import platform
from pathlib import Path

if platform.system() == "Windows":
    raise RuntimeError(
        "CodeGraphContext uses redislite/FalkorDB, which does not support Windows.\n"
        "Please run the project using WSL or Docker."
    )

from redislite import FalkorDB

def generate_visualization():
    db_path = os.path.expanduser('~/.codegraphcontext/falkordb.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    print(f"Reading graph from {db_path}...")
    f = FalkorDB(db_path)
    g = f.select_graph('codegraph')

    # Fetch nodes
    nodes_res = g.query("MATCH (n) RETURN id(n), labels(n)[0], n.name, n.path")
    nodes = []
    for row in nodes_res.result_set:
        node_id, label, name, path = row
        # Format label and name for display
        display_name = name if name else (os.path.basename(path) if path else label)
        nodes.append({
            "id": node_id,
            "label": display_name,
            "group": label,
            "title": f"Type: {label}\nPath: {path}"
        })

    # Fetch relationships
    edges_res = g.query("MATCH (s)-[r]->(t) RETURN id(s), type(r), id(t)")
    edges = []
    for row in edges_res.result_set:
        source, rel_type, target = row
        edges.append({
            "from": source,
            "to": target,
            "label": rel_type,
            "arrows": "to"
        })

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CGC Graph Visualization</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        body {{
            margin: 0;
            padding: 0;
            background-color: #1a1a1a;
            color: #ffffff;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
        }}
        #mynetwork {{
            width: 100vw;
            height: 100vh;
        }}
        .header {{
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 10;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #444;
            pointer-events: none;
        }}
        h1 {{ margin: 0; font-size: 1.5em; color: #00d4ff; }}
        .stats {{ font-size: 0.9em; color: #aaa; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>CodeGraphContext Visualizer</h1>
        <div class="stats">Nodes: {len(nodes)} | Relationships: {len(edges)}</div>
        <div style="font-size: 0.8em; margin-top: 10px; color: #888;">Drag to move | Scroll to zoom</div>
    </div>
    <div id="mynetwork"></div>

    <script type="text/javascript">
        var nodes = new vis.DataSet({json.dumps(nodes)});
        var edges = new vis.DataSet({json.dumps(edges)});

        var container = document.getElementById('mynetwork');
        var data = {{
            nodes: nodes,
            edges: edges
        }};
        var options = {{
            nodes: {{
                shape: 'dot',
                size: 16,
                font: {{ color: '#ffffff', size: 12 }},
                borderWidth: 2,
                shadow: true
            }},
            edges: {{
                width: 2,
                color: {{ color: '#666666', highlight: '#00d4ff' }},
                font: {{ size: 10, align: 'middle', color: '#aaaaaa' }},
                smooth: {{ type: 'continuous' }}
            }},
            groups: {{
                Repository: {{ color: {{ background: '#e91e63', border: '#c2185b' }} }},
                File: {{ color: {{ background: '#2196f3', border: '#1976d2' }} }},
                Function: {{ color: {{ background: '#4caf50', border: '#388e3c' }} }},
                Class: {{ color: {{ background: '#ff9800', border: '#f57c00' }} }},
                Module: {{ color: {{ background: '#9c27b0', border: '#7b1fa2' }} }},
                Variable: {{ color: {{ background: '#607d8b', border: '#455a64' }} }}
            }},
            physics: {{
                forceAtlas2Based: {{
                    gravitationalConstant: -26,
                    centralGravity: 0.005,
                    springLength: 230,
                    springConstant: 0.18
                }},
                maxVelocity: 146,
                solver: 'forceAtlas2Based',
                timestep: 0.35,
                stabilization: {{ iterations: 150 }}
            }}
        }};
        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>
    """
    
    target_path = Path.cwd() / "graph_viz.html"
    with open(target_path, "w") as f:
        f.write(html_content)
    
    print(f"\n✅ Visualization generated successfully!")
    print(f"👉 Open this file in your browser: file://{target_path.absolute()}")

if __name__ == "__main__":
    generate_visualization()
