# src/codegraphcontext/cli/visualizer.py
"""
Visualization module for CodeGraphContext CLI.

This module generates interactive HTML graph visualizations using vis-network.js
for various CLI command outputs (analyze calls, callers, chain, deps, tree, etc.).

The visualizations are standalone HTML files that can be opened in any browser.
"""

import html
import json
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
from rich.console import Console

console = Console(stderr=True)


def escape_html(text: Any) -> str:
    """Safely escape HTML special characters to prevent XSS."""
    if text is None:
        return ""
    return html.escape(str(text))


def get_visualization_dir() -> Path:
    """Get or create the visualization output directory."""
    viz_dir = Path.home() / ".codegraphcontext" / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    return viz_dir


def generate_filename(prefix: str = "cgc_viz") -> str:
    """Generate a unique filename with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    unique = uuid.uuid4().hex[:8]
    return f"{prefix}_{timestamp}_{unique}.html"


def _json_for_inline_script(data: Any) -> str:
    """Serialize to JSON safe to embed directly inside a <script> tag.

    Prevents script-breaking sequences like </script> from terminating the script.
    """
    raw = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    # Mitigate XSS via breaking out of script context.
    raw = raw.replace("</", "<\\/")
    raw = raw.replace("<!--", "<\\!--")
    raw = raw.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return raw


def get_node_color(node_type: str) -> Dict[str, str]:
    """Return color configuration based on node type."""
    colors = {
        "Function": {"background": "#4caf50", "border": "#388e3c"},  # Green
        "Class": {"background": "#ff9800", "border": "#f57c00"},  # Orange
        "Module": {"background": "#9c27b0", "border": "#7b1fa2"},  # Purple
        "File": {"background": "#2196f3", "border": "#1976d2"},  # Blue
        "Repository": {"background": "#e91e63", "border": "#c2185b"},  # Pink
        "Package": {"background": "#607d8b", "border": "#455a64"},  # Grey
        "Variable": {"background": "#795548", "border": "#5d4037"},  # Brown
        "Caller": {"background": "#00bcd4", "border": "#0097a7"},  # Cyan
        "Callee": {"background": "#8bc34a", "border": "#689f38"},  # Light Green
        "Target": {"background": "#f44336", "border": "#d32f2f"},  # Red
        "Source": {"background": "#3f51b5", "border": "#303f9f"},  # Indigo
        "Parent": {"background": "#ff5722", "border": "#e64a19"},  # Deep Orange
        "Child": {"background": "#009688", "border": "#00796b"},  # Teal
        "Override": {"background": "#673ab7", "border": "#512da8"},  # Deep Purple
        "default": {"background": "#97c2fc", "border": "#2b7ce9"},  # Default blue
    }
    return colors.get(node_type, colors["default"])


def generate_html_template(
    nodes: List[Dict],
    edges: List[Dict],
    title: str,
    layout_type: str = "force",
    description: str = ""
) -> str:
    """
    Generate standalone HTML with vis-network.js visualization.
    
    Args:
        nodes: List of node dictionaries with id, label, group, title, color
        edges: List of edge dictionaries with from, to, label, arrows
        title: Title for the visualization
        layout_type: "force" for force-directed, "hierarchical" for tree layouts
        description: Optional description to show in the header
    
    Returns:
        Complete HTML string
    """
    # Configure layout options based on type
    if layout_type == "hierarchical":
        layout_options = """
            layout: {
                hierarchical: {
                    enabled: true,
                    direction: 'UD',
                    sortMethod: 'directed',
                    levelSeparation: 100,
                    nodeSpacing: 150,
                    treeSpacing: 200,
                    blockShifting: true,
                    edgeMinimization: true,
                    parentCentralization: true
                }
            },
            physics: {
                enabled: false
            }
        """
    elif layout_type == "hierarchical_lr":
        layout_options = """
            layout: {
                hierarchical: {
                    enabled: true,
                    direction: 'LR',
                    sortMethod: 'directed',
                    levelSeparation: 200,
                    nodeSpacing: 100,
                    treeSpacing: 200
                }
            },
            physics: {
                enabled: false
            }
        """
    else:  # force-directed
        layout_options = """
            layout: {
                improvedLayout: true
            },
            physics: {
                enabled: true,
                forceAtlas2Based: {
                    gravitationalConstant: -50,
                    centralGravity: 0.01,
                    springLength: 150,
                    springConstant: 0.08,
                    damping: 0.4
                },
                maxVelocity: 50,
                solver: 'forceAtlas2Based',
                timestep: 0.35,
                stabilization: {
                    enabled: true,
                    iterations: 200,
                    updateInterval: 25
                }
            }
        """

    # Escape user-provided content to prevent XSS
    safe_title = escape_html(title)
    safe_description = escape_html(description)

    # Escape tooltip HTML (vis-network treats title as HTML)
    safe_nodes: List[Dict[str, Any]] = []
    for node in nodes:
        node_copy = dict(node)
        if "title" in node_copy:
            node_copy["title"] = escape_html(node_copy.get("title", ""))
        safe_nodes.append(node_copy)
    safe_edges: List[Dict[str, Any]] = [dict(edge) for edge in edges]
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{safe_title} - CodeGraphContext</title>
    <meta charset="utf-8">
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #ffffff;
            min-height: 100vh;
        }}
        .header {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            background: rgba(26, 26, 46, 0.95);
            backdrop-filter: blur(10px);
            padding: 15px 25px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-left {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .logo {{
            font-size: 1.4em;
            font-weight: 700;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .title {{
            font-size: 1.1em;
            color: #a0a0a0;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            font-size: 0.9em;
        }}
        .stat {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .stat-value {{
            color: #00d4ff;
            font-weight: 600;
        }}
        .description {{
            color: #888;
            font-size: 0.85em;
            margin-top: 5px;
        }}
        #mynetwork {{
            width: 100%;
            height: 100vh;
            padding-top: 70px;
        }}
        .legend {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: rgba(26, 26, 46, 0.95);
            backdrop-filter: blur(10px);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 0.85em;
            z-index: 1000;
        }}
        .legend-title {{
            font-weight: 600;
            margin-bottom: 10px;
            color: #00d4ff;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 5px 0;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        .controls {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(26, 26, 46, 0.95);
            backdrop-filter: blur(10px);
            padding: 10px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 0.8em;
            z-index: 1000;
            color: #888;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <span class="logo">CodeGraphContext</span>
            <span class="title">{safe_title}</span>
        </div>
        <div class="stats">
            <div class="stat">
                <span>Nodes:</span>
                <span class="stat-value">{len(nodes)}</span>
            </div>
            <div class="stat">
                <span>Edges:</span>
                <span class="stat-value">{len(edges)}</span>
            </div>
        </div>
    </div>
    {f'<div class="description">{safe_description}</div>' if description else ''}
    
    <div id="mynetwork"></div>

    <div class="legend">
        <div class="legend-title">Legend</div>
        <div id="legend-items"></div>
    </div>

    <div class="controls">
        Drag to pan • Scroll to zoom • Click node to highlight
    </div>

    <script type="text/javascript">
        var nodesData = {_json_for_inline_script(safe_nodes)};
        var edgesData = {_json_for_inline_script(safe_edges)};

        var nodes = new vis.DataSet(nodesData);
        var edges = new vis.DataSet(edgesData);

        var container = document.getElementById('mynetwork');
        var data = {{
            nodes: nodes,
            edges: edges
        }};
        
        var options = {{
            nodes: {{
                shape: 'dot',
                size: 20,
                font: {{
                    color: '#ffffff',
                    size: 14,
                    face: 'arial'
                }},
                borderWidth: 2,
                shadow: {{
                    enabled: true,
                    color: 'rgba(0,0,0,0.3)',
                    size: 5
                }}
            }},
            edges: {{
                width: 2,
                color: {{
                    color: '#666666',
                    highlight: '#00d4ff',
                    hover: '#00d4ff'
                }},
                font: {{
                    size: 11,
                    align: 'middle',
                    color: '#aaaaaa',
                    strokeWidth: 0
                }},
                smooth: {{
                    type: 'cubicBezier',
                    forceDirection: 'none'
                }},
                arrows: {{
                    to: {{
                        enabled: true,
                        scaleFactor: 0.8
                    }}
                }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 200,
                hideEdgesOnDrag: true,
                navigationButtons: true,
                keyboard: true
            }},
            {layout_options}
        }};

        var network = new vis.Network(container, data, options);

        // Build legend from unique groups
        var groups = [...new Set(nodesData.map(n => n.group))];
        var legendContainer = document.getElementById('legend-items');
        groups.forEach(function(group) {{
            var node = nodesData.find(n => n.group === group);
            var color = node && node.color ? node.color.background : '#97c2fc';
            var item = document.createElement('div');
            item.className = 'legend-item';

            var colorBox = document.createElement('div');
            colorBox.className = 'legend-color';
            if (color) {{
                colorBox.style.background = color;
            }}

            var label = document.createElement('span');
            label.textContent = String(group);

            item.appendChild(colorBox);
            item.appendChild(label);
            legendContainer.appendChild(item);
        }});

        // Highlight connected nodes on click
        network.on('click', function(params) {{
            if (params.nodes.length > 0) {{
                var nodeId = params.nodes[0];
                var connectedNodes = network.getConnectedNodes(nodeId);
                var connectedEdges = network.getConnectedEdges(nodeId);
                
                // Reset all nodes
                nodes.forEach(function(node) {{
                    nodes.update({{id: node.id, opacity: 0.3}});
                }});
                
                // Highlight selected and connected
                nodes.update({{id: nodeId, opacity: 1}});
                connectedNodes.forEach(function(id) {{
                    nodes.update({{id: id, opacity: 1}});
                }});
            }}
        }});

        // Reset on background click
        network.on('click', function(params) {{
            if (params.nodes.length === 0 && params.edges.length === 0) {{
                nodes.forEach(function(node) {{
                    nodes.update({{id: node.id, opacity: 1}});
                }});
            }}
        }});
    </script>
</body>
</html>
"""
    return html_content


