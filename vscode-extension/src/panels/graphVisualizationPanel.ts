// src/panels/graphVisualizationPanel.ts
import * as vscode from 'vscode';
import { GraphData } from '../cgcManager';

export class GraphVisualizationPanel {
    public static currentPanel: GraphVisualizationPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, graphData: GraphData, title: string) {
        this._panel = panel;
        this._panel.title = title;
        this._panel.webview.html = this._getHtmlForWebview(this._panel.webview, extensionUri, graphData);
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    }

    public static render(extensionUri: vscode.Uri, graphData: GraphData, title: string) {
        const column = vscode.ViewColumn.Two;

        if (GraphVisualizationPanel.currentPanel) {
            GraphVisualizationPanel.currentPanel._panel.reveal(column);
            GraphVisualizationPanel.currentPanel._panel.title = title;
            GraphVisualizationPanel.currentPanel._panel.webview.html =
                GraphVisualizationPanel.currentPanel._getHtmlForWebview(
                    GraphVisualizationPanel.currentPanel._panel.webview,
                    extensionUri,
                    graphData
                );
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'cgcGraphVisualization',
            title,
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true
            }
        );

        GraphVisualizationPanel.currentPanel = new GraphVisualizationPanel(panel, extensionUri, graphData, title);
    }

    public dispose() {
        GraphVisualizationPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) { disposable.dispose(); }
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview, extensionUri: vscode.Uri, graphData: GraphData): string {
        const graphDataJson = JSON.stringify(graphData);

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CGC Knowledge Graph</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            background: #050508;
            color: #e2e8f0;
            font-family: 'Inter', -apple-system, sans-serif;
            overflow: hidden;
            height: 100vh;
            width: 100vw;
            display: flex;
        }

        /* ── Sidebar ─────────────────────────────────────── */
        #sidebar {
            width: 220px;
            min-width: 220px;
            background: #0a0b10;
            border-right: 1px solid rgba(255,255,255,0.06);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            z-index: 10;
            transition: width 0.3s ease;
        }

        #sidebar.collapsed {
            width: 0;
            min-width: 0;
        }

        .sidebar-header {
            padding: 14px 16px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #64748b;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .sidebar-header span { color: #94a3b8; font-size: 10px; font-weight: 400; margin-left: auto; }

        .node-list {
            overflow-y: auto;
            flex: 1;
            padding: 8px 0;
        }

        .node-list::-webkit-scrollbar { width: 4px; }
        .node-list::-webkit-scrollbar-track { background: transparent; }
        .node-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

        .node-list-item {
            padding: 6px 16px;
            font-size: 12px;
            cursor: pointer;
            color: #64748b;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.15s;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .node-list-item:hover { background: rgba(255,255,255,0.04); color: #e2e8f0; }
        .node-list-item.active { background: rgba(255,255,255,0.06); color: #fff; }

        .node-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }

        /* ── Main canvas area ────────────────────────────── */
        #canvas-wrapper {
            flex: 1;
            position: relative;
            overflow: hidden;
        }

        svg#graph {
            width: 100%;
            height: 100%;
            cursor: grab;
        }

        svg#graph:active { cursor: grabbing; }

        /* ── Topbar ──────────────────────────────────────── */
        #topbar {
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 48px;
            background: rgba(10, 11, 16, 0.85);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255,255,255,0.05);
            display: flex;
            align-items: center;
            padding: 0 16px;
            gap: 12px;
            z-index: 20;
        }

        #toggle-sidebar {
            width: 28px; height: 28px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 6px;
            cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            font-size: 14px;
            transition: background 0.2s;
            color: #94a3b8;
        }
        #toggle-sidebar:hover { background: rgba(255,255,255,0.1); }

        #search-box {
            flex: 1;
            max-width: 280px;
            height: 30px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 0 12px;
            color: #e2e8f0;
            font-size: 12px;
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s;
        }
        #search-box::placeholder { color: #475569; }
        #search-box:focus { border-color: rgba(255,255,255,0.2); }

        .top-stats {
            margin-left: auto;
            display: flex;
            gap: 16px;
            font-size: 11px;
            color: #475569;
        }

        .top-stats .stat { display: flex; align-items: center; gap: 4px; }
        .top-stats .val { color: #94a3b8; font-weight: 500; }

        .top-btns {
            display: flex;
            gap: 6px;
        }

        .top-btn {
            padding: 5px 12px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 6px;
            font-size: 11px;
            font-family: inherit;
            color: #94a3b8;
            cursor: pointer;
            transition: all 0.2s;
        }
        .top-btn:hover { background: rgba(255,255,255,0.1); color: #e2e8f0; border-color: rgba(255,255,255,0.15); }

        /* ── Tooltip ─────────────────────────────────────── */
        #tooltip {
            position: absolute;
            padding: 12px 16px;
            background: rgba(15, 16, 22, 0.95);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s ease;
            z-index: 100;
            min-width: 220px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.6);
        }

        #tooltip .tt-name {
            font-size: 14px;
            font-weight: 600;
            color: #f1f5f9;
            margin-bottom: 8px;
            word-break: break-all;
        }

        #tooltip .tt-row {
            font-size: 11px;
            color: #475569;
            margin: 3px 0;
            display: flex;
            gap: 6px;
        }

        #tooltip .tt-row strong { color: #64748b; min-width: 40px; }
        #tooltip .tt-row span { color: #94a3b8; word-break: break-all; }

        #tooltip .tt-badge {
            display: inline-block;
            margin-top: 10px;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        /* ── Legend ──────────────────────────────────────── */
        #legend {
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(10, 11, 16, 0.9);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 14px;
            z-index: 20;
            display: flex;
            flex-direction: column;
            gap: 7px;
        }

        .legend-row {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 11px;
            color: #64748b;
        }

        .legend-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
        }

        /* ── Graph elements ──────────────────────────────── */
        .link-path {
            fill: none;
            stroke-opacity: 0.3;
        }

        .node-g { cursor: pointer; }
        .node-g circle { transition: r 0.2s; }
        .node-g text {
            pointer-events: none;
            user-select: none;
            paint-order: stroke fill;
            stroke: #050508;
            stroke-width: 3px;
        }
    </style>
