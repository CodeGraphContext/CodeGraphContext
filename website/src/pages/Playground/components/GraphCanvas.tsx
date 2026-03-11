import React, { useEffect, useRef, useState, useCallback, useImperativeHandle, forwardRef } from 'react';
import Graph from 'graphology';
import Sigma from 'sigma';
import FA2Layout from 'graphology-layout-forceatlas2/worker';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import noverlap from 'graphology-layout-noverlap';
import EdgeCurveProgram from '@sigma/edge-curve';
import { ZoomIn, ZoomOut, Maximize2, X, Play, Pause, Minimize2, Target, RotateCcw } from 'lucide-react';

export interface GraphCanvasProps {
  data: {
    nodes: Array<{ id: string; label: string; type: string; file: string }>;
    edges: Array<{ id: string; source: string; target: string; type: string }>;
  };
  onReset?: () => void;
  selectedFile?: string | null;
  onNodeClick?: (file: string, label: string) => void;
  onStageClick?: () => void;
  visibleNodeTypes: Set<string>;
  visibleEdgeTypes: Set<string>;
  selectedPath?: string | null;
  customNodeColors?: Record<string, string>;
  customEdgeColors?: Record<string, string>;
}

/* ── Colors ─────────────────────────────────────────────────────────── */
const NODE_COLORS: Record<string, string> = {
  file:       '#3b82f6',
  folder:     '#6366f1',
  class:      '#f59e0b',
  interface:  '#ec4899',
  function:   '#10b981',
  method:     '#14b8a6',
  struct:     '#f97316',
  enum:       '#a78bfa',
  module:     '#22d3ee',
  namespace:  '#7c3aed',
  default:    '#6b7280',
};

const NODE_SIZES: Record<string, number> = {
  folder:     12,
  file:        8,
  class:      10,
  interface:   9,
  function:    6,
  method:      5,
  struct:      7,
  enum:        7,
  namespace:  11,
  module:     12,
  default:     6,
};

export const EDGE_STYLES: Record<string, { color: string }> = {
  contains:   { color: '#10b981' },
  defines:    { color: '#06b6d4' },
  imports:    { color: '#3b82f6' },
  calls:      { color: '#8b5cf6' },
  inherits:   { color: '#f97316' },
  implements: { color: '#ec4899' },
  extends:    { color: '#f59e0b' },
};

const getColor  = (type: string, custom?: Record<string, string>) => (custom && custom[type]) || NODE_COLORS[type]  || NODE_COLORS.default;
const getSize   = (type: string) => NODE_SIZES[type]   || NODE_SIZES.default;
const getEdgeColor = (type: string, custom?: Record<string, string>) => (custom && custom[type.toLowerCase()]) || EDGE_STYLES[type.toLowerCase()]?.color || '#4a4a5a';