def visualize_call_graph(
    results: List[Dict],
    function_name: str,
    direction: Literal["outgoing", "incoming"] = "outgoing"
) -> Optional[str]:
    """
    Visualize function call relationships (calls or callers).
    
    Args:
        results: List of call results from CodeFinder
        function_name: The central function name
        direction: "outgoing" for calls, "incoming" for callers
    
    Returns:
        Path to generated HTML file, or None if no results
    """
    if not results:
        console.print("[yellow]No results to visualize.[/yellow]")
        return None

    nodes = []
    edges = []
    seen_nodes = set()

    # Add central function node
    central_id = f"central_{function_name}"
    central_color = get_node_color("Source" if direction == "outgoing" else "Target")
    nodes.append({
        "id": central_id,
        "label": function_name,
        "group": "Source" if direction == "outgoing" else "Target",
        "title": f"{'Caller' if direction == 'outgoing' else 'Called'}: {function_name}",
        "color": central_color,
        "size": 30,
        "font": {"size": 16, "color": "#ffffff"}
    })
    seen_nodes.add(central_id)

    for idx, result in enumerate(results):
        if direction == "outgoing":
            # calls: function_name -> called_function
            func_name = result.get("called_function", f"unknown_{idx}")
            path = result.get("called_file_path", "")
            line_num = result.get("called_line_number", "")
            is_dep = result.get("called_is_dependency", False)
        else:
            # callers: caller_function -> function_name
            func_name = result.get("caller_function", f"unknown_{idx}")
            path = result.get("caller_file_path", "")
            line_num = result.get("caller_line_number", "")
            is_dep = result.get("caller_is_dependency", False)

        node_id = f"node_{func_name}_{idx}"
        node_type = "Callee" if direction == "outgoing" else "Caller"
        if is_dep:
            node_type = "Package"

        if node_id not in seen_nodes:
            color = get_node_color(node_type)
            nodes.append({
                "id": node_id,
                "label": func_name,
                "group": node_type,
                "title": f"{func_name}\nFile: {path}\nLine: {line_num}",
                "color": color
            })
            seen_nodes.add(node_id)

        if direction == "outgoing":
            edges.append({
                "from": central_id,
                "to": node_id,
                "label": "calls",
                "arrows": "to"
            })
        else:
            edges.append({
                "from": node_id,
                "to": central_id,
                "label": "calls",
                "arrows": "to"
            })

    title = f"{'Outgoing Calls' if direction == 'outgoing' else 'Incoming Callers'}: {function_name}"
    description = f"Showing {len(results)} {'called functions' if direction == 'outgoing' else 'caller functions'}"
    
    html = generate_html_template(nodes, edges, title, layout_type="force", description=description)
    return save_and_open_visualization(html, f"cgc_{'calls' if direction == 'outgoing' else 'callers'}")


