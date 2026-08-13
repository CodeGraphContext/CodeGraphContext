import JSZip from "jszip";

async function fetchD3(): Promise<string> {
  const res = await fetch('https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js');
  if (!res.ok) throw new Error('Failed to fetch d3 for bundling');
  return res.text();
}

interface GraphNode {
  id: string | number;
  name: string;
  type: string;
  file?: string;
  val?: number;
  properties?: Record<string, any>;
  color?: string;
}

interface GraphLink {
  id?: string;
  source: string | number | { id: string | number };
  target: string | number | { id: string | number };
  type: string;
}

interface GraphMetadata {
  repo?: string;
  branch?: string;
  commit?: string;
  version?: string;
  [key: string]: any;
}

/* ── Shared CSS for both modes ─────────────────────────────────────── */
const SHARED_CSS = `
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body, html { width: 100%; height: 100%; overflow: hidden; background: #020202; font-family: Inter, system-ui, -apple-system, sans-serif; color: #e2e8f0; }
    #controls {
      position: absolute; top: 16px; right: 16px; z-index: 100;
      display: flex; gap: 8px;
    }
    .btn {
      background: rgba(0,0,0,0.4); color: #e2e8f0;
      border: 1px solid rgba(255,255,255,0.1);
      padding: 8px 16px; cursor: pointer; border-radius: 9999px;
      font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
      font-family: Inter, system-ui, sans-serif;
      backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
      transition: all 0.2s ease; outline: none;
    }
    .btn:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.2); }
    .btn.active { background: rgba(59,130,246,0.15); border-color: rgba(59,130,246,0.4); color: #93c5fd; }
    #tooltip {
      position: absolute; display: none;
      background: rgba(10,10,18,0.95); color: #fff;
      padding: 8px 14px; border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.08);
      pointer-events: none; z-index: 200;
      font-size: 12px; font-weight: 500;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
      backdrop-filter: blur(8px);
    }
    #legend {
      position: absolute; bottom: 16px; left: 16px; z-index: 100;
      background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.06);
      border-radius: 12px; padding: 12px 16px;
      backdrop-filter: blur(12px); max-height: 40vh; overflow-y: auto;
    }
    .leg-item { display: flex; align-items: center; gap: 8px; margin: 3px 0; }
    .leg-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .leg-lbl { font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
    .leg-cnt { font-size: 10px; color: #444; margin-left: auto; }
`;

/* ── Classic Mode: d3-force + Canvas (same engine as the website) ── */
function generateClassicHTML(
  dataJson: string,
  nodeColorsJson: string,
  edgeColorsJson: string,
  d3Bundle: string
): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Interactive Code Graph</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>${SHARED_CSS}
    canvas { display: block; }
  </style>
