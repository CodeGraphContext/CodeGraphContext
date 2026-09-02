# src/codegraphcontext/utils/visualize_graph.py
"""
Utility functions for generating code graph visualizations.

Provides a programmatic API for converting graph query results into
interactive HTML visualizations, complementing the `cgc visualize` CLI command.
"""

from __future__ import annotations

import json
import os
import tempfile
import webbrowser
from html import escape as html_escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from .debug_log import debug_log, error_logger, info_logger


# ---------------------------------------------------------------------------
# Node / edge colour palette (mirrors the website's dark-mode theme)
# ---------------------------------------------------------------------------

_NODE_COLORS: Dict[str, str] = {
    "Function": "#6366f1",   # indigo
    "Class":    "#10b981",   # emerald
    "Interface":"#f59e0b",   # amber
    "File":     "#3b82f6",   # blue
    "Module":   "#8b5cf6",   # violet
    "Variable": "#ec4899",   # pink
    "default":  "#94a3b8",   # slate
}

_EDGE_COLORS: Dict[str, str] = {
    "CALLS":      "#6366f1",
    "INHERITS":   "#10b981",
    "IMPORTS":    "#3b82f6",
    "DEFINES":    "#f59e0b",
    "default":    "#64748b",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def node_color(label: str) -> str:
    """Return the hex colour string for a given node label."""
    return _NODE_COLORS.get(label, _NODE_COLORS["default"])


def edge_color(rel_type: str) -> str:
    """Return the hex colour string for a given relationship type."""
    return _EDGE_COLORS.get(rel_type, _EDGE_COLORS["default"])


def _json_for_script(data: Any) -> str:
    """Serialise ``data`` for inlining inside a ``<script>`` element.

    ``json.dumps`` escapes quotes and backslashes but leaves ``<``, ``>`` and
    ``&`` alone, so a node name or file path containing ``</script>`` closes
    the element early and the rest of the document is parsed as markup. Those
    three characters only ever appear inside string literals, so replacing
    them with their ``\\uXXXX`` form keeps the payload valid JSON and valid
    JavaScript while making it inert as markup.
    """
    return (
        json.dumps(data, indent=2)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def build_graph_data(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Convert raw node/edge dicts from a graph query into a JSON-serialisable
    structure understood by the CGC web visualiser.

    Parameters
    ----------
    nodes:
        List of dicts with at minimum ``id`` and ``label`` keys.
        Optional keys: ``name``, ``file_path``, ``line_number``.
    edges:
        List of dicts with at minimum ``source``, ``target``, and ``type`` keys.

    Returns
    -------
    dict
        ``{"nodes": [...], "edges": [...]}`` ready for ``json.dumps``.
    """
    serialised_nodes = []
    for node in nodes:
        node_id = node.get("id") or node.get("name", "unknown")
        label = node.get("label", "Function")
        raw_name = node.get("name", str(node_id))
        file_path = node.get("file_path", "")
        if raw_name == "<module>" and file_path:
            raw_name = os.path.splitext(os.path.basename(file_path))[0]
        serialised_nodes.append({
            "id":        str(node_id),
            "label":     label,
            "name":      raw_name,
            "file_path": file_path,
            "line":      node.get("line_number"),
            "color":     node_color(label),
        })

    serialised_edges = []
    for edge in edges:
        rel_type = edge.get("type", "CALLS")
        serialised_edges.append({
            "source": str(edge.get("source", "")),
            "target": str(edge.get("target", "")),
            "type":   rel_type,
            "color":  edge_color(rel_type),
            "label":  edge.get("label", rel_type),
        })

    return {"nodes": serialised_nodes, "edges": serialised_edges}


def render_html(
    graph_data: Dict[str, Any],
    title: str = "CGC Code Graph",
) -> str:
    """
    Render a self-contained HTML string for the given graph data.

    The generated page uses an inline force-directed layout via vanilla JS
    so it works in any modern browser without external dependencies.

    Parameters
    ----------
    graph_data:
        Output of :func:`build_graph_data`.
    title:
        Page ``<title>`` and heading text.

    Returns
    -------
    str
        Complete HTML document as a string.
    """
    graph_json = _json_for_script(graph_data)
    safe_title = html_escape(title)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{safe_title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      height: 100vh;
      overflow: hidden;
    }}
    #header {{
      padding: 12px 20px;
      background: #1e293b;
      border-bottom: 1px solid #334155;
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    #header h1 {{ font-size: 1rem; font-weight: 600; color: #6366f1; }}
    #header span {{ font-size: 0.75rem; color: #64748b; }}
    #canvas-container {{
      width: 100%;
      height: calc(100vh - 48px);
      position: relative;
    }}
    canvas {{ display: block; }}
    #tooltip {{
      position: absolute;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 6px;
      padding: 8px 12px;
      font-size: 0.75rem;
      pointer-events: none;
      display: none;
      max-width: 280px;
      z-index: 10;
    }}
    #tooltip .node-name {{ color: #6366f1; font-weight: 700; }}
    #tooltip .node-meta {{ color: #94a3b8; margin-top: 4px; }}
    #legend {{
      position: absolute;
      bottom: 16px;
      right: 16px;
      background: #1e293be6;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 12px;
      font-size: 0.7rem;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 4px;
    }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex-shrink: 0;
    }}
  </style>
</head>
<body>
  <div id="header">
    <h1>🏗 {safe_title}</h1>
    <span id="stats"></span>
  </div>
  <div id="canvas-container">
    <canvas id="graph-canvas"></canvas>
    <div id="tooltip">
      <div class="node-name" id="tip-name"></div>
      <div class="node-meta" id="tip-meta"></div>
    </div>
    <div id="legend"></div>
  </div>

  <script>
    const GRAPH = {graph_json};

    // ---- canvas setup ----
    const container = document.getElementById('canvas-container');
    const canvas = document.getElementById('graph-canvas');
    const ctx = canvas.getContext('2d');

    function resize() {{
      canvas.width  = container.clientWidth;
      canvas.height = container.clientHeight;
    }}
    resize();
    window.addEventListener('resize', () => {{ resize(); simulate(); }});

    // ---- stats ----
    document.getElementById('stats').textContent =
      `${{GRAPH.nodes.length}} nodes · ${{GRAPH.edges.length}} edges`;

    // ---- legend ----
    const seen = {{}};
    const legendEl = document.getElementById('legend');
    GRAPH.nodes.forEach(n => {{
      if (!seen[n.label]) {{
        seen[n.label] = n.color;
        const item = document.createElement('div');
        item.className = 'legend-item';
        item.innerHTML = `<div class="legend-dot" style="background:${{n.color}}"></div>${{n.label}}`;
        legendEl.appendChild(item);
      }}
    }});

    // ---- force simulation (simple spring layout) ----
    const W = () => canvas.width;
    const H = () => canvas.height;
    const nodeMap = {{}};
    const positions = {{}};
    const velocities = {{}};

    GRAPH.nodes.forEach((n, i) => {{
      const angle = (i / GRAPH.nodes.length) * 2 * Math.PI;
      const r = Math.min(W(), H()) * 0.35;
      positions[n.id]  = {{ x: W()/2 + r*Math.cos(angle), y: H()/2 + r*Math.sin(angle) }};
      velocities[n.id] = {{ x: 0, y: 0 }};
      nodeMap[n.id] = n;
    }});

    const edgeSet = new Set(GRAPH.edges.map(e => e.source + '|' + e.target));

    function simulate() {{
      const k  = 80;
      const kc = 5000;
      const dt = 0.4;
      const damping = 0.85;

      GRAPH.nodes.forEach(a => {{
        let fx = 0, fy = 0;
        // repulsion
        GRAPH.nodes.forEach(b => {{
          if (a.id === b.id) return;
          const dx = positions[a.id].x - positions[b.id].x;
          const dy = positions[a.id].y - positions[b.id].y;
          const dist = Math.sqrt(dx*dx + dy*dy) || 1;
          const f = kc / (dist*dist);
          fx += (dx/dist)*f;
          fy += (dy/dist)*f;
        }});
        // spring attraction
        GRAPH.edges.forEach(e => {{
          let other = null;
          if (e.source === a.id) other = e.target;
          if (e.target === a.id) other = e.source;
          if (!other || !positions[other]) return;
          const dx = positions[other].x - positions[a.id].x;
          const dy = positions[other].y - positions[a.id].y;
          const dist = Math.sqrt(dx*dx + dy*dy) || 1;
          const f = (dist - k) * 0.05;
          fx += (dx/dist)*f;
          fy += (dy/dist)*f;
        }});
        // center pull
        fx += (W()/2 - positions[a.id].x) * 0.005;
        fy += (H()/2 - positions[a.id].y) * 0.005;

        velocities[a.id].x = (velocities[a.id].x + fx*dt) * damping;
        velocities[a.id].y = (velocities[a.id].y + fy*dt) * damping;
        positions[a.id].x += velocities[a.id].x;
        positions[a.id].y += velocities[a.id].y;
        // clamp
        positions[a.id].x = Math.max(24, Math.min(W()-24, positions[a.id].x));
        positions[a.id].y = Math.max(24, Math.min(H()-24, positions[a.id].y));
      }});
    }}

    function draw() {{
      ctx.clearRect(0, 0, W(), H());
      // edges
      GRAPH.edges.forEach(e => {{
        const s = positions[e.source];
        const t = positions[e.target];
        if (!s || !t) return;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(t.x, t.y);
        ctx.strokeStyle = e.color + '99';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        // arrowhead
        const angle = Math.atan2(t.y - s.y, t.x - s.x);
        const r = 14;
        ctx.beginPath();
        ctx.moveTo(t.x - r*Math.cos(angle-0.3), t.y - r*Math.sin(angle-0.3));
        ctx.lineTo(t.x - r*Math.cos(angle), t.y - r*Math.sin(angle));
        ctx.lineTo(t.x - r*Math.cos(angle+0.3), t.y - r*Math.sin(angle+0.3));
        ctx.strokeStyle = e.color;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }});
      // nodes
      GRAPH.nodes.forEach(n => {{
        const p = positions[n.id];
        ctx.beginPath();
        ctx.arc(p.x, p.y, 12, 0, 2*Math.PI);
        ctx.fillStyle = n.color;
        ctx.fill();
        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 2;
        ctx.stroke();
        // label
        ctx.fillStyle = '#e2e8f0';
        ctx.font = '10px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(n.name.length > 16 ? n.name.slice(0,14)+'…' : n.name, p.x, p.y + 24);
      }});
    }}

    let frame = 0;
    function loop() {{
      if (frame < 200) simulate();
      frame++;
      draw();
      requestAnimationFrame(loop);
    }}
    loop();

    // ---- tooltip ----
    const tooltip  = document.getElementById('tooltip');
    const tipName  = document.getElementById('tip-name');
    const tipMeta  = document.getElementById('tip-meta');

    canvas.addEventListener('mousemove', e => {{
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      let hit = null;
      GRAPH.nodes.forEach(n => {{
        const p = positions[n.id];
        const dx = mx - p.x, dy = my - p.y;
        if (Math.sqrt(dx*dx + dy*dy) < 14) hit = n;
      }});
      if (hit) {{
        tipName.textContent = hit.name;
        tipMeta.textContent = [
          hit.label,
          hit.file_path ? hit.file_path.split('/').pop() : '',
          hit.line ? `line ${{hit.line}}` : '',
        ].filter(Boolean).join(' · ');
        tooltip.style.display = 'block';
        tooltip.style.left = (e.clientX - rect.left + 16) + 'px';
        tooltip.style.top  = (e.clientY - rect.top  - 8)  + 'px';
      }} else {{
        tooltip.style.display = 'none';
      }}
    }});
    canvas.addEventListener('mouseleave', () => {{ tooltip.style.display = 'none'; }});
  </script>
</body>
</html>"""
    return html


def open_in_browser(
    graph_data: Dict[str, Any],
    title: str = "CGC Code Graph",
    output_path: Optional[str] = None,
) -> str:
    """
    Write the visualization HTML to a file and open it in the default browser.

    Parameters
    ----------
    graph_data:
        Output of :func:`build_graph_data`.
    title:
        Page title shown in the browser tab and heading.
    output_path:
        Optional explicit file path for the HTML output.
        If *None* a temporary file is created.

    Returns
    -------
    str
        Absolute path to the generated HTML file.
    """
    html = render_html(graph_data, title=title)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        abs_path = str(path.resolve())
    else:
        fd, abs_path = tempfile.mkstemp(suffix=".html", prefix="cgc_graph_")
        os.close(fd)
        Path(abs_path).write_text(html, encoding="utf-8")

    info_logger(f"[VISUALIZE] Graph written to {abs_path}")
    debug_log(f"[VISUALIZE] Opening browser: {abs_path}")

    webbrowser.open(f"file://{abs_path}")
    return abs_path


def save_graph_html(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    output_path: str,
    title: str = "CGC Code Graph",
) -> str:
    """
    Convenience wrapper: build graph data and save as HTML in one call.

    Parameters
    ----------
    nodes:
        Raw node dicts (see :func:`build_graph_data`).
    edges:
        Raw edge dicts (see :func:`build_graph_data`).
    output_path:
        File path for the HTML output.
    title:
        Page title.

    Returns
    -------
    str
        Absolute path to the saved HTML file.
    """
    graph_data = build_graph_data(nodes, edges)
    return open_in_browser(graph_data, title=title, output_path=output_path)