def visualize_call_chain(
    results: List[Dict],
    from_func: str,
    to_func: str
) -> Optional[str]:
    """
    Visualize call chain between two functions.
    
    Args:
        results: List of chain results, each containing function_chain
        from_func: Starting function name
        to_func: Target function name
    
    Returns:
        Path to generated HTML file, or None if no results
    """
    if not results:
        console.print("[yellow]No call chain found to visualize.[/yellow]")
        return None

    nodes = []
    edges = []
    seen_nodes = set()

    for chain_idx, chain in enumerate(results):
        functions = chain.get("function_chain", [])
        
        for idx, func in enumerate(functions):
            func_name = func.get("name", f"unknown_{idx}")
            path = func.get("path", "")
            line_num = func.get("line_number", "")
            
            node_id = f"chain{chain_idx}_{func_name}_{idx}"
            
            # Determine node type based on position
            if idx == 0:
                node_type = "Source"
            elif idx == len(functions) - 1:
                node_type = "Target"
            else:
                node_type = "Function"

            if node_id not in seen_nodes:
                color = get_node_color(node_type)
                nodes.append({
                    "id": node_id,
                    "label": func_name,
                    "group": node_type,
                    "title": f"{func_name}\nFile: {path}\nLine: {line_num}",
                    "color": color,
                    "level": idx  # For hierarchical layout
                })
                seen_nodes.add(node_id)

            # Add edge to next function in chain
            if idx < len(functions) - 1:
                next_func = functions[idx + 1]
                next_name = next_func.get("name", f"unknown_{idx+1}")
                next_id = f"chain{chain_idx}_{next_name}_{idx+1}"
                edges.append({
                    "from": node_id,
                    "to": next_id,
                    "label": "→",
                    "arrows": "to"
                })

    title = f"Call Chain: {from_func} → {to_func}"
    description = f"Found {len(results)} path(s)"
    
    html = generate_html_template(nodes, edges, title, layout_type="hierarchical", description=description)
    return save_and_open_visualization(html, "cgc_chain")