</head>
<body>
  <div id="controls">
    <button class="btn active" id="btn-layout">Stop Layout</button>
    <button class="btn" id="btn-reset">Reset View</button>
  </div>
  <div id="tooltip"></div>
  <div id="legend"></div>
  <canvas id="canvas"></canvas>
  ${d3Bundle ? `<script>${d3Bundle}</script>` : `<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>`}
  <script>
  (function() {
    var rawData = ${dataJson};
    var NC = ${nodeColorsJson};
    var EC = ${edgeColorsJson};

    var nodes = rawData.nodes;
    var links = rawData.links;
    var canvas = document.getElementById('canvas');
    var ctx = canvas.getContext('2d');
    var W = window.innerWidth, H = window.innerHeight;
    canvas.width = W; canvas.height = H;

    /* sizing — matches website logic */
    var N = nodes.length;
    var nScale = N > 3000 ? 0.3 : N > 1000 ? 0.5 : N > 400 ? 0.7 : 1.0;
    var nSize = 3.0;

    /* force simulation — same params as ForceGraph2D on the website */
    var sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(function(d){return d.id}).distance(30).strength(0.3))
      .force('charge', d3.forceManyBody().strength(N > 1000 ? -15 : -30))
      .force('center', d3.forceCenter(0, 0))
      .force('collision', d3.forceCollide().radius(function(d){return Math.max(2,(d.val||1)*0.8*nSize*nScale)}))
      .velocityDecay(0.4)
      .alphaDecay(0.05)
      .on('tick', render);

    var tx = W/2, ty = H/2, tk = 1;
    var hovered = null;

    function rgba(hex, a) {
      if (!hex || hex[0] !== '#') return 'rgba(100,100,100,' + a + ')';
      var r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
      return 'rgba('+r+','+g+','+b+','+a+')';
    }

    function render() {
      ctx.clearRect(0,0,W,H);
      ctx.fillStyle = '#020202';
      ctx.fillRect(0,0,W,H);
      ctx.save();
      ctx.translate(tx,ty);
      ctx.scale(tk,tk);
      var gs = tk;

      /* draw links */
      for (var i = 0; i < links.length; i++) {
        var l = links[i], s = l.source, t = l.target;
        if (!s || !t || !isFinite(s.x) || !isFinite(t.x)) continue;
        ctx.beginPath();
        ctx.moveTo(s.x,s.y);
        ctx.lineTo(t.x,t.y);
        ctx.strokeStyle = rgba(EC[l.type] || '#ffffff', 0.25);
        ctx.lineWidth = Math.max(0.15, 0.5 / gs);
        ctx.stroke();
      }

      /* draw nodes */
      for (var i = 0; i < nodes.length; i++) {
        var nd = nodes[i];
        if (!isFinite(nd.x) || !isFinite(nd.y)) continue;
        var col = NC[nd.type] || NC.Other || '#42a5f5';
        var r = Math.max(0.5, (nd.val||1) * 0.8 * nSize * nScale);
        var isH = hovered && nd.id === hovered.id;

        /* hover halo */
        if (isH) {
          ctx.beginPath();
          ctx.arc(nd.x, nd.y, r*2.5, 0, 6.283);
          ctx.fillStyle = rgba(col, 0.3);
          ctx.fill();
        }

        /* circle */
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, r, 0, 6.283);
        ctx.fillStyle = col;
        ctx.fill();

        /* label */
        var showLbl = isH || gs > 2.0;
        if (showLbl && nd.name) {
          var fs = Math.max(2, Math.round((isH ? 14 : 10) / gs));
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = isH ? '#ffffff' : '#c0c0c0';
          ctx.font = (isH ? 'bold ' : '') + fs + 'px Inter,sans-serif';
          ctx.shadowColor = '#000'; ctx.shadowBlur = 4;
          ctx.fillText(nd.name, nd.x, nd.y + r + fs/2 + 4);
          ctx.shadowBlur = 0;
        }
      }
      ctx.restore();
    }

    /* d3-zoom for pan/zoom */
    var zoomBeh = d3.zoom().scaleExtent([0.01,100])
      .on('zoom', function(e){ tx=e.transform.x; ty=e.transform.y; tk=e.transform.k; render(); });
    d3.select(canvas).call(zoomBeh).call(zoomBeh.transform, d3.zoomIdentity.translate(W/2,H/2));

    /* hover detection */
    canvas.addEventListener('mousemove', function(e) {
      var mx = (e.clientX - tx)/tk, my = (e.clientY - ty)/tk;
      var found = null, best = Infinity;
      for (var i = 0; i < nodes.length; i++) {
        var nd = nodes[i];
        if (!isFinite(nd.x)) continue;
        var rr = Math.max(3, (nd.val||1)*0.8*nSize*nScale);
        var dd = Math.hypot(nd.x-mx, nd.y-my);
        if (dd < rr*1.5 && dd < best) { found = nd; best = dd; }
      }
      if (found !== hovered) { hovered = found; if (sim.alpha() < 0.01) render(); }
      canvas.style.cursor = found ? 'pointer' : 'grab';
      var tip = document.getElementById('tooltip');
      if (found) {
        var c = NC[found.type] || '#42a5f5';
        tip.innerHTML = '<strong>' + (found.name||'?') + '</strong><br><span style="color:'+c+';font-size:10px;text-transform:uppercase;letter-spacing:0.05em;font-weight:700">' + found.type + '</span>';
        tip.style.display = 'block';
        tip.style.left = (e.clientX+15)+'px';
        tip.style.top = (e.clientY+15)+'px';
      } else { tip.style.display = 'none'; }
    });

    /* layout toggle */
    var running = true;
    document.getElementById('btn-layout').addEventListener('click', function(){
      if (running) { sim.stop(); running=false; this.textContent='Start Layout'; this.classList.remove('active'); }
      else { sim.alpha(1).restart(); running=true; this.textContent='Stop Layout'; this.classList.add('active'); }
    });

    /* reset view */
    document.getElementById('btn-reset').addEventListener('click', function(){
      d3.select(canvas).transition().duration(500).call(zoomBeh.transform, d3.zoomIdentity.translate(W/2,H/2));
    });

    /* resize */
    window.addEventListener('resize', function(){ W=innerWidth; H=innerHeight; canvas.width=W; canvas.height=H; render(); });

    /* legend */
    var types = {};
    nodes.forEach(function(n){ types[n.type] = (types[n.type]||0)+1; });
    var leg = document.getElementById('legend');
    leg.innerHTML = Object.entries(types).sort(function(a,b){return b[1]-a[1]}).map(function(e){
      var c = NC[e[0]] || '#42a5f5';
      return '<div class="leg-item"><span class="leg-dot" style="background:'+c+'"></span><span class="leg-lbl">'+e[0]+'</span><span class="leg-cnt">'+e[1]+'</span></div>';
    }).join('');
  })();
  </script>