</head>
<body>

<!-- SIDEBAR -->
<div id="sidebar">
    <div class="sidebar-header">Nodes <span id="node-count"></span></div>
    <div class="node-list" id="node-list"></div>
</div>

<!-- CANVAS -->
<div id="canvas-wrapper">
    <div id="topbar">
        <button id="toggle-sidebar" title="Toggle sidebar">☰</button>
        <input id="search-box" type="text" placeholder="Search nodes…">
        <div class="top-stats">
            <div class="stat"><span class="val" id="stat-nodes">–</span> nodes</div>
            <div class="stat"><span class="val" id="stat-edges">–</span> edges</div>
        </div>
        <div class="top-btns">
            <button class="top-btn" onclick="centerGraph()">Center</button>
            <button class="top-btn" onclick="resetZoom()">Reset Zoom</button>
            <button class="top-btn" id="pause-btn" onclick="toggleSim()">Pause</button>
        </div>
    </div>

    <svg id="graph"></svg>

    <div id="tooltip"></div>

    <div id="legend">
        <div class="legend-row"><div class="legend-dot" style="background:#f97316"></div>Repository</div>
        <div class="legend-row"><div class="legend-dot" style="background:#22d3ee"></div>File/Module</div>
        <div class="legend-row"><div class="legend-dot" style="background:#a78bfa"></div>Class</div>
        <div class="legend-row"><div class="legend-dot" style="background:#4ade80"></div>Function</div>
        <div class="legend-row"><div class="legend-dot" style="background:#fb923c"></div>High Degree</div>
    </div>
</div>

<script>
const RAW = ${graphDataJson};

// ── One fixed colour per node type ─────────────────────────
const NODE_COLORS = {
    repository: '#f97316',   // orange
    file:       '#22d3ee',   // cyan
    module:     '#22d3ee',   // cyan (same as file)
    class:      '#a78bfa',   // violet
    function:   '#4ade80',   // green
    default:    '#f472b6'    // pink
};

