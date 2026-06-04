import * as vscode from "vscode";
import { CgcService } from "../mcp/service";

export class CallGraphPanel {
  private panel?: vscode.WebviewPanel;

  constructor(private readonly service: CgcService) {}

  show(context: vscode.ExtensionContext, symbol?: string): void {
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel("cgc.callGraph", "CGC Call Graph", vscode.ViewColumn.Beside, {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [context.extensionUri]
      });
      this.panel.onDidDispose(() => {
        this.panel = undefined;
      });
      this.panel.webview.onDidReceiveMessage(async (msg: Record<string, unknown>) => {
        if (msg.type === "open-location" && msg.path) {
          const uri = vscode.Uri.file(msg.path as string);
          const doc = await vscode.workspace.openTextDocument(uri);
          const editor = await vscode.window.showTextDocument(doc, vscode.ViewColumn.One);
          if (msg.line) {
            const pos = new vscode.Position(Math.max(0, (msg.line as number) - 1), 0);
            editor.selection = new vscode.Selection(pos, pos);
            editor.revealRange(new vscode.Range(pos, pos));
          }
        }
        if (msg.type === "fetch-graph" && msg.symbol) {
          await this._refreshData(msg.symbol as string, (msg.depth as number) ?? 1);
        }
      });
    }

    this.panel.webview.html = this.renderHtml();
    this.panel.reveal();
    if (symbol) {
      // Let the panel render first, then push data
      setTimeout(() => this._refreshData(symbol, 1), 250);
    }
  }

  private async _refreshData(symbol: string, depth: number) {
    if (!this.panel) return;
    try {
      const [callers, callees] = await Promise.all([
        this.service.findCallers(symbol),
        depth > 1
          ? this.service.listCallees(symbol, undefined, depth)
          : this.service.runCypher(
              `MATCH (f:Function {name: "${symbol}"})-[r:CALLS]->(callee) RETURN callee.name as name, callee.file_path as path, r.line_number as line`
            )
      ]);

      const nodes: Array<Record<string, unknown>> = [{ id: symbol, name: symbol, type: "center" }];
      const links: Array<Record<string, unknown>> = [];

      callers.forEach(c => {
        let name = c.caller_name ?? "";
        if (!name || name === "unknown") {
          const fileName = c.caller_file_path ? c.caller_file_path.split("/").pop() : "unknown";
          name = `[Global] ${fileName}:${c.call_line_number ?? "?"}`;
        }
        if (!nodes.find(n => n["id"] === name)) {
          nodes.push({ id: name, name, path: c.caller_file_path ?? "", line: c.call_line_number ?? 1, type: "caller" });
        }
        links.push({ source: name, target: symbol, type: "CALLS" });
      });

      if (depth > 1) {
        // Multi-level graph from find_all_callees (which now returns edges)
        (callees as Array<Record<string, unknown>>).forEach(edge => {
          const sName = String(edge["caller_name"] ?? "");
          const tName = String(edge["callee_name"] ?? "");
          const sPath = String(edge["caller_path"] ?? "");
          const tPath = String(edge["callee_path"] ?? "");
          const line = Number(edge["line"] ?? 1);

          if (sName && !nodes.find(n => n["id"] === sName)) {
            nodes.push({ id: sName, name: sName, path: sPath, line: 1, type: sName === symbol ? "center" : "callee" });
          }
          if (tName && !nodes.find(n => n["id"] === tName)) {
            nodes.push({ id: tName, name: tName, path: tPath, line: line, type: "callee" });
          }
          if (sName && tName) {
            links.push({ source: sName, target: tName, type: "CALLS" });
          }
        });
      } else {
        // Single level graph
        (callees as Array<Record<string, unknown>>).forEach(c => {
          const rawName = c["name"] ?? c["called_name"] ?? "";
          let name = String(rawName);
          if (!name || name === "unknown") {
            const path = String(c["path"] ?? c["called_file_path"] ?? "");
            name = `[Anon] ${path.split("/").pop()}:${c["line"] ?? "?"}`;
          }
          if (!nodes.find(n => n["id"] === name)) {
            nodes.push({
              id: name,
              name,
              path: String(c["path"] ?? c["called_file_path"] ?? ""),
              line: c["line"] ?? c["called_line_number"] ?? 1,
              type: "callee"
            });
          }
          links.push({ source: symbol, target: name, type: "CALLS" });
        });
      }

      this.panel?.webview.postMessage({ type: "graph-data", symbol, nodes, links, depth });
    } catch (err) {
      this.panel?.webview.postMessage({ type: "error", message: String(err) });
    }
  }

  postEditorSelection(path: string, symbol: string): void {
    if (this.panel) {
      this._refreshData(symbol, 1);
    }
  }

  private renderHtml(): string {
    return `<!DOCTYPE html>
<html>
<head>
  <script src="https://d3js.org/d3.v7.min.js"></script>
  <style>
    :root {
      --bg: var(--vscode-editor-background);
      --text: var(--vscode-editor-foreground);
      --border: var(--vscode-widget-border, #454545);
      --node-center: #7C6AF7;
      --node-caller: #E3B341;
      --node-callee: #4EC9B0;
      --node-class:  #569CD6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: var(--vscode-font-family); overflow: hidden; }
    #graph { width: 100vw; height: 100vh; }

    /* ── Toolbar ── */
    #toolbar {
      position: absolute; top: 12px; left: 12px; right: 12px;
      display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
      padding: 8px 12px;
      background: rgba(0,0,0,0.45);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 10px;
      z-index: 10;
    }
    #toolbar .title { font-weight: 800; color: var(--node-center); font-size: 13px; white-space: nowrap; }
    #toolbar .sym   { font-family: monospace; font-size: 12px; opacity: 0.85; }
    #toolbar .sep   { width: 1px; height: 18px; background: var(--border); margin: 0 2px; }
    #toolbar label  { font-size: 11px; opacity: 0.65; white-space: nowrap; }

    .tb-btn {
      padding: 4px 10px; border: 1px solid var(--border); background: rgba(255,255,255,0.07);
      color: var(--text); border-radius: 6px; cursor: pointer; font-size: 11px;
      transition: background 0.15s;
    }
    .tb-btn:hover { background: rgba(255,255,255,0.14); }
    .tb-btn.active { background: var(--node-center); border-color: var(--node-center); color: #fff; }

    input[type=range] { width: 80px; accent-color: var(--node-center); }
    input[type=text]  {
      padding: 4px 8px; background: rgba(255,255,255,0.07); border: 1px solid var(--border);
      border-radius: 6px; color: var(--text); font-size: 11px; width: 140px;
    }
    input[type=text]::placeholder { opacity: 0.4; }

    /* ── Legend ── */
    #legend {
      position: absolute; bottom: 12px; left: 12px;
      display: flex; gap: 12px;
      padding: 6px 12px;
      background: rgba(0,0,0,0.4); backdrop-filter: blur(8px);
      border: 1px solid var(--border); border-radius: 8px;
      font-size: 10px; opacity: 0.8;
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 4px; }

    /* ── Context menu ── */
    #ctx-menu {
      position: absolute; display: none;
      background: var(--vscode-menu-background, #252526);
      border: 1px solid var(--border);
      border-radius: 6px; padding: 4px 0;
      z-index: 100; min-width: 160px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    }
    #ctx-menu.show { display: block; }
    .ctx-item {
      padding: 6px 14px; cursor: pointer; font-size: 12px;
      transition: background 0.1s;
    }
    .ctx-item:hover { background: var(--vscode-menu-selectionBackground, #094771); }

    /* ── Nodes & links ── */
    .node { cursor: pointer; transition: r 0.2s; }
    .label { font-size: 10px; pointer-events: none; fill: var(--text); font-weight: 600; }
    .link { stroke-opacity: 0.45; stroke-width: 1.5px; marker-end: url(#arrow); }

    /* ── Error/loading overlay ── */
    #overlay {
      position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
      font-size: 14px; opacity: 0.5; display: none; pointer-events: none;
    }
  </style>
</head>
<body>

<div id="toolbar">
  <span class="title">CGC CALL GRAPH</span>
  <span id="sym-label" class="sym">—</span>
  <div class="sep"></div>
  <label>Depth</label>
  <input type="range" id="depth-slider" min="1" max="5" value="1" oninput="onDepthChange(this.value)">
  <span id="depth-label" style="font-size:11px;min-width:12px">1</span>
  <div class="sep"></div>
  <button class="tb-btn active" id="btn-force" onclick="setLayout('force')">Force</button>
  <button class="tb-btn" id="btn-tree" onclick="setLayout('tree')">Tree</button>
  <button class="tb-btn" id="btn-radial" onclick="setLayout('radial')">Radial</button>
  <div class="sep"></div>
  <input type="text" id="filter-input" placeholder="Filter nodes…" oninput="applyFilter(this.value)">
  <div class="sep"></div>
  <button class="tb-btn" onclick="exportPng()" title="Export as PNG">⬇ PNG</button>
  <button class="tb-btn" onclick="resetView()" title="Reset zoom">⌖ Reset</button>
</div>

<div id="legend">
  <span><span class="dot" style="background:var(--node-caller)"></span>Caller</span>
  <span><span class="dot" style="background:var(--node-center)"></span>Target</span>
  <span><span class="dot" style="background:var(--node-callee)"></span>Callee</span>
</div>

<div id="ctx-menu">
  <div class="ctx-item" id="ctx-open">📄 Jump to file</div>
  <div class="ctx-item" id="ctx-center">🎯 Set as new center</div>
  <div class="ctx-item" id="ctx-expand">🔍 Expand (depth +1)</div>
</div>

<div id="overlay">Click a node to explore • Scroll to zoom • Drag to pan</div>
<svg id="graph"></svg>

<script>
const vscode = acquireVsCodeApi();
const svg = d3.select('#graph');
const W = () => window.innerWidth;
const H = () => window.innerHeight;

// Arrow marker
const defs = svg.append('defs');
defs.append('marker')
  .attr('id','arrow').attr('viewBox','-0 -5 10 10').attr('refX',20).attr('refY',0)
  .attr('orient','auto').attr('markerWidth',5).attr('markerHeight',5)
  .append('path').attr('d','M 0,-5 L 10,0 L 0,5')
  .attr('fill','var(--border)').style('stroke','none');

const zoomBehavior = d3.zoom().scaleExtent([0.1, 8]).on('zoom', e => g.attr('transform', e.transform));
svg.call(zoomBehavior);
const g = svg.append('g');

let simulation = d3.forceSimulation()
  .force('link', d3.forceLink().id(d => d.id).distance(130))
  .force('charge', d3.forceManyBody().strength(-500))
  .force('center', d3.forceCenter(W()/2, H()/2))
  .force('collision', d3.forceCollide().radius(45));

let currentLayout = 'force';
let currentNodes = [];
let currentLinks = [];
let currentSymbol = '';
let currentDepth = 1;
let ctxNode = null;

// ── Depth slider ──────────────────────────────────────────────────────────────
function onDepthChange(val) {
  document.getElementById('depth-label').textContent = val;
  currentDepth = Number(val);
  if (currentSymbol) {
    vscode.postMessage({ type: 'fetch-graph', symbol: currentSymbol, depth: currentDepth });
  }
}

// ── Layout ────────────────────────────────────────────────────────────────────
function setLayout(mode) {
  currentLayout = mode;
  document.querySelectorAll('.tb-btn[id^=btn-]').forEach(b => b.classList.remove('active'));
  document.getElementById('btn-' + mode)?.classList.add('active');
  if (currentNodes.length) renderGraph(currentNodes, currentLinks);
}

// ── Filter ────────────────────────────────────────────────────────────────────
function applyFilter(text) {
  const q = text.toLowerCase();
  g.selectAll('.node').attr('opacity', d => (!q || d.name.toLowerCase().includes(q)) ? 1 : 0.15);
  g.selectAll('.label').attr('opacity', d => (!q || d.name.toLowerCase().includes(q)) ? 1 : 0.1);
}

// ── Context menu ──────────────────────────────────────────────────────────────
const ctxMenu = document.getElementById('ctx-menu');
document.addEventListener('click', () => ctxMenu.classList.remove('show'));

document.getElementById('ctx-open').onclick = () => {
  if (ctxNode?.path) vscode.postMessage({ type:'open-location', path: ctxNode.path, line: ctxNode.line });
  ctxMenu.classList.remove('show');
};
document.getElementById('ctx-center').onclick = () => {
  if (ctxNode?.name) {
    currentSymbol = ctxNode.name;
    document.getElementById('sym-label').textContent = currentSymbol;
    vscode.postMessage({ type:'fetch-graph', symbol: currentSymbol, depth: currentDepth });
  }
  ctxMenu.classList.remove('show');
};
document.getElementById('ctx-expand').onclick = () => {
  if (ctxNode?.name) {
    currentDepth = Math.min(5, currentDepth + 1);
    document.getElementById('depth-slider').value = currentDepth;
    document.getElementById('depth-label').textContent = currentDepth;
    vscode.postMessage({ type:'fetch-graph', symbol: ctxNode.name, depth: currentDepth });
  }
  ctxMenu.classList.remove('show');
};

// ── Main graph renderer ───────────────────────────────────────────────────────
function renderGraph(nodes, links) {
  currentNodes = nodes;
  currentLinks = links;
  g.selectAll('*').remove();
  simulation.stop();

  if (nodes.length === 0) {
    document.getElementById('overlay').style.display = 'block';
    return;
  }
  document.getElementById('overlay').style.display = 'none';

  const link = g.append('g').selectAll('line').data(links).enter().append('line')
    .attr('class','link')
    .attr('stroke', d => d.type === 'INHERITS' ? '#569CD6' : 'var(--border)');

  const nodeGroup = g.append('g').selectAll('g').data(nodes).enter().append('g')
    .attr('class','node-group')
    .call(d3.drag().on('start', dstart).on('drag', ddrag).on('end', dend))
    .on('click', (event, d) => {
      if (d.path) vscode.postMessage({ type:'open-location', path: d.path, line: d.line });
    })
    .on('contextmenu', (event, d) => {
      event.preventDefault();
      ctxNode = d;
      ctxMenu.style.left = event.pageX + 'px';
      ctxMenu.style.top = event.pageY + 'px';
      ctxMenu.classList.add('show');
    });

  nodeGroup.append('circle')
    .attr('class','node')
    .attr('r', d => d.type === 'center' ? 13 : 8)
    .attr('fill', d => {
      if (d.type === 'center') return 'var(--node-center)';
      if (d.type === 'caller') return 'var(--node-caller)';
      if (d.type === 'class')  return 'var(--node-class)';
      return 'var(--node-callee)';
    })
    .attr('stroke', 'var(--bg)')
    .attr('stroke-width', 2)
    .on('mouseenter', function(e, d) {
      d3.select(this).transition().duration(120).attr('r', d.type === 'center' ? 17 : 11)
        .attr('filter', 'drop-shadow(0 0 6px currentColor)');
    })
    .on('mouseleave', function(e, d) {
      d3.select(this).transition().duration(120).attr('r', d.type === 'center' ? 13 : 8)
        .attr('filter', null);
    });

  nodeGroup.append('text')
    .attr('class','label')
    .attr('dy', d => d.type === 'center' ? -18 : -13)
    .attr('text-anchor','middle')
    .text(d => d.name.length > 20 ? d.name.slice(0,18)+'…' : d.name);

  if (currentLayout === 'force') {
    simulation.nodes(nodes).on('tick', () => {
      link.attr('x1', d=>d.source.x).attr('y1',d=>d.source.y)
          .attr('x2', d=>d.target.x).attr('y2',d=>d.target.y);
      nodeGroup.attr('transform', d=>\`translate(\${d.x},\${d.y})\`);
    });
    simulation.force('link').links(links);
    simulation.alpha(1).restart();

  } else if (currentLayout === 'tree') {
    // Hierarchical layout via d3-tree
    const stratify = d3.stratify().id(d=>d.id).parentId(d => {
      const l = links.find(lk => lk.target === d.id || (lk.target && lk.target.id === d.id));
      return l ? (l.source.id ?? l.source) : null;
    });
    try {
      const root = stratify(nodes);
      const treeFn = d3.tree().size([W() - 200, H() - 200]);
      treeFn(root);
      nodeGroup.attr('transform', d => {
        const n = root.descendants().find(x=>x.id===d.id);
        return n ? \`translate(\${n.x+100},\${n.y+80})\` : 'translate(0,0)';
      });
      link.attr('x1', d => {
        const s = root.descendants().find(x=>x.id===(d.source.id??d.source));
        return s ? s.x+100 : 0;
      }).attr('y1', d => {
        const s = root.descendants().find(x=>x.id===(d.source.id??d.source));
        return s ? s.y+80 : 0;
      }).attr('x2', d => {
        const t = root.descendants().find(x=>x.id===(d.target.id??d.target));
        return t ? t.x+100 : 0;
      }).attr('y2', d => {
        const t = root.descendants().find(x=>x.id===(d.target.id??d.target));
        return t ? t.y+80 : 0;
      });
    } catch {
      // Fall back to force if stratify fails (cycles)
      setLayout('force');
    }

  } else if (currentLayout === 'radial') {
    const cx = W()/2, cy = H()/2;
    const angleStep = (2 * Math.PI) / Math.max(nodes.length - 1, 1);
    const radius = Math.min(W(), H()) * 0.35;
    nodes.forEach((n, i) => {
      if (n.type === 'center') { n.x = cx; n.y = cy; }
      else { n.x = cx + radius * Math.cos(i * angleStep); n.y = cy + radius * Math.sin(i * angleStep); }
    });
    nodeGroup.attr('transform', d=>\`translate(\${d.x},\${d.y})\`);
    link.attr('x1',d=>d.source.x??cx).attr('y1',d=>d.source.y??cy)
        .attr('x2',d=>d.target.x??cx).attr('y2',d=>d.target.y??cy);
  }
}

// ── Drag helpers ──────────────────────────────────────────────────────────────
function dstart(e,d){ if(!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }
function ddrag(e,d){ d.fx=e.x; d.fy=e.y; }
function dend(e,d){ if(!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; }

// ── Zoom reset ────────────────────────────────────────────────────────────────
function resetView() {
  svg.transition().duration(400).call(zoomBehavior.transform, d3.zoomIdentity);
}

// ── Export PNG ────────────────────────────────────────────────────────────────
function exportPng() {
  const svgEl = document.getElementById('graph');
  const serializer = new XMLSerializer();
  const source = serializer.serializeToString(svgEl);
  const img = new Image();
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(source);
  img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = svgEl.clientWidth; canvas.height = svgEl.clientHeight;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#1e1e1e';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0);
    const a = document.createElement('a');
    a.download = (currentSymbol || 'cgc-graph') + '.png';
    a.href = canvas.toDataURL('image/png');
    a.click();
  };
  img.src = url;
}

// ── Message handler ───────────────────────────────────────────────────────────
window.addEventListener('message', event => {
  const msg = event.data;
  if (msg.type === 'graph-data') {
    currentSymbol = msg.symbol;
    document.getElementById('sym-label').textContent = msg.symbol;
    renderGraph(msg.nodes, msg.links);
  }
  if (msg.type === 'error') {
    document.getElementById('overlay').textContent = 'Error: ' + msg.message;
    document.getElementById('overlay').style.display = 'block';
  }
});

// Initial hint
document.getElementById('overlay').style.display = 'block';
document.getElementById('overlay').textContent = 'Hover a symbol in the editor or select a function to explore its call graph';
window.addEventListener('resize', () => {
  simulation.force('center', d3.forceCenter(W()/2, H()/2));
  if (currentLayout === 'force') simulation.alpha(0.3).restart();
});
</script>
</body>
</html>`;
  }
}