</body>
</html>`;
}

/* ── Flowchart Mode: Vanilla JS tree layout + SVG ──────────────────── */
function generateFlowchartHTML(
  dataJson: string,
  nodeColorsJson: string,
  edgeColorsJson: string,
  d3Bundle: string
): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Interactive Flowchart</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>${SHARED_CSS}
    svg { display: block; background: #020202; }
    .node-body { transition: fill 0.15s; }
    .node-body:hover { fill: #181822 !important; }
    .expand-btn { cursor: pointer; }
    .expand-btn:hover rect { fill-opacity: 0.3; }
    #orphan-btn {
      position: absolute; bottom: 16px; right: 16px; z-index: 10;
      padding: 6px 18px; border-radius: 9999px;
      background: rgba(17,17,24,0.9); color: #888;
      border: 1px solid rgba(255,255,255,0.1);
      font-size: 10px; font-weight: 700; letter-spacing: 0.06em;
      cursor: pointer; backdrop-filter: blur(8px);
      transition: all 0.2s;
    }
    #orphan-btn.active { background: rgba(30,30,46,0.9); border-color: rgba(245,158,11,0.35); color: #f59e0b; }
  </style>
</head>
<body>
  <div id="controls">
    <button class="btn" id="btn-reset">Reset View</button>
  </div>
  <div id="tooltip"></div>
  <div id="legend"></div>
  <svg id="chart"></svg>
  ${d3Bundle ? `<script>${d3Bundle}</script>` : `<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>`}
  <script>
  (function() {
    var rawData = ${dataJson};
    var NC = ${nodeColorsJson};
    var EC = ${edgeColorsJson};

    var NODE_W = 200, NODE_H = 40, LEVEL_GAP = 280, NODE_GAP = 16, SLOT_R = 3.5;
    var nodes = rawData.nodes;
    var links = rawData.links;

    var W = window.innerWidth, H = window.innerHeight;
    var svg = d3.select('#chart').attr('width', W).attr('height', H);

    /* build containment tree */
    var nodeMap = new Map(nodes.map(function(n){return [String(n.id), n]}));
    var childMap = new Map();
    var parentMap = new Map();
    var crossLinks = [];

    links.forEach(function(l) {
      var s = String(l.source), t = String(l.target);
      if (l.type === 'CONTAINS') {
        if (!childMap.has(s)) childMap.set(s, []);
        childMap.get(s).push(t);
        parentMap.set(t, s);
      } else { crossLinks.push({source:s, target:t, type:l.type}); }
    });

    var roots = nodes.filter(function(n){return !parentMap.has(String(n.id))}).map(function(n){return String(n.id)});
    var orphanIds = new Set(roots.filter(function(r){ return !(childMap.get(r)||[]).some(function(k){return nodeMap.has(k)}); }));
    var expanded = new Set(roots);
    var positions = new Map();
    var showOrphans = false;

    /* compute visible nodes */
    function getVisible() {
      var vis = new Set();
      var q = roots.slice();
      while (q.length) {
        var id = q.shift();
        if (!nodeMap.has(id)) continue;
        if (orphanIds.has(id) && !showOrphans) continue;
        vis.add(id);
        if (expanded.has(id)) {
          var kids = childMap.get(id) || [];
          kids.forEach(function(k){ if(nodeMap.has(k)) q.push(k); });
        }
      }
      return vis;
    }

    function hasKids(id) { return (childMap.get(id)||[]).some(function(k){return nodeMap.has(k)}); }
    function kidCount(id) { return (childMap.get(id)||[]).filter(function(k){return nodeMap.has(k)}).length; }

    /* layout */
    function doLayout() {
      var vis = getVisible();
      positions = new Map();

      function subtreeH(id) {
        if (!expanded.has(id) || !vis.has(id)) return NODE_H;
        var kids = (childMap.get(id)||[]).filter(function(k){return vis.has(k)});
        if (!kids.length) return NODE_H;
        return kids.reduce(function(s,k){return s + subtreeH(k) + NODE_GAP}, -NODE_GAP);
      }

      function place(id, x, yCenter) {
        positions.set(id, {x: x, y: yCenter - NODE_H/2});
        if (!expanded.has(id)) return;
        var kids = (childMap.get(id)||[]).filter(function(k){return vis.has(k)});
        if (!kids.length) return;
        var total = subtreeH(id);
        var oy = yCenter - total/2;
        kids.forEach(function(kid) {
          var kh = subtreeH(kid);
          place(kid, x + LEVEL_GAP, oy + kh/2);
          oy += kh + NODE_GAP;
        });
      }

      var treeRoots = roots.filter(function(r){return vis.has(r) && !orphanIds.has(r)});
      var totalH = treeRoots.reduce(function(s,r){ return s + subtreeH(r) + NODE_GAP*3; }, 0);
      var y = -totalH/2;
      treeRoots.forEach(function(r) {
        var rh = subtreeH(r);
        place(r, 40, y + rh/2);
        y += rh + NODE_GAP*3;
      });

      if (showOrphans) {
        var orphans = roots.filter(function(r){return orphanIds.has(r) && vis.has(r)});
        var maxX = 40;
        positions.forEach(function(p) { if (p.x + NODE_W > maxX) maxX = p.x + NODE_W; });
        var orphanStartX = maxX + LEVEL_GAP;
        var COLS = 2, COL_W = NODE_W + 20, ROW_H = NODE_H + NODE_GAP, gridTop = -totalH/2;
        for (var i = 0; i < orphans.length; i++) {
          var col = i % COLS, row = Math.floor(i / COLS);
          positions.set(orphans[i], { x: orphanStartX + col * COL_W, y: gridTop + row * ROW_H });
        }
      }

      return vis;
    }

    /* rendering */
    /* defs */
    var defs = svg.append('defs');
    defs.append('filter').attr('id','glow').attr('x','-20%').attr('y','-20%').attr('width','140%').attr('height','140%')
      .append('feGaussianBlur').attr('stdDeviation','3').attr('result','blur');
    /* grid pattern */
    var pat = defs.append('pattern').attr('id','grid').attr('width',40).attr('height',40).attr('patternUnits','userSpaceOnUse');
    pat.append('path').attr('d','M 40 0 L 0 0 0 40').attr('fill','none').attr('stroke','#0d0d14').attr('stroke-width',0.6);

    svg.append('rect').attr('width',W).attr('height',H).attr('fill','url(#grid)').style('pointer-events','none');
    var gMain = svg.append('g');

    /* zoom */
    var zoomBeh = d3.zoom().scaleExtent([0.04, 4])
      .on('zoom', function(e) {
        gMain.attr('transform', e.transform);
        pat.attr('patternTransform', 'translate('+e.transform.x+','+e.transform.y+') scale('+e.transform.k+')');
      });
    svg.call(zoomBeh).call(zoomBeh.transform, d3.zoomIdentity.translate(W/2, H/2).scale(0.65));

    document.getElementById('btn-reset').addEventListener('click', function() {
      svg.transition().duration(500).call(zoomBeh.transform, d3.zoomIdentity.translate(W/2,H/2).scale(0.65));
    });

    function draw() {
      gMain.selectAll('*').remove();
      var vis = doLayout();

      /* edges */
      var gEdges = gMain.append('g');

      /* CONTAINS edges */
      vis.forEach(function(id) {
        if (!expanded.has(id)) return;
        var sp = positions.get(id);
        if (!sp) return;
        (childMap.get(id)||[]).filter(function(k){return vis.has(k)}).forEach(function(kid) {
          var tp = positions.get(kid);
          if (!tp) return;
          var sx = sp.x + NODE_W, sy = sp.y + NODE_H/2;
          var txx = tp.x, tyy = tp.y + NODE_H/2;
          var mx = (sx+txx)/2;
          gEdges.append('path')
            .attr('d', 'M'+sx+','+sy+' C'+mx+','+sy+' '+mx+','+tyy+' '+txx+','+tyy)
            .attr('fill','none').attr('stroke','#4a4a5a').attr('stroke-width',1.6).attr('opacity',0.7);
        });
      });

      /* cross-link edges */
      crossLinks.forEach(function(cl) {
        if (!vis.has(cl.source) || !vis.has(cl.target)) return;
        var sp = positions.get(cl.source), tp = positions.get(cl.target);
        if (!sp || !tp) return;
        var sx = sp.x + NODE_W, sy = sp.y + NODE_H/2;
        var txx = tp.x, tyy = tp.y + NODE_H/2;
        var mx = (sx+txx)/2;
        var col = EC[cl.type] || '#555';
        gEdges.append('path')
          .attr('d', 'M'+sx+','+sy+' C'+mx+','+sy+' '+mx+','+tyy+' '+txx+','+tyy)
          .attr('fill','none').attr('stroke',col).attr('stroke-width',2).attr('opacity',0.85)
          .attr('stroke-dasharray','6 3');
      });

      /* nodes */
      var gNodes = gMain.append('g');
      vis.forEach(function(id) {
        var nd = nodeMap.get(id);
        var pos = positions.get(id);
        if (!nd || !pos) return;
        var color = NC[nd.type] || '#78909c';
        var isExp = expanded.has(id);
        var hk = hasKids(id);
        var kc = kidCount(id);

        var g = gNodes.append('g').attr('transform','translate('+pos.x+','+pos.y+')').style('cursor','pointer');

        /* body */
        g.append('rect').attr('class','node-body')
          .attr('width',NODE_W).attr('height',NODE_H).attr('rx',6)
          .attr('fill','#0e0e14').attr('stroke',color).attr('stroke-width',1).attr('opacity',0.95);

        /* connection slots */
        g.append('circle').attr('cx',0).attr('cy',NODE_H/2).attr('r',SLOT_R).attr('fill',color).attr('opacity',0.5);
        g.append('circle').attr('cx',NODE_W).attr('cy',NODE_H/2).attr('r',SLOT_R).attr('fill',color).attr('opacity',0.5);

        /* name */
        var name = (nd.name||'Unknown');
        if (name.length > 22) name = name.slice(0,20) + '\\u2026';
        g.append('text').attr('x',12).attr('y',16)
          .attr('font-size',12).attr('font-family','Inter,system-ui,sans-serif').attr('font-weight',600)
          .attr('fill','#d4d4d8').style('pointer-events','none').text(name);

        /* type badge */
        g.append('text').attr('x',12).attr('y',33)
          .attr('font-size',8).attr('font-family','Inter,system-ui,sans-serif').attr('font-weight',700)
          .attr('fill',color).attr('opacity',0.55).style('pointer-events','none')
          .style('letter-spacing','0.08em').text((nd.type||'').toUpperCase());

        /* expand/collapse */
        if (hk) {
          var btn = g.append('g').attr('class','expand-btn');
          btn.append('rect')
            .attr('x',NODE_W-30).attr('y',(NODE_H-18)/2).attr('width',24).attr('height',18).attr('rx',4)
            .attr('fill',isExp ? color : color).attr('fill-opacity', isExp ? 0.13 : 0.07)
            .attr('stroke',color).attr('stroke-width',0.5);
          btn.append('text')
            .attr('x',NODE_W-18).attr('y',NODE_H/2+1)
            .attr('font-size',11).attr('font-weight',700).attr('text-anchor','middle').attr('dominant-baseline','middle')
            .attr('fill',color).style('pointer-events','none')
            .text(isExp ? '\\u2212' : '+'+kc);
          btn.on('click', function(e) {
            e.stopPropagation();
            if (expanded.has(id)) expanded.delete(id); else expanded.add(id);
            draw();
          });
        }

        /* hover tooltip */
        g.on('mouseenter', function(e) {
          var tip = document.getElementById('tooltip');
          tip.innerHTML = '<strong>'+(nd.name||'?')+'</strong><br><span style="color:'+color+';font-size:10px;text-transform:uppercase;letter-spacing:0.05em;font-weight:700">'+(nd.type||'')+'</span>';
          tip.style.display = 'block';
          tip.style.left = (e.clientX+15)+'px';
          tip.style.top = (e.clientY+15)+'px';
        });
        g.on('mouseleave', function() { document.getElementById('tooltip').style.display='none'; });
      });
    }

    draw();

    /* orphans toggle */
    if (orphanIds.size > 0) {
      var btn = document.createElement('button');
      btn.id = 'orphan-btn';
      btn.textContent = 'SHOW ' + orphanIds.size + ' EXTERNAL';
      document.body.appendChild(btn);
      btn.addEventListener('click', function() {
        showOrphans = !showOrphans;
        btn.textContent = (showOrphans ? 'HIDE ' : 'SHOW ') + orphanIds.size + ' EXTERNAL';
        if (showOrphans) btn.classList.add('active'); else btn.classList.remove('active');
        draw();
      });
    }

    /* legend */
    var types = {};
    nodes.forEach(function(n){ types[n.type] = (types[n.type]||0)+1; });
    var leg = document.getElementById('legend');
    leg.innerHTML = Object.entries(types).sort(function(a,b){return b[1]-a[1]}).map(function(e){
      var c = NC[e[0]] || '#78909c';
      return '<div class="leg-item"><span class="leg-dot" style="background:'+c+'"></span><span class="leg-lbl">'+e[0]+'</span><span class="leg-cnt">'+e[1]+'</span></div>';
    }).join('');

    /* resize */
    window.addEventListener('resize', function(){ W=innerWidth; H=innerHeight; svg.attr('width',W).attr('height',H); });
  })();
  </script>
</body>
</html>`;
}