def visualize_dependencies(
    results: Dict,
    module_name: str
) -> Optional[str]:
    """
    Visualize module dependencies (imports and importers).
    
    Args:
        results: Dict with 'importers' and 'imports' lists
        module_name: The central module name
    
    Returns:
        Path to generated HTML file, or None if no results
    """
    importers = results.get("importers", [])
    imports = results.get("imports", [])
    
    if not importers and not imports:
        console.print("[yellow]No dependency information to visualize.[/yellow]")
        return None

    nodes = []
    edges = []
    seen_nodes = set()

    # Central module node
    central_id = f"central_{module_name}"
    color = get_node_color("Module")
    nodes.append({
        "id": central_id,
        "label": module_name,
        "group": "Module",
        "title": f"Module: {module_name}",
        "color": color,
        "size": 30
    })
    seen_nodes.add(central_id)

    # Files that import this module
    for idx, imp in enumerate(importers):
        path = imp.get("importer_file_path", f"file_{idx}")
        file_name = Path(path).name if path else f"file_{idx}"
        node_id = f"importer_{idx}"
        
        if node_id not in seen_nodes:
            color = get_node_color("File")
            nodes.append({
                "id": node_id,
                "label": file_name,
                "group": "Importer",
                "title": f"File: {path}\nLine: {imp.get('import_line_number', '')}",
                "color": color
            })
            seen_nodes.add(node_id)
            
        edges.append({
            "from": node_id,
            "to": central_id,
            "label": "imports",
            "arrows": "to"
        })

    # Modules that this module imports
    for idx, imp in enumerate(imports):
        imported_module = imp.get("imported_module", f"module_{idx}")
        alias = imp.get("import_alias", "")
        node_id = f"imported_{idx}"
        
        if node_id not in seen_nodes:
            color = get_node_color("Package")
            nodes.append({
                "id": node_id,
                "label": imported_module + (f" as {alias}" if alias else ""),
                "group": "Imported",
                "title": f"Module: {imported_module}",
                "color": color
            })
            seen_nodes.add(node_id)
            
        edges.append({
            "from": central_id,
            "to": node_id,
            "label": "imports",
            "arrows": "to"
        })

    title = f"Dependencies: {module_name}"
    description = f"{len(importers)} importer(s), {len(imports)} import(s)"
    
    html = generate_html_template(nodes, edges, title, layout_type="force", description=description)
    return save_and_open_visualization(html, "cgc_deps")


