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
    """Return color configuration based on node type with a modern palette."""
    # Using HSL-based harmonious colors for a premium look
    colors = {
        "Function": {"background": "#D1FAE5", "border": "#10B981", "highlight": "#34D399"},  # Teal/Emerald
        "Class": {"background": "#DBEAFE", "border": "#3B82F6", "highlight": "#60A5FA"},     # Blue
        "Module": {"background": "#F3E8FF", "border": "#A855F7", "highlight": "#C084FC"},    # Purple
        "File": {"background": "#E0E7FF", "border": "#6366F1", "highlight": "#818CF8"},      # Indigo
        "Repository": {"background": "#FFE4E6", "border": "#F43F5E", "highlight": "#FB7185"},# Rose
        "Package": {"background": "#F1F5F9", "border": "#64748B", "highlight": "#94A3B8"},   # Slate
        "Variable": {"background": "#FEF3C7", "border": "#F59E0B", "highlight": "#FBBF24"},  # Amber
        "Caller": {"background": "#CFFAFE", "border": "#06B6D4", "highlight": "#22D3EE"},    # Cyan
        "Callee": {"background": "#ECFDF5", "border": "#10B981", "highlight": "#34D399"},    # Emerald
        "Target": {"background": "#FEE2E2", "border": "#EF4444", "highlight": "#F87171"},    # Red
        "Source": {"background": "#E0F2FE", "border": "#0EA5E9", "highlight": "#38BDF8"},    # Sky Blue
        "Parent": {"background": "#FFEDD5", "border": "#F97316", "highlight": "#FB923C"},    # Orange
        "Child": {"background": "#F0FDFA", "border": "#14B8A6", "highlight": "#2DD4BF"},     # Teal
        "Override": {"background": "#EDE9FE", "border": "#8B5CF6", "highlight": "#A78BFA"},   # Violet
        "default": {"background": "#F1F5F9", "border": "#94A3B8", "highlight": "#CBD5E1"},   # Default Slate
    }
    config = colors.get(node_type, colors["default"])
    # Vis-network expects specific keys or hex
    return {
        "background": config["background"],
        "border": config["border"],
        "highlight": {
            "background": config["highlight"],
            "border": config["border"]
        },
        "hover": {
            "background": config["highlight"],
            "border": config["border"]
        }
    }


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
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title} | CodeGraphContext</title>
    
    <!-- Modern Typography -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    
    <!-- Vis Network Library -->
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    
    <style type="text/css">
        :root {{
            --primary: #6366f1;
            --primary-glow: rgba(99, 102, 241, 0.4);
            --bg-dark: #0f172a;
            --bg-card: rgba(30, 41, 59, 0.7);
            --border: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --accent: #818cf8;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(129, 140, 248, 0.1) 0px, transparent 50%);
            color: var(--text-main);
            overflow: hidden;
            height: 100vh;
        }}

        /* --- Header & Glassmorphism --- */
        .header {{
            position: fixed;
            top: 20px;
            left: 20px;
            right: 20px;
            z-index: 1000;
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            padding: 12px 24px;
            border-radius: 16px;
            border: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            animation: slideDown 0.6s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        @keyframes slideDown {{
            from {{ transform: translateY(-100%); opacity: 0; }}
            to {{ transform: translateY(0); opacity: 1; }}
        }}

        .logo-group {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .logo-icon {{
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, var(--primary), var(--accent));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 18px;
            box-shadow: 0 0 15px var(--primary-glow);
        }}

        .logo-text {{
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(to right, #fff, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .viz-title {{
            font-size: 0.9rem;
            color: var(--text-dim);
            font-weight: 400;
            padding-left: 12px;
            border-left: 1px solid var(--border);
            margin-left: 12px;
        }}

        .stats-group {{
            display: flex;
            gap: 24px;
        }}

        .stat-item {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}

        .stat-label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-dim);
        }}

        .stat-count {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--accent);
        }}

        .search-container {{
            position: fixed;
            top: 100px;
            left: 20px;
            z-index: 1000;
            width: 200px;
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            padding: 12px;
            border-radius: 16px;
            border: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            gap: 8px;
            animation: slideLeft 0.6s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        @keyframes slideLeft {{
            from {{ transform: translateX(-100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}

        .search-input {{
            background: rgba(0,0,0,0.2);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px 12px;
            color: white;
            font-family: inherit;
            font-size: 0.85rem;
            outline: none;
            width: 100%;
        }}

        .search-input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 2px var(--primary-glow);
        }}

        /* --- Main Network Container --- */
        #mynetwork {{
            width: 100%;
            height: 100vh;
            cursor: grab;
        }}

        #mynetwork:active {{
            cursor: grabbing;
        }}

        /* --- Side Info Panel --- */
        .info-panel {{
            position: fixed;
            top: 100px;
            right: 20px;
            width: 340px;
            max-height: calc(100vh - 140px);
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border-radius: 20px;
            border: 1px solid var(--border);
            padding: 24px;
            z-index: 900;
            transform: translateX(400px);
            transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex;
            flex-direction: column;
            gap: 16px;
            overflow-y: auto;
            box-shadow: -8px 0 32px rgba(0,0,0,0.2);
        }}

        .info-panel.active {{
            transform: translateX(0);
        }}

        .info-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border);
            padding-bottom: 12px;
        }}

        .node-type-badge {{
            font-size: 0.7rem;
            padding: 4px 10px;
            border-radius: 20px;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.05em;
        }}

        .node-name {{
            font-size: 1.4rem;
            font-weight: 700;
            word-break: break-all;
            margin-top: 8px;
        }}

        .info-section {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .info-label {{
            font-size: 0.75rem;
            color: var(--text-dim);
            text-transform: uppercase;
        }}

        .info-value {{
            font-size: 0.9rem;
            color: var(--text-main);
            font-family: 'JetBrains Mono', monospace;
            word-break: break-all;
            background: rgba(0,0,0,0.2);
            padding: 8px;
            border-radius: 8px;
        }}

        /* --- Legend --- */
        .legend {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            padding: 20px;
            border-radius: 16px;
            border: 1px solid var(--border);
            z-index: 1000;
            width: 200px;
            animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        @keyframes slideUp {{
            from {{ transform: translateY(100%); opacity: 0; }}
            to {{ transform: translateY(0); opacity: 1; }}
        }}

        .legend-title {{
            font-weight: 700;
            font-size: 0.8rem;
            text-transform: uppercase;
            margin-bottom: 12px;
            color: var(--text-dim);
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 8px 0;
            font-size: 0.85rem;
            color: #ccc;
            cursor: pointer;
            transition: color 0.2s;
        }}

        .legend-item:hover {{
            color: #fff;
        }}

        .legend-color {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            box-shadow: 0 0 8px currentColor;
        }}

        /* --- Controls & Utilities --- */
        .controls {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(0,0,0,0.4);
            padding: 8px 16px;
            border-radius: 30px;
            font-size: 0.75rem;
            color: var(--text-dim);
            z-index: 800;
        }}

        .close-btn {{
            cursor: pointer;
            color: var(--text-dim);
            transition: color 0.2s;
        }}

        .close-btn:hover {{ color: #fff; }}

        ::-webkit-scrollbar {{
            width: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: transparent;
        }}
        ::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo-group">
            <div class="logo-icon">C</div>
            <div class="logo-text">CodeGraphContext</div>
            <div class="viz-title">{safe_title}</div>
        </div>
        <div class="stats-group">
            <div class="stat-item">
                <span class="stat-label">Nodes</span>
                <span class="stat-count">{len(nodes)}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Edges</span>
                <span class="stat-count">{len(edges)}</span>
            </div>
        </div>
    </div>

    <div id="info-panel" class="info-panel">
        <div class="info-header">
            <div id="node-badge" class="node-type-badge">TYPE</div>
            <div class="close-btn" onclick="closePanel()">✕</div>
        </div>
        <div id="node-name" class="node-name">Symbol Name</div>
        
        <div class="info-section">
            <span class="info-label">File Path</span>
            <div id="node-path" class="info-value">/path/to/file.py</div>
        </div>
        
        <div class="info-section">
            <span class="info-label">Context</span>
            <div id="node-context" class="info-value">None</div>
        </div>

        <div id="extra-info"></div>
    </div>

    <div class="search-container">
        <div class="legend-title" style="margin-bottom: 4px;">Quick Search</div>
        <input type="text" id="node-search" class="search-input" placeholder="Find symbol...">
    </div>

    <div id="mynetwork"></div>

    <div class="legend">
        <div class="legend-title">Entity Types</div>
        <div id="legend-items"></div>
    </div>

    <div class="controls">
        Scroll to zoom • Click to inspect • Drag to explore
    </div>

    <script type="text/javascript">
        const nodesData = {_json_for_inline_script(safe_nodes)};
        const edgesData = {_json_for_inline_script(safe_edges)};

        const nodes = new vis.DataSet(nodesData);
        const edges = new vis.DataSet(edgesData);

        const container = document.getElementById('mynetwork');
        const data = {{ nodes, edges }};
        
        const options = {{
            nodes: {{
                shape: 'dot',
                size: 24,
                font: {{
                    color: '#e2e8f0',
                    size: 14,
                    face: 'Outfit'
                }},
                borderWidth: 2,
                shadow: {{
                    enabled: true,
                    color: 'rgba(0,0,0,0.5)',
                    size: 10,
                    x: 0,
                    y: 4
                }}
            }},
            edges: {{
                width: 1.5,
                color: {{
                    color: 'rgba(148, 163, 184, 0.3)',
                    highlight: '#6366f1',
                    hover: '#818cf8'
                }},
                font: {{
                    size: 11,
                    face: 'Outfit',
                    color: '#94a3b8',
                    strokeWidth: 0
                }},
                smooth: {{
                    type: 'cubicBezier',
                    forceDirection: 'none',
                    roundness: 0.5
                }},
                arrows: {{
                    to: {{
                        enabled: true,
                        scaleFactor: 0.5
                    }}
                }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 300,
                hideEdgesOnDrag: true,
                navigationButtons: false,
                keyboard: true
            }},
            physics: {{
                enabled: true,
                stabilization: {{
                    enabled: true,
                    iterations: 150
                }},
                barnesHut: {{
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 120,
                    springConstant: 0.04,
                    damping: 0.09
                }}
            }},
            {layout_options}
        }};

        const network = new vis.Network(container, data, options);

        // Sidebar logic
        function closePanel() {{
            document.getElementById('info-panel').classList.remove('active');
        }}

        network.on('click', function(params) {{
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                const node = nodes.get(nodeId);
                const panel = document.getElementById('info-panel');
                
                document.getElementById('node-name').textContent = node.label;
                document.getElementById('node-badge').textContent = node.group;
                document.getElementById('node-badge').style.backgroundColor = node.color.border + '22';
                document.getElementById('node-badge').style.color = node.color.border;
                document.getElementById('node-badge').style.border = `1px solid ${{node.color.border}}`;
                
                // Parse tooltip for extra info
                const tooltipText = node.title || "";
                const lines = tooltipText.split('\\n');
                let path = "Unknown";
                let context = "None";
                
                lines.forEach(l => {{
                    if (l.startsWith('File:')) path = l.replace('File:', '').trim();
                    if (l.startsWith('Line:')) context = 'Line ' + l.replace('Line:', '').trim();
                }});
                
                document.getElementById('node-path').textContent = path;
                document.getElementById('node-context').textContent = context;
                
                panel.classList.add('active');

                // Visual highlight
                const connectedNodes = network.getConnectedNodes(nodeId);
                nodes.forEach(n => {{
                    nodes.update({{id: n.id, opacity: 0.15}});
                }});
                nodes.update({{id: nodeId, opacity: 1}});
                connectedNodes.forEach(id => {{
                    nodes.update({{id: id, opacity: 1}});
                }});
            }} else {{
                closePanel();
                nodes.forEach(n => {{
                    nodes.update({{id: n.id, opacity: 1}});
                }});
            }}
        }});

        // Build legend from unique groups
        const groups = [...new Set(nodesData.map(n => n.group))];
        const legendContainer = document.getElementById('legend-items');
        groups.forEach(group => {{
            const node = nodesData.find(n => n.group === group);
            const color = node?.color?.border || '#94a3b8';
            
            const item = document.createElement('div');
            item.className = 'legend-item';
            item.innerHTML = `
                <div class="legend-color" style="background: ${{color}}; color: ${{color}}"></div>
                <span>${{group}}</span>
            `;
            
            item.onclick = () => {{
                // Highlight nodes of this group
                nodes.forEach(n => {{
                    nodes.update({{id: n.id, opacity: n.group === group ? 1 : 0.15}});
                }});
            }};
            
            legendContainer.appendChild(item);
        }});

        // Search logic
        const searchInput = document.getElementById('node-search');
        searchInput.oninput = (e) => {{
            const term = e.target.value.toLowerCase();
            if (!term) {{
                nodes.forEach(n => nodes.update({{id: n.id, opacity: 1}}));
                return;
            }}
            
            nodes.forEach(n => {{
                const matches = n.label.toLowerCase().includes(term);
                nodes.update({{id: n.id, opacity: matches ? 1 : 0.1}});
            }});
        }};
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