const hexToRgb = (hex: string) => {
  if (!hex || typeof hex !== 'string') return { r: 100, g: 100, b: 100 };
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map(s => s + s).join('');
  const r = /^([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(h);
  return r ? { r: parseInt(r[1],16), g: parseInt(r[2],16), b: parseInt(r[3],16) } : { r: 100, g: 100, b: 100 };
};
const rgbToHex = (r: number, g: number, b: number) =>
  '#' + [r,g,b].map(x => Math.max(0,Math.min(255,Math.round(x))).toString(16).padStart(2,'0')).join('');

const dimColor = (hex: string, amount: number) => {
  const { r,g,b } = hexToRgb(hex);
  const bg = { r: 6, g: 6, b: 10 };
  return rgbToHex(bg.r+(r-bg.r)*amount, bg.g+(g-bg.g)*amount, bg.b+(b-bg.b)*amount);
};
const brightenColor = (hex: string, factor: number) => {
  const { r,g,b } = hexToRgb(hex);
  return rgbToHex(r+(255-r)*(factor-1)/factor, g+(255-g)*(factor-1)/factor, b+(255-b)*(factor-1)/factor);
};

const getScaledNodeSize = (baseSize: number, nodeCount: number): number => {
  if (nodeCount > 5000) return Math.max(3, baseSize * 0.7);
  if (nodeCount > 1000) return Math.max(4, baseSize * 0.85);
  return baseSize;
};

const getNodeMass = (type: string, nodeCount: number): number => {
  const base = nodeCount > 1000 ? 1.5 : 1;
  switch (type) {
    case 'folder': return 15 * base;
    case 'file':   return 3 * base;
    case 'class':  return 5 * base;
    case 'interface': return 5 * base;
    case 'function': return 2 * base;
    default: return 1;
  }
};

const getFA2Settings = (nodeCount: number) => {
  const isSmall  = nodeCount < 500;
  const isMedium = nodeCount >= 500 && nodeCount < 2000;
  const isLarge  = nodeCount >= 2000 && nodeCount < 10000;
  return {
    gravity:                      isSmall ? 0.8 : isMedium ? 0.5 : isLarge ? 0.3 : 0.15,
    scalingRatio:                 isSmall ? 15  : isMedium ? 30  : isLarge ? 60  : 100,
    slowDown:                     isSmall ? 1   : isMedium ? 2   : isLarge ? 3   : 5,
    barnesHutOptimize:            nodeCount > 200,
    barnesHutTheta:               isLarge || !isSmall && !isMedium ? 0.8 : 0.6,
    strongGravityMode:            false,
    outboundAttractionDistribution: true,
    linLogMode:                   false,
    adjustSizes:                  true,
    edgeWeightInfluence:          1,
  };
};

export const GraphCanvas = forwardRef<any, GraphCanvasProps>(({ 
  data, onReset, selectedFile, onNodeClick, onStageClick,
  visibleNodeTypes, visibleEdgeTypes, selectedPath,
  customNodeColors, customEdgeColors
}, ref) => {
  const containerRef   = useRef<HTMLDivElement>(null);
  const sigmaRef       = useRef<Sigma | null>(null);
  const graphRef       = useRef<Graph | null>(null);
  const layoutRef      = useRef<FA2Layout | null>(null);
  const selectedRef    = useRef<string | null>(null);
  const selectedPathRef = useRef<string | null>(selectedPath || null);

  const [isLayoutRunning, setIsLayoutRunning] = useState(true);
  const [selectedNode,    setSelectedNodeState] = useState<string | null>(null);
  const [hoveredLabel,    setHoveredLabel]      = useState<{ label: string; type: string } | null>(null);

  useImperativeHandle(ref, () => ({
    exportHTML: () => {
      if (!graphRef.current) return;
      
      // DEEP COPY to avoid any side effects during stringification
      const gJSON = graphRef.current.export();
      
      const htmlTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CGC - Interactive Graph Export</title>
    <script src="https://cdn.jsdelivr.net/npm/graphology@0.25.1/dist/graphology.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/sigma@2.4.0/build/sigma.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        body, html { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #06060a; color: #e4e4ed; font-family: 'Outfit', sans-serif; }
        #sigma-container { width: 100%; height: 100%; }
        .header { position: absolute; top: 20px; left: 20px; z-index: 10; background: rgba(16, 16, 24, 0.85); padding: 12px 20px; border-radius: 12px; border: 1px solid #2a2a3a; backdrop-filter: blur(12px); box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
        h1 { margin: 0; font-size: 18px; font-weight: 600; color: #7c3aed; }
        p { margin: 4px 0 0 0; font-size: 12px; color: #8888a0; font-family: 'JetBrains Mono', monospace; }
        .controls { position: absolute; bottom: 30px; right: 30px; z-index: 10; display: flex; gap: 10px; }
        .btn { background: #1a1a2e; border: 1px solid #2a2a3a; color: #e4e4ed; padding: 10px 16px; border-radius: 10px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); outline: none; }
        .btn:hover { background: #7c3aed; border-color: #8b5cf6; color: #fff; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3); }
        .btn:active { transform: translateY(0); }
    </style>
</head>
<body>
    <div class="header"><h1>Code-Graph-Context</h1><p>Interactive Codebase Explorer (Export)</p></div>
    <div id="sigma-container"></div>
    <div class="controls">
        <button class="btn" onclick="zoomIn()">Zoom +</button>
        <button class="btn" onclick="zoomOut()">Zoom -</button>
        <button class="btn" onclick="resetCamera()">Reset View</button>
    </div>
    <script>
        let sigmaInstance, camera;
        window.onload = () => {
            try {
                const graphData = __GRAPH_DATA__;
                const container = document.getElementById('sigma-container');
                
                // CRITICAL FIX: The export contains 'curved' edge types which require 
                // external shaders/programs not included in the standard Sigma bundle.
                // We strip these for the export to ensure it uses the stable default renderer.
                if (graphData.edges) {
                    graphData.edges.forEach(e => {
                        if (e.attributes) delete e.attributes.type;
                    });
                }

                const Graph = window.graphology.Graph;
                const SigmaObj = window.Sigma;

                if (!Graph || !SigmaObj) {
                    console.error("Required libraries (Graphology/Sigma) failed to load.");
                    return;
                }

                const graph = new Graph();
                graph.import(graphData);
                sigmaInstance = new SigmaObj(graph, container, {
                    renderLabels: true,
                    labelFont: 'JetBrains Mono, monospace',
                    labelSize: 12,
                    labelColor: { color: '#ffffff' },
                    defaultNodeColor: '#6b7280',
                    defaultEdgeColor: 'rgba(255,255,255,0.1)'
                });
                camera = sigmaInstance.getCamera();
            } catch (e) {
                console.error("Initialization error:", e);
            }
        };

        function zoomIn() { if (camera) camera.animatedZoom({ duration: 300 }); }
        function zoomOut() { if (camera) camera.animatedUnzoom({ duration: 300 }); }
        function resetCamera() { if (camera) camera.animatedReset({ duration: 500 }); }
    </script>
</body>
</html>`;

      // CRITICAL: Robust stringification. Using double-quotes and basic JSON.
      // We only escape </script> to prevent breaking the script tag.
      const escapedData = JSON.stringify(gJSON).replace(/<\/script>/g, '<\\/script>');
      const fullHTML = htmlTemplate.replace('__GRAPH_DATA__', escapedData);

      // THE ULTIMATE FALLBACK: Base64 encoded Data URI
      // This completely bypasses the browser's Blob URL manager which is responsible 
      // for the random UUID naming bug in Firefox on Linux.
      const base64Data = btoa(unescape(encodeURIComponent(fullHTML)));
      const dataUri = `data:text/html;base64,${base64Data}`;
      const link = document.createElement('a');
      link.href = dataUri;
      link.download = 'cgc-interactive-graph.html';
      
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  }));

  const zoomIn    = useCallback(() => sigmaRef.current?.getCamera().animatedZoom({ duration: 200 }), []);
  const zoomOut   = useCallback(() => sigmaRef.current?.getCamera().animatedUnzoom({ duration: 200 }), []);
  const resetView = useCallback(() => sigmaRef.current?.getCamera().animatedReset({ duration: 300 }), []);
  const recenter  = useCallback(() => sigmaRef.current?.getCamera().animate({ x: 0.5, y: 0.5 }, { duration: 300 }), []);
  const clearSelection = useCallback(() => {
    selectedRef.current = null;
    setSelectedNodeState(null);
    sigmaRef.current?.refresh();
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const graph = new Graph();
    graphRef.current = graph;
    const nodeCount = data.nodes.length;
    const structuralTypes = new Set(['folder', 'module', 'namespace']);
    const structuralNodes = data.nodes.filter(n => structuralTypes.has(n.type));
    const structuralSpread = Math.sqrt(nodeCount) * 45;
    const childJitter = Math.sqrt(nodeCount) * 4;
    const childToParent = new Map<string, string>();
    data.edges.forEach(e => {
        if (['contains', 'defines', 'imports'].includes(e.type.toLowerCase())) {
            childToParent.set(e.target, e.source);
        }
    });

    const nodePositions = new Map<string, { x: number; y: number }>();
    structuralNodes.forEach((n, i) => {
        const goldenAngle = Math.PI * (3 - Math.sqrt(5));
        const angle = i * goldenAngle;
        const radius = structuralSpread * Math.sqrt((i + 1) / Math.max(structuralNodes.length, 1));
        const x = radius * Math.cos(angle);
        const y = radius * Math.sin(angle);
        nodePositions.set(n.id, { x, y });
        graph.addNode(n.id, {
            label: n.label,
            size: getScaledNodeSize(getSize(n.type), nodeCount),
            color: getColor(n.type, customNodeColors),
            x, y,
            nodeType: n.type,
            file: n.file,
            hidden: !visibleNodeTypes.has(n.type),
            mass: getNodeMass(n.type, nodeCount),
        });
    });

    data.nodes.forEach(n => {
        if (graph.hasNode(n.id)) return;
        const parentId = childToParent.get(n.id);
        const parentPos = parentId ? nodePositions.get(parentId) : null;
        const x = parentPos ? parentPos.x + (Math.random() - 0.5) * childJitter : (Math.random() - 0.5) * structuralSpread;
        const y = parentPos ? parentPos.y + (Math.random() - 0.5) * childJitter : (Math.random() - 0.5) * structuralSpread;
        nodePositions.set(n.id, { x, y });
        graph.addNode(n.id, {
            label: n.label,
            size: getScaledNodeSize(getSize(n.type), nodeCount),
            color: getColor(n.type, customNodeColors),
            x, y,
            nodeType: n.type,
            file: n.file,
            hidden: !visibleNodeTypes.has(n.type),
            mass: getNodeMass(n.type, nodeCount),
        });
    });

    data.edges.forEach(e => {
      if (!graph.hasNode(e.source) || !graph.hasNode(e.target)) return;
      if (graph.hasEdge(e.source, e.target)) return;
      const color = getEdgeColor(e.type, customEdgeColors);
      const isVisible = visibleEdgeTypes.has(e.type);
      graph.addEdge(e.source, e.target, {
        size: nodeCount > 5000 ? 0.6 : 1.2,
        color: color,
        type: 'curved',
        curvature: 0.12 + Math.random() * 0.08,
        edgeType: e.type,
        hidden: !isVisible,
      });
    });

    const sigma = new Sigma(graph, containerRef.current!, {
      allowInvalidContainer:  true,
      defaultEdgeType:        'curved',
      edgeProgramClasses:     { curved: EdgeCurveProgram },
      renderLabels:           true,
      labelFont:              'JetBrains Mono, monospace',
      labelSize:              12,
      labelWeight:            '600',
      labelColor:             { color: '#ffffff' },
      labelRenderedSizeThreshold: 6,
      labelDensity:           0.12,
      labelGridCellSize:      65,
      defaultNodeColor:       '#6b7280',
      defaultEdgeColor:       'rgba(255, 255, 255, 0.2)',
      hideEdgesOnMove:        false,
      zIndex:                 true,
      minCameraRatio:         0.002,
      maxCameraRatio:         50,
      defaultDrawNodeHover: (context, data, settings) => {
        const label = data.label; if (!label) return;
        const size = 12, font = 'JetBrains Mono, monospace';
        context.font = `600 ${size}px ${font}`;
        const tw = context.measureText(label).width;
        const ns = data.size || 8;
        const x = data.x, y = data.y - ns - 12;
        const px = 10, py = 6, h = size + py*2, w = tw + px*2;
        context.shadowColor = 'rgba(0,0,0,0.5)'; context.shadowBlur = 10;
        context.fillStyle = '#12121c'; context.beginPath(); context.roundRect(x - w/2, y - h/2, w, h, 6); context.fill();
        context.shadowBlur = 0; context.strokeStyle = (data as any).color; context.lineWidth = 2.5; context.stroke();
        context.fillStyle = '#ffffff'; context.textAlign = 'center'; context.textBaseline = 'middle'; context.fillText(label, x, y);
      },
      nodeReducer: (node, attrs) => {
        const res = { ...attrs };
        const sel = selectedRef.current;
        const g = graphRef.current;
        if (!g) return res;
        if (!visibleNodeTypes.has(attrs.nodeType)) { res.hidden = true; return res; } else { res.hidden = false; }
        if (sel) {
          const isSelected = node === sel;
          const isNeighbor = g.hasEdge(node, sel) || g.hasEdge(sel, node);
          if (isSelected) {
            res.color = attrs.color; res.size = (attrs.size||8)*2.0; res.zIndex = 10; res.highlighted = true;
          } else if (isNeighbor) {
            res.color = attrs.color; res.size = (attrs.size||8)*1.5; res.zIndex = 5;
          } else {
            res.color = dimColor(attrs.color, 0.1); res.size = (attrs.size||8)*0.4; res.zIndex = 0;
          }
        } else if (selectedPathRef.current) {
          const sp = selectedPathRef.current;
          const matched = (attrs.id === sp) || (attrs.id && attrs.id.startsWith(sp + '/')) || (attrs.file === sp) || (attrs.file && attrs.file.startsWith(sp + '/'));
          if (matched) { res.color = attrs.color; res.zIndex = 10; res.highlighted = true; } 
          else { res.color = dimColor(attrs.color, 0.1); res.size = (attrs.size || 8) * 0.4; res.zIndex = 0; res.label = ""; }
        }
        return res;
      },
      edgeReducer: (edge, attrs) => {
        const res = { ...attrs };
        const sel = selectedRef.current;
        const g = graphRef.current;
        if (!g) return res;
        const [src, tgt] = g.extremities(edge);
        const srcAttrs = g.getNodeAttributes(src);
        const tgtAttrs = g.getNodeAttributes(tgt);
        if (!visibleEdgeTypes.has(attrs.edgeType) || !visibleNodeTypes.has(srcAttrs.nodeType) || !visibleNodeTypes.has(tgtAttrs.nodeType)) {
          res.hidden = true; return res;
        } else { res.hidden = false; }
        if (sel) {
          if (src === sel || tgt === sel) {
            res.color = brightenColor(attrs.color, 1.4); res.size = Math.max(3.5, (attrs.size||1) * 3); res.zIndex = 5;
          } else {
            res.color = dimColor(attrs.color, 0.05); res.size = 0.2; res.zIndex = 0;
          }
        } else if (selectedPathRef.current) {
          const sp = selectedPathRef.current;
          const srcM = (srcAttrs.id === sp) || (srcAttrs.id && srcAttrs.id.startsWith(sp + '/')) || (srcAttrs.file === sp) || (srcAttrs.file && srcAttrs.file.startsWith(sp + '/'));
          const tgtM = (tgtAttrs.id === sp) || (tgtAttrs.id && tgtAttrs.id.startsWith(sp + '/')) || (tgtAttrs.file === sp) || (tgtAttrs.file && tgtAttrs.file.startsWith(sp + '/'));
          if (srcM || tgtM) { res.color = brightenColor(attrs.color, 1.2); res.size = Math.max(1.8, (attrs.size||1) * 2); res.zIndex = 5; } 
          else { res.color = dimColor(attrs.color, 0.05); res.size = 0.1; res.zIndex = 0; }
        }
        return res;
      },
    });

    sigmaRef.current = sigma;
    sigma.on('clickNode', ({ node }) => {
      const already = selectedRef.current === node;
      selectedRef.current = already ? null : node;
      setSelectedNodeState(already ? null : node);
      const a = graph.getNodeAttributes(node);
      if (!already && onNodeClick && a.file) { onNodeClick(a.file, a.label); }
      sigma.getCamera().animate({ ratio: sigma.getCamera().ratio * 1.0001 }, { duration: 50 });
      sigma.refresh();
    });
    sigma.on('clickStage', () => {
      selectedRef.current = null; setSelectedNodeState(null);
      if (onStageClick) onStageClick(); sigma.refresh();
    });
    sigma.on('enterNode', ({ node }) => {
      const a = graph.getNodeAttributes(node);
      setHoveredLabel({ label: a.label, type: a.nodeType });
      if (containerRef.current) containerRef.current.style.cursor = 'pointer';
    });
    sigma.on('leaveNode', () => {
      setHoveredLabel(null);
      if (containerRef.current) containerRef.current.style.cursor = 'grab';
    });

    const layout = new FA2Layout(graph, { settings: { ...forceAtlas2.inferSettings(graph), ...getFA2Settings(graph.order) } });
    layoutRef.current = layout; layout.start(); setIsLayoutRunning(true);
    const stopTimer = setTimeout(() => {
      layout.stop(); layoutRef.current = null; noverlap.assign(graph, 25); sigma.refresh(); setIsLayoutRunning(false);
    }, graph.order < 500 ? 20000 : 35000);

    return () => {
      clearTimeout(stopTimer); layout.kill(); sigma.kill();
      sigmaRef.current = null; graphRef.current = null; layoutRef.current = null;
    };
  }, [data, visibleNodeTypes, visibleEdgeTypes, customNodeColors, customEdgeColors]);

  useEffect(() => {
    selectedPathRef.current = selectedPath || null;
    if (selectedPath) { selectedRef.current = null; setSelectedNodeState(null); }
    sigmaRef.current?.refresh();
  }, [selectedFile, selectedPath]);

  return (
    <div className="relative w-full h-full bg-void flex-1">
      <div className="absolute inset-0 pointer-events-none" style={{
        background: `radial-gradient(circle at 50% 50%, rgba(124,58,237,0.03) 0%, transparent 70%), linear-gradient(to bottom, #06060a, #0a0a10)`
      }} />
      <div ref={containerRef} className="sigma-container cursor-grab active:cursor-grabbing" />
      
      {/* Layout Indicator - Top Center to avoid blockages */}
      {isLayoutRunning && (
        <div className="absolute top-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-full backdrop-blur-md z-30 shadow-[0_0_20px_rgba(16,185,129,0.1)]">
          <div className="w-2.5 h-2.5 bg-emerald-400 rounded-full animate-ping" />
          <span className="text-xs text-emerald-400 font-semibold tracking-wide uppercase">Mapping Codebase...</span>
        </div>
      )}
      
      {hoveredLabel && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-30 pointer-events-none transition-all">
          <div className="flex items-center gap-3 px-4 py-2 bg-[#12121c]/98 border border-[#3a3a4a] rounded-xl backdrop-blur-xl shadow-2xl">
            <div className="w-2.5 h-2.5 rounded-full shadow-lg" style={{ background: getColor(hoveredLabel.type) }} />
            <span className="text-sm font-mono font-medium text-white">{hoveredLabel.label}</span>
            <span className="text-xs text-[#8888a0] bg-[#1a1a2e] px-2 py-1 rounded-md border border-[#2a2a3a] uppercase font-bold">{hoveredLabel.type}</span>
          </div>
        </div>
      )}

      {/* Floating Control Bar — High Contrast & Elevated UI */}
      <div className="absolute bottom-12 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 bg-[#0a0a10]/98 border border-[#3a3a4a] px-6 py-3 rounded-3xl backdrop-blur-2xl shadow-[0_20px_60px_rgba(0,0,0,0.9)] transition-all hover:border-accent/40 group">
        
        {/* Zoom Controls (Large & Tap-Friendly) */}
        <div className="flex items-center gap-2.5 pr-5 border-r border-[#2a2a3a]">
          <button onClick={zoomIn} title="Zoom In"
            className="w-11 h-11 flex items-center justify-center rounded-2xl bg-accent/10 border border-accent/20 text-accent hover:bg-accent hover:text-white transition-all transform active:scale-90 shadow-inner">
            <ZoomIn className="w-[22px] h-[22px]" />
          </button>
          <button onClick={zoomOut} title="Zoom Out"
            className="w-11 h-11 flex items-center justify-center rounded-2xl bg-accent/10 border border-accent/20 text-accent hover:bg-accent hover:text-white transition-all transform active:scale-90 shadow-inner">
            <ZoomOut className="w-[22px] h-[22px]" />
          </button>
        </div>

        {/* Framing Group (Recenter and Fit All) */}
        <div className="flex items-center gap-2.5 pr-5 border-r border-[#2a2a3a]">
          <button onClick={recenter} title="Recenter Camera"
            className="w-11 h-11 flex items-center justify-center rounded-2xl bg-void/50 border border-border-subtle text-text-secondary hover:bg-accent hover:text-white transition-all transform active:scale-90">
            <Target className="w-[22px] h-[22px]" />
          </button>
          <button onClick={clearSelection} title="Reset Controls"
            className="w-11 h-11 flex items-center justify-center rounded-2xl bg-void/50 border border-border-subtle text-text-secondary hover:bg-emerald-500 hover:text-white transition-all transform active:scale-90">
            <RotateCcw className="w-[22px] h-[22px]" />
          </button>
        </div>

        {/* Layout & Delete Actions */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => {
              if (isLayoutRunning) {
                layoutRef.current?.stop(); layoutRef.current = null; setIsLayoutRunning(false);
              } else if (graphRef.current) {
                const g = graphRef.current;
                const l = new FA2Layout(g, { settings: { ...forceAtlas2.inferSettings(g), ...getFA2Settings(g.order) } });
                layoutRef.current = l; l.start(); setIsLayoutRunning(true);
              }
            }}
            title={isLayoutRunning ? 'Freeze Animation' : 'Resume Animation'}
            className={`w-11 h-11 flex items-center justify-center rounded-2xl border-2 transition-all transform active:scale-90
              ${isLayoutRunning ? 'bg-emerald-500 border-emerald-400 text-white shadow-[0_0_20px_rgba(16,185,129,0.5)]' : 'bg-void/50 border-border-subtle text-text-secondary hover:bg-accent hover:text-white'}`}
          >
            {isLayoutRunning ? <Pause className="w-[22px] h-[22px]" /> : <Play className="w-[22px] h-[22px]" />}
          </button>
          <button onClick={onReset} title="Clear All Data"
            className="w-11 h-11 flex items-center justify-center rounded-2xl bg-void/50 border border-border-subtle text-text-secondary hover:bg-red-500 hover:text-white transition-all transform active:scale-90">
            <X className="w-[22px] h-[22px]" />
          </button>
        </div>
      </div>

      {/* Stats Overlay */}
      <div className="absolute top-6 right-6 z-20">
        <div className="flex items-center gap-4 text-[12px] font-mono font-bold text-[#8888a0] bg-[#12121c]/90 border border-[#3a3a4a] px-4 py-2 rounded-xl backdrop-blur-xl shadow-xl">
          <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-[#3b82f6] rounded-full" /><span>{data.nodes.length} N</span></div>
          <div className="w-px h-3 bg-[#3a3a4a]" />
          <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-[#10b981] rounded-full" /><span>{data.edges.length} E</span></div>
        </div>
      </div>
    </div>
  );
});