def visualize_inheritance_tree(
    results: Dict,
    class_name: str
) -> Optional[str]:
    """
    Visualize class inheritance hierarchy.
    
    Args:
        results: Dict with 'parent_classes', 'child_classes', and 'methods'
        class_name: The central class name
    
    Returns:
        Path to generated HTML file, or None if no results
    """
    parents = results.get("parent_classes", [])
    children = results.get("child_classes", [])
    methods = results.get("methods", [])
    
    if not parents and not children:
        console.print("[yellow]No inheritance hierarchy to visualize.[/yellow]")
        return None

    nodes = []
    edges = []
    seen_nodes = set()

    # Central class node
    central_id = f"central_{class_name}"
    color = get_node_color("Class")
    method_list = ", ".join([m.get("method_name", "") for m in methods[:5]])
    if len(methods) > 5:
        method_list += f"... (+{len(methods) - 5} more)"
    
    nodes.append({
        "id": central_id,
        "label": class_name,
        "group": "Class",
        "title": f"Class: {class_name}\nMethods: {method_list or 'None'}",
        "color": color,
        "size": 30,
        "level": 1  # Middle level
    })
    seen_nodes.add(central_id)

    # Parent classes (above)
    for idx, parent in enumerate(parents):
        parent_name = parent.get("parent_class", f"Parent_{idx}")
        path = parent.get("parent_file_path", "")
        node_id = f"parent_{idx}"
        
        if node_id not in seen_nodes:
            color = get_node_color("Parent")
            nodes.append({
                "id": node_id,
                "label": parent_name,
                "group": "Parent",
                "title": f"Parent: {parent_name}\nFile: {path}",
                "color": color,
                "level": 0  # Top level
            })
            seen_nodes.add(node_id)
            
        edges.append({
            "from": central_id,
            "to": node_id,
            "label": "extends",
            "arrows": "to"
        })

    # Child classes (below)
    for idx, child in enumerate(children):
        child_name = child.get("child_class", f"Child_{idx}")
        path = child.get("child_file_path", "")
        node_id = f"child_{idx}"
        
        if node_id not in seen_nodes:
            color = get_node_color("Child")
            nodes.append({
                "id": node_id,
                "label": child_name,
                "group": "Child",
                "title": f"Child: {child_name}\nFile: {path}",
                "color": color,
                "level": 2  # Bottom level
            })
            seen_nodes.add(node_id)
            
        edges.append({
            "from": node_id,
            "to": central_id,
            "label": "extends",
            "arrows": "to"
        })

    title = f"Class Hierarchy: {class_name}"
    description = f"{len(parents)} parent(s), {len(children)} child(ren), {len(methods)} method(s)"
    
    html = generate_html_template(nodes, edges, title, layout_type="hierarchical", description=description)
    return save_and_open_visualization(html, "cgc_tree")