/* ── Main export function ──────────────────────────────────────────── */
export async function packageInteractiveExport(
  nodes: GraphNode[],
  links: GraphLink[],
  metadata: GraphMetadata,
  nodeColors: Record<string, string>,
  edgeColors: Record<string, string>,
  mode: 'classic' | 'mermaid' = 'classic'
): Promise<Blob> {
  const zip = new JSZip();

  // Serialize graph data in d3-compatible format
  const graphData = {
    nodes: nodes.map(n => ({
      id: String(n.id),
      name: n.name || String(n.id),
      type: n.type,
      val: n.val || 1,
      file: n.file || ''
    })),
    links: links.map(l => {
      const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;
      return { source: String(sourceId), target: String(targetId), type: l.type };
    }),
    metadata
  };

  const graphDataJson = JSON.stringify(graphData, null, 2);
  zip.file("graph-data.json", graphDataJson);

  // Serialize colors
  const nodeColorsJson = JSON.stringify(nodeColors);
  const edgeColorsJson = JSON.stringify(edgeColors);

  // Compact data json for inline use (no pretty-print)
  const inlineDataJson = JSON.stringify(graphData);

  let d3Bundle = '';
  try {
    d3Bundle = await fetchD3();
  } catch {
    // fallback to CDN if fetch fails (e.g. user is already offline at export time)
    d3Bundle = '';
  }

  // Generate HTML based on mode
  const htmlContent = mode === 'mermaid'
    ? generateFlowchartHTML(inlineDataJson, nodeColorsJson, edgeColorsJson, d3Bundle)
    : generateClassicHTML(inlineDataJson, nodeColorsJson, edgeColorsJson, d3Bundle);

  zip.file("index.html", htmlContent);

  // README
  const repoStr = metadata.repo || 'Unknown Repository';
  const readmeContent = `# Code Graph Export: ${repoStr}

This is an interactive HTML export of the code graph from CodeGraphContext.

## Usage
1. Open \`index.html\` in any modern web browser.
2. **Pan**: Click and drag the background.
3. **Zoom**: Scroll wheel.
4. **Hover**: Mouse over nodes to see details.
${mode === 'classic' ? '5. **Layout**: Use the Stop/Start Layout button to control physics simulation.' : '5. **Expand/Collapse**: Click the +/− buttons on nodes to explore the tree.'}
6. **Reset**: Click Reset View to return to default zoom.

## Data
The raw graph data is available in \`graph-data.json\`.

Generated by [CodeGraphContext](https://codegraphcontext.com).`;

  zip.file("README.md", readmeContent);

  return await zip.generateAsync({ type: "blob" });
}