// ── Edge type colours ─────────────────────────────────────────
const EDGE_COLORS = {
    calls:    '#f59e0b',  // amber  — execution flow
    contains: '#475569',  // slate  — structural hierarchy
    inherits: '#c084fc',  // purple — class inheritance
    imports:  '#38bdf8',  // sky    — module imports
    default:  '#7c3f1a',  // reddish-brown fallback
};

function edgeColor(e) {
    return EDGE_COLORS[(e.type || '').toLowerCase()] || EDGE_COLORS.default;
}

function nodeColor(d) {
    const type = (d.type || 'default').toLowerCase();
    return NODE_COLORS[type] || NODE_COLORS.default;
}

// ── Compute degree (connectivity) for node sizing ──────────
const degree = {};
RAW.nodes.forEach(n => { degree[n.id] = 0; });
RAW.edges.forEach(e => {
    const s = typeof e.source === 'object' ? e.source.id : e.source;
    const t = typeof e.target === 'object' ? e.target.id : e.target;
    degree[s] = (degree[s] || 0) + 1;
    degree[t] = (degree[t] || 0) + 1;
});

const maxDeg = Math.max(1, ...Object.values(degree));
const rScale = d3.scaleSqrt().domain([0, maxDeg]).range([4, 28]);

function nodeRadius(d) { return rScale(degree[d.id] || 0); }

// ── Sidebar population ─────────────────────────────────────
const nodeList = document.getElementById('node-list');
document.getElementById('node-count').textContent = RAW.nodes.length;
document.getElementById('stat-nodes').textContent = RAW.nodes.length;
document.getElementById('stat-edges').textContent  = RAW.edges.length;

const sortedNodes = [...RAW.nodes].sort((a,b) => (degree[b.id]||0) - (degree[a.id]||0));

sortedNodes.forEach(n => {
    const item = document.createElement('div');
    item.className = 'node-list-item';
    item.dataset.id = n.id;
    const dot = document.createElement('div');
    dot.className = 'node-dot';
    dot.style.background = nodeColor(n);
    item.appendChild(dot);
    const label = document.createElement('span');
    label.textContent = n.label || n.id;
    label.title = n.label || n.id;
    item.appendChild(label);
    item.addEventListener('click', () => focusNode(n.id));
    nodeList.appendChild(item);
});

// ── D3 Setup ───────────────────────────────────────────────
const svg = d3.select('#graph');
const g   = svg.append('g');
let W = () => document.getElementById('canvas-wrapper').clientWidth;
let H = () => document.getElementById('canvas-wrapper').clientHeight;

const zoom = d3.zoom()
    .scaleExtent([0.02, 8])
    .on('zoom', ev => g.attr('transform', ev.transform));

svg.call(zoom);

// Arrow markers — refX=0 because we clip the line endpoint to the node boundary
const defs = svg.append('defs');
function makeMarker(id, color) {
    defs.append('marker')
        .attr('id', id)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 0)          // endpoint IS the node boundary, so no extra offset
        .attr('refY', 0)
        .attr('markerWidth', 7)
        .attr('markerHeight', 7)
        .attr('orient', 'auto')
        .append('path')
            .attr('d', 'M0,-5L10,0L0,5Z')
            .attr('fill', color)
            .attr('opacity', 0.9);
}
// One marker per edge type — each coloured to match
Object.entries(EDGE_COLORS).forEach(([type, color]) => {
    makeMarker('arrow-' + type, color);
});

// ── Force simulation ───────────────────────────────────────
const sim = d3.forceSimulation(RAW.nodes)
    .force('link', d3.forceLink(RAW.edges).id(d => d.id).distance(d => {
        // longer distance for high-degree connectors so graph spreads like GitNexus
        const s = typeof d.source === 'object' ? d.source.id : d.source;
        const t = typeof d.target === 'object' ? d.target.id : d.target;
        return 60 + (degree[s] + degree[t]) * 3;
    }).strength(0.4))
    .force('charge', d3.forceManyBody().strength(d => -120 - (degree[d.id] || 0) * 8))
    .force('center', d3.forceCenter(W() / 2, H() / 2))
    .force('collision', d3.forceCollide().radius(d => nodeRadius(d) + 4))
    .alphaDecay(0.015);