def visualize_overrides(
    results: List[Dict],
    function_name: str
) -> Optional[str]:
    """
    Visualize function/method overrides across classes.
    
    Args:
        results: List of override results with class_name and function info
        function_name: The method name being overridden
    
    Returns:
        Path to generated HTML file, or None if no results
    """
    if not results:
        console.print("[yellow]No overrides to visualize.[/yellow]")
        return None

    nodes = []
    edges = []
    seen_nodes = set()

    # Central method name node
    central_id = f"method_{function_name}"
    color = get_node_color("Function")
    nodes.append({
        "id": central_id,
        "label": f"Method: {function_name}",
        "group": "Method",
        "title": f"Method: {function_name}\n{len(results)} implementation(s)",
        "color": color,
        "size": 30
    })
    seen_nodes.add(central_id)

    # Classes implementing this method
    for idx, res in enumerate(results):
        class_name = res.get("class_name", f"Class_{idx}")
        path = res.get("class_file_path", "")
        line_num = res.get("function_line_number", "")
        node_id = f"class_{idx}"
        
        if node_id not in seen_nodes:
            color = get_node_color("Override")
            nodes.append({
                "id": node_id,
                "label": class_name,
                "group": "Class",
                "title": f"Class: {class_name}\nFile: {path}\nLine: {line_num}",
                "color": color
            })
            seen_nodes.add(node_id)
            
        edges.append({
            "from": node_id,
            "to": central_id,
            "label": "implements",
            "arrows": "to"
        })

    title = f"Overrides: {function_name}"
    description = f"{len(results)} implementation(s) found"
    
    html = generate_html_template(nodes, edges, title, layout_type="force", description=description)
    return save_and_open_visualization(html, "cgc_overrides")


def visualize_search_results(
    results: List[Dict],
    search_term: str,
    search_type: str = "search"
) -> Optional[str]:
    """
    Visualize search/find results as a cluster of nodes.
    
    Args:
        results: List of search results with name, type, path, etc.
        search_term: The search term used
        search_type: Type of search (name, pattern, type)
    
    Returns:
        Path to generated HTML file, or None if no results
    """
    if not results:
        console.print("[yellow]No search results to visualize.[/yellow]")
        return None

    nodes = []
    edges = []
    seen_nodes = set()

    # Central search node
    central_id = "search_center"
    nodes.append({
        "id": central_id,
        "label": f"Search: {search_term}",
        "group": "Search",
        "title": f"Search term: {search_term}\n{len(results)} result(s)",
        "color": {"background": "#ff4081", "border": "#c51162"},
        "size": 35
    })
    seen_nodes.add(central_id)

    # Group results by type
    for idx, res in enumerate(results):
        name = res.get("name", f"result_{idx}")
        node_type = res.get("type", "Unknown")
        path = res.get("path", "")
        line_num = res.get("line_number", "")
        is_dep = res.get("is_dependency", False)
        
        node_id = f"result_{idx}"
        
        if node_id not in seen_nodes:
            color = get_node_color(node_type if not is_dep else "Package")
            nodes.append({
                "id": node_id,
                "label": name,
                "group": node_type,
                "title": f"{node_type}: {name}\nFile: {path}\nLine: {line_num}",
                "color": color
            })
            seen_nodes.add(node_id)
            
        edges.append({
            "from": central_id,
            "to": node_id,
            "label": "matches",
            "arrows": "to",
            "dashes": True
        })

    title = f"Search Results: {search_term}"
    description = f"Found {len(results)} match(es) for '{search_term}'"
    
    html = generate_html_template(nodes, edges, title, layout_type="force", description=description)
    return save_and_open_visualization(html, f"cgc_find_{search_type}")


