import * as vscode from "vscode";
import { CgcService } from "../mcp/service";

export class CallGraphPanel {
  private panel?: vscode.WebviewPanel;

  constructor(private readonly service: CgcService) {}

  show(context: vscode.ExtensionContext, symbol?: string): void {
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel("cgc.callGraph", "CGC Call Graph", vscode.ViewColumn.Beside, {
        enableScripts: true,
        retainContextWhenHidden: true
      });
      this.panel.onDidDispose(() => {
        this.panel = undefined;
      });
      this.panel.webview.onDidReceiveMessage(async (msg: any) => {
        if (msg.type === "open-location" && msg.path) {
          const uri = vscode.Uri.file(msg.path);
          const doc = await vscode.workspace.openTextDocument(uri);
          const editor = await vscode.window.showTextDocument(doc, vscode.ViewColumn.One);
          if (msg.line) {
            const pos = new vscode.Position(Math.max(0, msg.line - 1), 0);
            editor.selection = new vscode.Selection(pos, pos);
            editor.revealRange(new vscode.Range(pos, pos));
          }
        }
      });
    }

    this.panel.webview.html = this.renderHtml();
    this.panel.reveal();
    if (symbol) {
      this._refreshData(symbol);
    }
  }

  private async _refreshData(symbol: string) {
    if (!this.panel) return;
    try {
      // Fetch both callers and callees for a more complete picture
      const [callers, callees] = await Promise.all([
        this.service.findCallers(symbol),
        this.service.runCypher(`MATCH (f:Function {name: "${symbol}"})-[r:CALLS]->(callee) RETURN callee.name as name, callee.file_path as path, r.line_number as line`)
      ]);

      const nodes: any[] = [{ id: symbol, name: symbol, type: 'center' }];
      const links: any[] = [];

      callers.forEach(c => {
        let name = c.caller_name || '';
        if (!name || name === 'unknown') {
          const fileName = c.caller_file_path ? c.caller_file_path.split('/').pop() : 'unknown';
          name = `[Global] ${fileName}:${c.call_line_number || '?'}`;
        }
        const callerId = name;
        if (!nodes.find(n => n.id === callerId)) {
          nodes.push({ 
            id: callerId,
            name: name, 
            path: c.caller_file_path || '', 
            line: c.call_line_number || 1,
            type: 'caller'
          });
        }
        links.push({ source: callerId, target: symbol, type: 'CALLS' });
      });

      (callees as any[]).forEach(c => {
        let name = c.name || '';
        if (!name || name === 'unknown') {
          const fileName = c.path ? c.path.split('/').pop() : 'unknown';
          name = `[Anon] ${fileName}:${c.line || '?'}`;
        }
        const calleeId = name;
        if (!nodes.find(n => n.id === calleeId)) {
          nodes.push({ 
            id: calleeId,
            name: name, 
            path: c.path || '', 
            line: c.line || 1,
            type: 'callee'
          });
        }
        links.push({ source: symbol, target: calleeId, type: 'CALLS' });
      });

      this.panel.webview.postMessage({ type: 'graph-data', symbol, nodes, links });
    } catch (err) {
      this.panel.webview.postMessage({ type: 'error', message: String(err) });
    }
  }

  postEditorSelection(path: string, symbol: string): void {
    if (this.panel) {
        this._refreshData(symbol);
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
      --accent: var(--vscode-button-background);
      --node-center: #007acc;
      --node-caller: #ffca28;
      --node-callee: #4ec9b0;
      --link: var(--vscode-widget-border);
    }
    body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--vscode-font-family); overflow: hidden; }
    #graph { width: 100vw; height: 100vh; }
    .label { font-size: 10px; pointer-events: none; fill: var(--text); opacity: 0.8; font-weight: bold; }
    .node { cursor: pointer; stroke: var(--bg); stroke-width: 2px; transition: r 0.2s; }
    .node:hover { r: 10; }
    .link { stroke: var(--link); stroke-opacity: 0.4; stroke-width: 2px; marker-end: url(#arrowhead); }
    .overlay { 
      position: absolute; top: 16px; left: 16px; 
      padding: 8px 12px; background: rgba(0,0,0,0.3); 
      backdrop-filter: blur(8px); border-radius: 8px; 
      border: 1px solid var(--link); font-size: 12px;
    }
    .legend { display: flex; gap: 12px; margin-top: 4px; font-size: 10px; opacity: 0.7; }
    .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  </style>
</head>
<body>
  <div class="overlay">
    <div style="font-weight: 800; color: var(--node-center); margin-bottom: 2px;">CGC CALL GRAPH</div>
    <div id="target-name" style="font-family: monospace;">-</div>
    <div class="legend">
      <span><span class="dot" style="background: var(--node-caller)"></span> Caller</span>
      <span><span class="dot" style="background: var(--node-center)"></span> Target</span>
      <span><span class="dot" style="background: var(--node-callee)"></span> Callee</span>
    </div>
  </div>
  <svg id="graph"></svg>

  <script>
    const vscode = acquireVsCodeApi();
    const svg = d3.select("#graph");
    const width = window.innerWidth;
    const height = window.innerHeight;

    // Define arrowheads
    svg.append("defs").append("marker")
      .attr("id", "arrowhead")
      .attr("viewBox", "-0 -5 10 10")
      .attr("refX", 20)
      .attr("refY", 0)
      .attr("orient", "auto")
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("xoverflow", "visible")
      .append("svg:path")
      .attr("d", "M 0,-5 L 10 ,0 L 0,5")
      .attr("fill", "var(--link)")
      .style("stroke", "none");

    let simulation = d3.forceSimulation()
      .force("link", d3.forceLink().id(d => d.id).distance(120))
      .force("charge", d3.forceManyBody().strength(-400))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(40));

    const g = svg.append("g");

    svg.call(d3.zoom().on("zoom", (event) => {
      g.attr("transform", event.transform);
    }));

    window.addEventListener('message', event => {
      const msg = event.data;
      if (msg.type === 'graph-data') {
        document.getElementById('target-name').textContent = msg.symbol;
        updateGraph(msg.nodes, msg.links);
      }
    });

    function updateGraph(nodes, links) {
      g.selectAll("*").remove();

      const link = g.append("g")
        .selectAll("line")
        .data(links)
        .enter().append("line")
        .attr("class", "link");

      const node = g.append("g")
        .selectAll("circle")
        .data(nodes)
        .enter().append("circle")
        .attr("class", "node")
        .attr("r", d => d.type === 'center' ? 10 : 7)
        .attr("fill", d => {
          if (d.type === 'center') return 'var(--node-center)';
          if (d.type === 'caller') return 'var(--node-caller)';
          return 'var(--node-callee)';
        })
        .on("click", (event, d) => {
          if (d.path) {
            vscode.postMessage({ type: 'open-location', path: d.path, line: d.line });
          }
        })
        .call(d3.drag()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended));

      const label = g.append("g")
        .selectAll("text")
        .data(nodes)
        .enter().append("text")
        .attr("class", "label")
        .attr("dy", d => d.type === 'center' ? -15 : -12)
        .attr("text-anchor", "middle")
        .text(d => d.name);

      simulation.nodes(nodes).on("tick", () => {
        link
          .attr("x1", d => d.source.x)
          .attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x)
          .attr("y2", d => d.target.y);

        node
          .attr("cx", d => d.x)
          .attr("cy", d => d.y);

        label
          .attr("x", d => d.x)
          .attr("y", d => d.y);
      });

      simulation.force("link").links(links);
      simulation.alpha(1).restart();
    }

    function dragstarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event, d) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }
  </script>
</body>
</html>`;
  }
}