// ── Draw links ─────────────────────────────────────────────
const linkG = g.append('g').attr('class', 'links');
const link = linkG.selectAll('line')
    .data(RAW.edges)
    .join('line')
    .attr('class', 'link-path')
    .attr('stroke', e => edgeColor(e))
    .attr('stroke-width', e => e.type === 'contains' ? 1.2 : 1.8)
    .attr('stroke-opacity', e => e.type === 'contains' ? 0.25 : 0.5)
    .attr('stroke-dasharray', e => e.type === 'imports' ? '5 3' : 'none')
    .attr('marker-end', e => {
        const t = (e.type || '').toLowerCase();
        const key = EDGE_COLORS[t] ? t : 'default';
        return 'url(#arrow-' + key + ')';
    });

// ── Draw nodes ─────────────────────────────────────────────
const nodeG = g.append('g').attr('class', 'nodes');
const node = nodeG.selectAll('g')
    .data(RAW.nodes)
    .join('g')
    .attr('class', 'node-g')
    .call(d3.drag()
        .on('start', (ev, d) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag',  (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
        .on('end',   (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
    )
    .on('mouseover', onMouseOver)
    .on('mouseout',  onMouseOut)
    .on('click',     onClick);

// Outer glow ring — wider + brighter for focus node (depth 0)
node.append('circle')
    .attr('r', d => {
        if (d.depth === 0) return nodeRadius(d) + 8;   // focus: big double-ring
        return nodeRadius(d) + 3;
    })
    .attr('fill', 'none')
    .attr('stroke', d => {
        if (d.depth === 0) return '#ffffff';        // focus = white ring
        if (d.depth !== undefined && d.depth < 0)  return '#fbbf24';  // upstream = amber
        if (d.depth !== undefined && d.depth > 0)  return '#22d3ee';  // downstream = cyan
        return nodeColor(d);
    })
    .attr('stroke-opacity', d => d.depth === 0 ? 0.7 : 0.22)
    .attr('stroke-width',   d => d.depth === 0 ? 2.5 : 1.5)
    .attr('stroke-dasharray', d => {
        // upstream nodes get a dashed upstream-indicator ring
        return (d.depth !== undefined && d.depth < 0) ? '4 3' : 'none';
    });

// Main filled circle
node.append('circle')
    .attr('class', 'main-circle')
    .attr('r', d => d.depth === 0 ? nodeRadius(d) + 2 : nodeRadius(d))
    .attr('fill', d => nodeColor(d))
    .attr('fill-opacity', d => {
        if (d.depth === 0) return 1.0;
        if (d.depth === undefined) return 0.9;
        // fade with each hop
        return Math.max(0.4, 1.0 - Math.abs(d.depth) * 0.12);
    });

// Label for larger nodes only, or all if small graph
node.append('text')
    .attr('x', d => nodeRadius(d) + 4)
    .attr('y', 4)
    .attr('font-size', d => Math.max(8, Math.min(12, nodeRadius(d) * 0.8)) + 'px')
    .attr('fill', '#cbd5e1')
    .attr('font-family', 'Inter, sans-serif')
    .text(d => d.label || d.id);

// ── Tick — compute clipped endpoints so arrows stop at node boundary ──
const ARROW_GAP = 2; // extra px gap between arrowhead tip and circle edge

sim.on('tick', () => {
    link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => {
            // Direction vector from source to target
            const dx = d.target.x - d.source.x;
            const dy = d.target.y - d.source.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist === 0) return d.target.x;
            // Stop at target node's circle edge + ARROW_GAP
            const r = nodeRadius(d.target) + ARROW_GAP;
            return d.target.x - (dx / dist) * r;
        })
        .attr('y2', d => {
            const dx = d.target.x - d.source.x;
            const dy = d.target.y - d.source.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist === 0) return d.target.y;
            const r = nodeRadius(d.target) + ARROW_GAP;
            return d.target.y - (dy / dist) * r;
        });

    node.attr('transform', d => \`translate(\${d.x},\${d.y})\`);
});

// ── Tooltip ────────────────────────────────────────────────
const tooltip = document.getElementById('tooltip');

// ── Edge hover tooltip ──────────────────────────────────────
const edgeTooltip = document.getElementById('tooltip');
link
    .on('mouseover', function(ev, e) {
        const col = edgeColor(e);
        const srcId = typeof e.source === 'object' ? e.source.id : e.source;
        const tgtId = typeof e.target === 'object' ? e.target.id : e.target;
        const srcLabel = RAW.nodes.find(n => n.id === srcId)?.label || srcId;
        const tgtLabel = RAW.nodes.find(n => n.id === tgtId)?.label || tgtId;
        edgeTooltip.style.opacity = '1';
        edgeTooltip.style.left = (ev.pageX + 14) + 'px';
        edgeTooltip.style.top  = (ev.pageY - 14) + 'px';
        edgeTooltip.innerHTML =
            '<div class="tt-name" style="color:' + col + '">' + (e.type || 'edge') + '</div>' +
            '<div class="tt-row"><strong>from</strong><span>' + srcLabel + '</span></div>' +
            '<div class="tt-row"><strong>to</strong><span>' + tgtLabel + '</span></div>' +
            '<div class="tt-badge" style="background:' + col + '22;color:' + col + ';border:1px solid ' + col + '55">' + (e.type || 'edge') + '</div>';
        d3.select(this).attr('stroke-width', 3).attr('stroke-opacity', 1);
    })
    .on('mouseout', function(ev, e) {
        edgeTooltip.style.opacity = '0';
        d3.select(this)
            .attr('stroke-width', e.type === 'contains' ? 1.2 : 1.8)
            .attr('stroke-opacity', e.type === 'contains' ? 0.25 : 0.5);
    });

function onMouseOver(ev, d) {
    const col = nodeColor(d);
    tooltip.style.opacity = '1';
    tooltip.style.left = (ev.pageX + 18) + 'px';
    tooltip.style.top  = (ev.pageY - 12) + 'px';
    tooltip.innerHTML = \`
        <div class="tt-name">\${d.label || d.id}</div>
        <div class="tt-row"><strong>Type</strong><span>\${d.type || '\u2013'}</span></div>
        \${d.file ? \`<div class="tt-row"><strong>File</strong><span>\${d.file}</span></div>\` : ''}
        \${d.line ? \`<div class="tt-row"><strong>Line</strong><span>\${d.line}</span></div>\` : ''}
        \${d.depth !== undefined ? \`<div class="tt-row"><strong>Hop</strong><span>\${d.depth === 0 ? 'focus' : (d.depth > 0 ? '+' + d.depth + ' downstream' : Math.abs(d.depth) + ' upstream')}</span></div>\` : ''}
        <div class="tt-row"><strong>Links</strong><span>\${degree[d.id] || 0} connections</span></div>
        <div class="tt-badge" style="background:\${col}22;color:\${col};border:1px solid \${col}44">\${d.type || 'node'}</div>
    \`;

    // Highlight connected
    const connected = new Set([d.id]);
    RAW.edges.forEach(e => {
        const s = typeof e.source === 'object' ? e.source.id : e.source;
        const t = typeof e.target === 'object' ? e.target.id : e.target;
        if (s === d.id || t === d.id) { connected.add(s); connected.add(t); }
    });

    node.transition().duration(150)
        .style('opacity', n => connected.has(n.id) ? 1 : 0.08);
    link.transition().duration(150)
        .attr('stroke-opacity', e => {
            const s = typeof e.source === 'object' ? e.source.id : e.source;
            const t = typeof e.target === 'object' ? e.target.id : e.target;
            return (s === d.id || t === d.id) ? 0.9 : 0.03;
        })
        .attr('stroke', e => {
            const s = typeof e.source === 'object' ? e.source.id : e.source;
            return (s === d.id || typeof e.target === 'object' ? e.target.id === d.id : e.target === d.id)
                ? edgeColor(e) : EDGE_COLORS.default;
        });
}

function onMouseOut() {
    tooltip.style.opacity = '0';
    node.transition().duration(200).style('opacity', 1);
    link.transition().duration(200)
        .attr('stroke-opacity', e => e.type === 'contains' ? 0.25 : 0.5)
        .attr('stroke', e => edgeColor(e));  // restore per-type colour
}

// ── Sidebar highlight on click ─────────────────────────────
function onClick(ev, d) {
    document.querySelectorAll('.node-list-item').forEach(el => el.classList.remove('active'));
    const el = document.querySelector(\`.node-list-item[data-id="\${d.id}"]\`);
    if (el) { el.classList.add('active'); el.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
}

function focusNode(id) {
    const d = RAW.nodes.find(n => n.id === id);
    if (!d || d.x === undefined) return;
    const cw = W(), ch = H();
    const s = 2;
    svg.transition().duration(600).call(
        zoom.transform,
        d3.zoomIdentity.translate(cw/2 - s*d.x, ch/2 - s*d.y).scale(s)
    );
    document.querySelectorAll('.node-list-item').forEach(el => el.classList.remove('active'));
    const el = document.querySelector(\`.node-list-item[data-id="\${id}"]\`);
    if (el) el.classList.add('active');
}

// ── Search ─────────────────────────────────────────────────
document.getElementById('search-box').addEventListener('input', ev => {
    const q = ev.target.value.trim().toLowerCase();
    if (!q) {
        node.transition().duration(200).style('opacity', 1);
        link.transition().duration(200).attr('stroke-opacity', 0.3);
        return;
    }
    const matched = new Set(RAW.nodes.filter(n => (n.label || n.id).toLowerCase().includes(q)).map(n => n.id));
    node.transition().duration(200).style('opacity', n => matched.has(n.id) ? 1 : 0.06);
    link.transition().duration(200).attr('stroke-opacity', e => {
        const s = typeof e.source === 'object' ? e.source.id : e.source;
        const t = typeof e.target === 'object' ? e.target.id : e.target;
        return (matched.has(s) && matched.has(t)) ? 0.5 : 0.03;
    });
});

// ── Controls ───────────────────────────────────────────────
function centerGraph() {
    const { x, y, width, height } = g.node().getBBox();
    if (!width || !height) return;
    const cw = W(), ch = H();
    const s = Math.min(0.9, Math.min(cw / width, ch / height)) * 0.85;
    const tx = cw/2 - s*(x + width/2);
    const ty = ch/2 - s*(y + height/2);
    svg.transition().duration(800).call(zoom.transform, d3.zoomIdentity.translate(tx,ty).scale(s));
}

function resetZoom() {
    svg.transition().duration(600).call(zoom.transform, d3.zoomIdentity.translate(W()/2, H()/2).scale(1));
}

let simRunning = true;
function toggleSim() {
    simRunning ? sim.stop() : sim.restart();
    simRunning = !simRunning;
    document.getElementById('pause-btn').textContent = simRunning ? 'Pause' : 'Resume';
}

document.getElementById('toggle-sidebar').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('collapsed');
});

// ── Initial center — fires exactly ONCE on first load ───────
let hasAutocentered = false;
let userHasZoomed   = false;  // set true the moment the user touches zoom/pan

// Mark user interaction on any zoom/pan so we never override it
svg.on('zoom.trackuser', () => { userHasZoomed = true; });

function autoCenter() {
    if (hasAutocentered || userHasZoomed) { return; }
    const bbox = g.node().getBBox();
    if (!bbox.width || !bbox.height) { return; }
    hasAutocentered = true;
    centerGraph();
}

// Fire once when simulation settles the first time
sim.on('end.autocenter', () => {
    autoCenter();
    sim.on('end.autocenter', null); // remove after first fire so drag-end never retriggers
});

// Fallback: also try 2 s in, in case graph is tiny and settles fast
setTimeout(autoCenter, 2000);

// On resize: just nudge the gravity centre — never reset the user's viewport
window.addEventListener('resize', () => {
    sim.force('center', d3.forceCenter(W()/2, H()/2));
    if (!hasAutocentered) { sim.alpha(0.05).restart(); }
});

</script>
</body>
</html>`;
    }
}