def _safe_json_dumps(obj: Any, indent: int = 2) -> str:
    """Safely serialize object to JSON, handling non-serializable types."""
    def default_handler(o):
        try:
            return str(o)
        except Exception:
            return "<non-serializable>"
    
    try:
        return json.dumps(obj, indent=indent, default=default_handler)
    except Exception:
        return "{}"


def visualize_cypher_results(
    records: List[Dict],
    query: str
) -> Optional[str]:
    """
    Visualize raw Cypher query results.
    
    Args:
        records: List of records returned from Cypher query
        query: The original Cypher query
    
    Returns:
        Path to generated HTML file, or None if no results
    """
    if not records:
        console.print("[yellow]No query results to visualize.[/yellow]")
        return None

    nodes = []
    edges = []
    seen_nodes = set()

    for record in records:
        for key, value in record.items():
            if isinstance(value, dict):
                # Likely a node
                node_id = value.get("id", value.get("name", f"node_{len(seen_nodes)}"))
                if str(node_id) not in seen_nodes:
                    labels = value.get("labels", [key])
                    label = labels[0] if isinstance(labels, list) and labels else str(labels)
                    name = value.get("name", str(node_id))
                    
                    color = get_node_color(label)
                    nodes.append({
                        "id": str(node_id),
                        "label": str(name) if name else str(node_id),
                        "group": label,
                        "title": _safe_json_dumps(value),
                        "color": color
                    })
                    seen_nodes.add(str(node_id))
            elif isinstance(value, list):
                # Could be a path or list of nodes
                for item in value:
                    if isinstance(item, dict):
                        node_id = item.get("id", item.get("name", f"node_{len(seen_nodes)}"))
                        if str(node_id) not in seen_nodes:
                            name = item.get("name", str(node_id))
                            labels = item.get("labels", ["Node"])
                            label = labels[0] if isinstance(labels, list) and labels else "Node"
                            
                            color = get_node_color(label)
                            nodes.append({
                                "id": str(node_id),
                                "label": str(name) if name else str(node_id),
                                "group": label,
                                "title": _safe_json_dumps(item),
                                "color": color
                            })
                            seen_nodes.add(str(node_id))

    # NOTE: We intentionally do not infer edges when the Cypher query doesn't
    # explicitly return relationships. Auto-linking sequential nodes can be
    # misleading when the result set contains unrelated nodes.

    title = "Cypher Query Results"
    # Truncate query for description
    short_query = query[:50] + "..." if len(query) > 50 else query
    description = f"Query: {short_query}"
    
    html = generate_html_template(nodes, edges, title, layout_type="force", description=description)
    return save_and_open_visualization(html, "cgc_query")


def save_and_open_visualization(html_content: str, prefix: str = "cgc_viz") -> Optional[str]:
    """
    Save HTML content to file and open in browser.
    
    Args:
        html_content: The complete HTML string
        prefix: Filename prefix
    
    Returns:
        Path to the saved file, or None if saving failed
    """
    viz_dir = get_visualization_dir()
    filename = generate_filename(prefix)
    filepath = viz_dir / filename
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
    except (IOError, OSError) as e:
        console.print(f"[red]Error saving visualization: {e}[/red]")
        return None
    
    console.print(f"[green]✓ Visualization saved:[/green] {filepath}")
    console.print("[dim]Opening in browser...[/dim]")
    
    # Open in default browser - use proper file URI format
    try:
        # Convert to proper file URI (works on Windows and Unix)
        file_uri = filepath.as_uri()
        webbrowser.open(file_uri)
    except Exception as e:
        console.print(f"[yellow]Could not open browser automatically: {e}[/yellow]")
        console.print(f"[dim]Open this file manually: {filepath}[/dim]")
    
    return str(filepath)


def check_visual_flag(ctx: Any, local_visual: bool = False) -> bool:
    """
    Check if visual mode is enabled (either globally or locally).
    
    Args:
        ctx: Typer context object
        local_visual: Local --visual flag value
    
    Returns:
        True if visualization should be used
    """
    global_visual = False
    if ctx and hasattr(ctx, 'obj') and ctx.obj:
        global_visual = ctx.obj.get("visual", False)
    return local_visual or global_visual
