import ForceGraph2D from "react-force-graph-2d";
import { useCallback, useRef, useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, ZoomIn, ZoomOut, Maximize, FileCode, Search,
  Eye, EyeOff, Settings2, Palette, Github, Star,
  ChevronRight, ChevronDown, Folder, FolderOpen,
  PanelLeftClose, PanelLeftOpen, GripVertical
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const DEFAULT_NODE_COLORS: Record<string, string> = {
  Repository: '#ffffff',
  Folder: '#f59e0b',
  File: '#42a5f5',
  Class: '#66bb6a',
  Interface: '#26a69a',
  Trait: '#81c784',
  Function: '#ffca28',
  Module: '#ef5350',
  Variable: '#ffa726',
  Enum: '#7e57c2',
  Struct: '#5c6bc0',
  Annotation: '#ec407a',
  Parameter: '#90a4ae',
  Other: '#78909c'
};

const DEFAULT_EDGE_COLORS: Record<string, string> = {
  CONTAINS: '#ffffff',
  CALLS: '#ab47bc',
  IMPORTS: '#42a5f5',
  INHERITS: '#66bb6a',
  HAS_PARAMETER: '#ffca28'
};

// ─── Tree Building ────────────────────────────────────────────────────────────
interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children: TreeNode[];
}

function buildTree(files: string[]): TreeNode[] {
  const root: TreeNode[] = [];

  for (const filePath of files) {
    const parts = filePath.split('/').filter(Boolean);
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      // For leaf nodes (files) we MUST store the original full path from data.files,
      // otherwise onFileClick won't match `n.file === path` in the graph data.
      const nodePath = isLast ? filePath : parts.slice(0, i + 1).join('/');

      let node = current.find(n => n.name === part);
      if (!node) {
        node = { name: part, path: nodePath, isDir: !isLast, children: [] };
        current.push(node);
      }
      current = node.children;
    }
  }

  // Sort: folders first, then files, each alphabetically
  const sortNodes = (nodes: TreeNode[]): TreeNode[] =>
    nodes
      .sort((a, b) => {
        if (a.isDir && !b.isDir) return -1;
        if (!a.isDir && b.isDir) return 1;
        return a.name.localeCompare(b.name);
      })
      .map(n => ({ ...n, children: sortNodes(n.children) }));

  return sortNodes(root);
}

// ─── Tree Item ────────────────────────────────────────────────────────────────
function TreeItem({
  node,
  depth,
  selectedFile,
  onFileClick,
  searchQuery,
}: {
  node: TreeNode;
  depth: number;
  selectedFile: string | null;
  onFileClick: (path: string | null) => void;
  searchQuery: string;
}) {
  const [open, setOpen] = useState(depth < 2);

  // Auto-expand when search active
  useEffect(() => {
    if (searchQuery) setOpen(true);
  }, [searchQuery]);

  const isMatch = node.name.toLowerCase().includes(searchQuery.toLowerCase());
  const hasMatchingDescendant = (n: TreeNode): boolean =>
    n.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    n.children.some(hasMatchingDescendant);

  if (searchQuery && !hasMatchingDescendant(node) && !isMatch) return null;

  const indent = depth * 12;

  if (node.isDir) {
    return (
      <div>
        <button
          onClick={() => setOpen(o => !o)}
          className="w-full flex items-center gap-1 py-[3px] px-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors group"
          style={{ paddingLeft: `${indent + 8}px` }}
        >
          {open
            ? <ChevronDown className="w-3 h-3 flex-shrink-0 text-gray-500" />
            : <ChevronRight className="w-3 h-3 flex-shrink-0 text-gray-500" />}
          {open
            ? <FolderOpen className="w-3.5 h-3.5 flex-shrink-0 text-amber-400 ml-0.5" />
            : <Folder className="w-3.5 h-3.5 flex-shrink-0 text-amber-400 ml-0.5" />}
          <span className="text-[13px] text-gray-300 group-hover:text-white truncate font-medium ml-1">
            {node.name}
          </span>
        </button>
        {open && (
          <div>
            {node.children.map(child => (
              <TreeItem
                key={child.path}
                node={child}
                depth={depth + 1}
                selectedFile={selectedFile}
                onFileClick={onFileClick}
                searchQuery={searchQuery}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const isSelected = selectedFile === node.path;
  const ext = node.name.split('.').pop() || '';

  // Map extensions to colors
  const extColors: Record<string, string> = {
    py: '#ffca28', ts: '#42a5f5', tsx: '#42a5f5', js: '#f59e0b',
    jsx: '#f59e0b', rs: '#ef5350', go: '#26a69a', java: '#ef9a9a',
    c: '#90caf9', h: '#90caf9', cpp: '#7986cb', cs: '#b39ddb',
    rb: '#ef5350', php: '#9fa8da', swift: '#ffa726', kt: '#ab47bc',
    scala: '#e91e63', md: '#80cbc4', json: '#a5d6a7', yml: '#80deea',
    yaml: '#80deea', toml: '#ffcc02', sh: '#a5d6a7',
  };
  const dotColor = extColors[ext] || '#78909c';

  return (
    <button
      onClick={() => onFileClick(node.path)}
      className={`w-full flex items-center gap-2 py-[3px] px-2 rounded-lg text-[13px] transition-all group ${isSelected
          ? 'bg-blue-500/20 text-blue-200 border border-blue-500/20'
          : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
        }`}
      style={{ paddingLeft: `${indent + 20}px` }}
    >
      <div
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ backgroundColor: dotColor, boxShadow: isSelected ? `0 0 6px ${dotColor}` : 'none' }}
      />
      <span className="truncate font-medium">{node.name}</span>
    </button>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
const MIN_SIDEBAR_W = 180;
const MAX_SIDEBAR_W = 520;
const DEFAULT_SIDEBAR_W = 300;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function getGraphAwareNodeScale(totalNodes: number): number {
  const safeNodeCount = Math.max(totalNodes, 1);
  return clamp(1 + Math.log10(safeNodeCount) * 0.22, 1, 2);
}

export default function CodeGraphViewer({ data, onClose }: { data: any, onClose: () => void }) {
  const fgRef = useRef<any>();
  const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight });
  const [hoverNode, setHoverNode] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [focusSet, setFocusSet] = useState<{ nodes: Set<number>, links: Set<any> } | null>(null);

  // LEGEND & CONFIG STATE
  const [nodeColors, setNodeColors] = useState(DEFAULT_NODE_COLORS);
  const [edgeColors, setEdgeColors] = useState(DEFAULT_EDGE_COLORS);
  const [visibleNodeTypes, setVisibleNodeTypes] = useState<Set<string>>(() => {
    const all = new Set(Object.keys(DEFAULT_NODE_COLORS));
    all.delete('Variable');
    all.delete('Parameter');
    return all;
  });
  const [showConfig, setShowConfig] = useState(false);
  const [lineWidth, setLineWidth] = useState(0.8);
  const [nodeSize, setNodeSize] = useState(1.0);

  // Sidebar resize / collapse
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_W);
  const [collapsed, setCollapsed] = useState(false);
  const isResizing = useRef(false);
  const resizeStartX = useRef(0);
  const resizeStartW = useRef(DEFAULT_SIDEBAR_W);

  useEffect(() => {
    const handleResize = () => setDimensions({
      width: window.innerWidth,
      height: window.innerHeight
    });
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  /* ── Drag-to-resize ── */
  const onDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    resizeStartX.current = e.clientX;
    resizeStartW.current = sidebarWidth;

    const onMove = (ev: MouseEvent) => {
      if (!isResizing.current) return;
      const delta = ev.clientX - resizeStartX.current;
      const newW = Math.min(MAX_SIDEBAR_W, Math.max(MIN_SIDEBAR_W, resizeStartW.current + delta));
      setSidebarWidth(newW);
    };
    const onUp = () => {
      isResizing.current = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const getRGBA = (hex: string, alpha: number) => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const filteredData = useMemo(() => {
    const visibleNodes = data.nodes.filter((n: any) => visibleNodeTypes.has(n.type));
    const nodeIds = new Set(visibleNodes.map((n: any) => n.id));
    const visibleLinks = data.links.filter((l: any) =>
      nodeIds.has(typeof l.source === 'object' ? l.source.id : l.source) &&
      nodeIds.has(typeof l.target === 'object' ? l.target.id : l.target)
    );
    return { nodes: visibleNodes, links: visibleLinks };
  }, [data, visibleNodeTypes]);

  const graphAwareNodeScale = useMemo(
    () => getGraphAwareNodeScale(filteredData.nodes.length),
    [filteredData.nodes.length]
  );

  const nodeCanvasObject = useCallback((node: any, ctx: any, globalScale: number) => {
    if (!visibleNodeTypes.has(node.type)) return;

    const isHovered = hoverNode && node.id === hoverNode.id;
    const isFocused = focusSet ? focusSet.nodes.has(node.id) : true;

    const baseColor = nodeColors[node.type] || nodeColors.Other;
    const radius = node.val * 0.8 * nodeSize * graphAwareNodeScale;
    const opacity = isFocused ? (isHovered ? 1 : 0.9) : 0.05;

    const isMassive = filteredData.nodes.length > 3000;

    if (isMassive && !isFocused && !isHovered) {
      ctx.fillStyle = getRGBA(baseColor, opacity);
      ctx.fillRect(node.x - radius, node.y - radius, radius * 2, radius * 2);
      return;
    }

    if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || !Number.isFinite(radius)) return;

    if (isHovered || (selectedFile && node.file === selectedFile && node.type === 'File')) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius * (isHovered ? 2.5 : 2.0), 0, 2 * Math.PI, false);
      ctx.fillStyle = getRGBA(baseColor, isHovered ? (isFocused ? 0.3 : 0.1) : 0.1);
      ctx.fill();
    }

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = isFocused ? baseColor : getRGBA(baseColor, opacity);
    ctx.fill();

    if (isHovered || (isFocused && globalScale > (isMassive ? 5.0 : 2.0))) {
      const fontSize = Math.max(2, Math.round((isHovered ? 14 : 10) / globalScale));
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = isFocused ? 'rgba(255, 255, 255, 0.9)' : 'rgba(255, 255, 255, 0.1)';
      ctx.font = `${isHovered ? 'bold' : 'normal'} ${fontSize}px Inter, sans-serif`;
      if (isFocused && !isMassive) { ctx.shadowColor = 'black'; ctx.shadowBlur = 4; }
      ctx.fillText(node.name || 'Unknown', node.x, node.y + radius + (fontSize / 2) + 4);
      if (isFocused && !isMassive) ctx.shadowBlur = 0;
    }
  }, [filteredData.nodes.length, focusSet, graphAwareNodeScale, hoverNode, nodeColors, nodeSize, selectedFile, visibleNodeTypes]);

  const handleZoom = (inOut: number) => {
    fgRef.current?.zoom(fgRef.current.zoom() * inOut, 400);
  };

  const toggleNodeType = (type: string) => {
    const next = new Set(visibleNodeTypes);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    setVisibleNodeTypes(next);
  };

  const fileTree = useMemo(() => buildTree(data.files || []), [data.files]);

  const onFileClick = (path: string | null) => {
    if (!path) {
      setSelectedFile(null);
      setFocusSet(null);
      return;
    }

    setSelectedFile(path);
    const fileNode = data.nodes.find((n: any) => n.file === path && n.type === 'File');
    if (fileNode) {
      if (fgRef.current) {
        fgRef.current.centerAt(fileNode.x, fileNode.y, 800);
        fgRef.current.zoom(2.5, 800);
      }

      const nodesInFocus = new Set<number>();
      const linksInFocus = new Set<any>();
      nodesInFocus.add(fileNode.id);

      data.links.forEach((l: any) => {
        const sId = typeof l.source === 'object' ? l.source.id : l.source;
        const tId = typeof l.target === 'object' ? l.target.id : l.target;
        if (sId === fileNode.id || tId === fileNode.id) {
          nodesInFocus.add(sId);
          nodesInFocus.add(tId);
          linksInFocus.add(l);
        }
      });

      setFocusSet({ nodes: nodesInFocus, links: linksInFocus });
    }
  };

  const getLinkColor = useCallback((link: any) => {
    const isFocused = focusSet ? focusSet.links.has(link) : true;
    const baseColor = edgeColors[link.type] || 'rgba(255,255,255,0.1)';
    if (!isFocused) return 'rgba(255, 255, 255, 0.02)';
    return baseColor;
  }, [focusSet, edgeColors]);

  const effectiveSidebarW = collapsed ? 0 : sidebarWidth;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-[#020202] overflow-hidden flex font-sans"
    >
      {/* ── SIDEBAR ── */}
      <div
        className="relative h-full flex-shrink-0 flex"
        style={{ width: collapsed ? 0 : sidebarWidth, transition: isResizing.current ? 'none' : 'width 0.2s ease' }}
      >
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              key="sidebar"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.18 }}
              className="flex flex-col h-full w-full bg-[#0d0d0d] border-r border-white/[0.07] z-[70] shadow-2xl overflow-hidden"
            >
              {/* Header */}
              <div className="px-4 pt-4 pb-2 flex-shrink-0">
                <Button
                  onClick={onClose}
                  variant="ghost"
                  className="w-full justify-start text-gray-400 hover:text-white hover:bg-white/5 mb-4 rounded-xl border border-white/5 transition-colors text-sm"
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back to Dashboard
                </Button>

                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-bold text-white flex items-center gap-2 tracking-tight uppercase">
                    <FileCode className="w-4 h-4 text-blue-400" />
                    Project Tree
                  </h2>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setShowConfig(!showConfig)}
                      title="Graph Settings"
                      className={`p-1.5 rounded-lg transition-colors ${showConfig ? 'bg-blue-500/20 text-blue-400' : 'text-gray-500 hover:text-white hover:bg-white/5'}`}
                    >
                      <Settings2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setCollapsed(true)}
                      title="Collapse sidebar"
                      className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/5 transition-colors"
                    >
                      <PanelLeftClose className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="relative mb-2">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
                  <input
                    type="text"
                    placeholder="Filter files..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-white/5 border border-white/8 rounded-lg py-1.5 pl-9 pr-3 text-[13px] text-white placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all"
                  />
                </div>
              </div>

              {/* Tree / Config */}
              <div className="flex-1 overflow-y-auto px-2 py-1 custom-scrollbar">
                {showConfig ? (
                  <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="p-3 space-y-6">
                    <div>
                      <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                        <Palette className="w-3 h-3" /> Visualization Config
                      </h3>

                      <div className="mb-6 px-1">
                        <label className="text-[10px] text-gray-400 uppercase font-bold tracking-widest block mb-2">Node Size: {nodeSize.toFixed(1)}x</label>
                        <input
                          type="range" min="0.2" max="4.0" step="0.1" value={nodeSize}
                          onChange={(e) => setNodeSize(parseFloat(e.target.value))}
                          className="w-full accent-purple-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
                        />
                      </div>

                      <div className="mb-6 px-1">
                        <label className="text-[10px] text-gray-400 uppercase font-bold tracking-widest block mb-2">Edge Width: {lineWidth.toFixed(1)}px</label>
                        <input
                          type="range" min="0.2" max="3.0" step="0.1" value={lineWidth}
                          onChange={(e) => setLineWidth(parseFloat(e.target.value))}
                          className="w-full accent-blue-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
                        />
                      </div>

                      <div className="space-y-3">
                        {Object.keys(DEFAULT_NODE_COLORS).map(type => (
                          <div key={type} className="flex items-center justify-between group">
                            <div className="flex items-center gap-3">
                              <button
                                onClick={() => toggleNodeType(type)}
                                className={`p-1 rounded transition-colors ${visibleNodeTypes.has(type) ? 'text-blue-400 bg-blue-500/10' : 'text-gray-600'}`}
                              >
                                {visibleNodeTypes.has(type) ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                              </button>
                              <span className={`text-sm ${visibleNodeTypes.has(type) ? 'text-gray-200' : 'text-gray-600'}`}>{type}</span>
                            </div>
                            <input
                              type="color" value={nodeColors[type] || '#78909c'}
                              onChange={(e) => setNodeColors({ ...nodeColors, [type]: e.target.value })}
                              className="w-6 h-6 bg-transparent border-none cursor-pointer p-0 rounded overflow-hidden"
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-4">Edge Type Colors</h3>
                      <div className="space-y-3">
                        {Object.keys(DEFAULT_EDGE_COLORS).map(type => (
                          <div key={type} className="flex items-center justify-between">
                            <span className="text-sm text-gray-400">{type}</span>
                            <input
                              type="color" value={edgeColors[type]}
                              onChange={(e) => setEdgeColors({ ...edgeColors, [type]: e.target.value })}
                              className="w-6 h-6 bg-transparent border-none cursor-pointer p-0"
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                ) : (
                  <div className="py-1">
                    {fileTree.map(node => (
                      <TreeItem
                        key={node.path}
                        node={node}
                        depth={0}
                        selectedFile={selectedFile}
                        onFileClick={onFileClick}
                        searchQuery={searchQuery}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Footer stats */}
              <div className="px-4 py-3 border-t border-white/5 bg-black/40 text-[10px] text-gray-500 flex justify-between uppercase tracking-widest font-black flex-shrink-0">
                <span>{filteredData.nodes.length} Visible</span>
                <span>{filteredData.links.length} Edges</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Drag Handle ── */}
        {!collapsed && (
          <div
            onMouseDown={onDragStart}
            className="absolute right-0 top-0 h-full w-1 cursor-col-resize z-[80] group flex items-center justify-center"
            title="Drag to resize"
          >
            <div className="w-0.5 h-full bg-white/5 group-hover:bg-blue-500/50 transition-colors duration-150" />
          </div>
        )}
      </div>

      {/* ── Expand button when collapsed ── */}
      {collapsed && (
        <button
          onClick={() => setCollapsed(false)}
          title="Expand sidebar"
          className="absolute left-0 top-1/2 -translate-y-1/2 z-[80] bg-[#0d0d0d] border border-white/10 hover:border-blue-500/40 hover:bg-white/5 text-gray-400 hover:text-white transition-all rounded-r-xl p-2 shadow-2xl"
        >
          <PanelLeftOpen className="w-4 h-4" />
        </button>
      )}

      {/* ── VIEWPORT ── */}
      <div className="flex-1 relative bg-[radial-gradient(circle_at_center,_#0a0a0a_0%,_#000_100%)] overflow-hidden">

        {/* Top Right Badges */}
        <div className="absolute top-6 right-6 z-[60] flex flex-col md:flex-row items-end md:items-center gap-3">
          <a
            href="https://github.com/CodeGraphContext/CodeGraphContext"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 bg-black/40 hover:bg-white/10 text-white text-[11px] uppercase tracking-widest font-bold px-4 py-2 border border-white/10 rounded-full transition-all backdrop-blur-md shadow-2xl"
          >
            <Star className="w-3.5 h-3.5 text-yellow-400 fill-yellow-400" />
            Star on GitHub
          </a>
          <div className="bg-black/40 text-gray-400 text-[11px] uppercase tracking-widest font-bold px-4 py-2 border border-white/10 rounded-full backdrop-blur-md shadow-2xl">
            Made by <a href="https://github.com/shashankss1205" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 transition-colors">shashankss1205</a>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="absolute top-6 left-6 z-[60] flex flex-col gap-4">
          <div className="flex flex-col bg-black/60 border border-white/10 backdrop-blur-xl rounded-2xl overflow-hidden shadow-2xl">
            <button onClick={() => handleZoom(1.4)} className="p-3 hover:bg-white/10 text-gray-300 transition-colors border-b border-white/5"><ZoomIn className="w-5 h-5" /></button>
            <button onClick={() => fgRef.current?.zoomToFit(600, 100)} className="p-3 hover:bg-white/10 text-gray-300 transition-colors border-b border-white/5"><Maximize className="w-5 h-5" /></button>
            <button onClick={() => handleZoom(0.7)} className="p-3 hover:bg-white/10 text-gray-300 transition-colors"><ZoomOut className="w-5 h-5" /></button>
          </div>

          <AnimatePresence>
            {selectedFile && (
              <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                onClick={() => onFileClick(null)}
                className="bg-red-500/20 hover:bg-red-500/40 text-red-400 border border-red-500/30 text-xs font-bold uppercase tracking-widest py-3 px-5 rounded-xl backdrop-blur-xl transition-all shadow-xl"
              >
                Clear Focus
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        <ForceGraph2D
          ref={fgRef}
          graphData={filteredData}
          width={dimensions.width - effectiveSidebarW}
          height={dimensions.height}
          nodeLabel="name"
          linkColor={getLinkColor}
          linkWidth={lineWidth}
          linkDirectionalParticles={(l: any) => (focusSet ? (focusSet.links.has(l) ? 2 : 0) : (filteredData.links.length > 500 ? 0 : 1))}
          linkDirectionalParticleWidth={lineWidth * 1.5}
          linkDirectionalParticleSpeed={0.005}
          nodeCanvasObject={nodeCanvasObject}
          onNodeClick={(node: any) => {
            if (node.type === 'File') onFileClick(node.file);
          }}
          onBackgroundClick={() => onFileClick(null)}
          onNodeHover={setHoverNode}
          d3VelocityDecay={0.4}
          d3AlphaDecay={0.05}
          cooldownTicks={50}
        />

        {/* Legend Overlay */}
        {!showConfig && (
          <div
            onClick={() => setShowConfig(true)}
            className="absolute bottom-6 right-6 z-[60] bg-black/50 hover:bg-black/70 transition-colors cursor-pointer backdrop-blur-3xl border border-white/10 rounded-2xl p-5 shadow-2xl max-w-lg"
          >
            <p className="text-[10px] text-gray-500 font-bold uppercase tracking-widest mb-3 flex items-center justify-between">
              <span>Graph Legend</span>
              <span className="text-blue-400/50">Click to Open Filters</span>
            </p>
            <div className="flex flex-wrap gap-x-5 gap-y-3 justify-end">
              {Object.keys(DEFAULT_NODE_COLORS).map(type => (
                <div key={type} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: nodeColors[type], boxShadow: `0 0 8px ${nodeColors[type]}` }} />
                  <span className={`text-[10px] font-bold uppercase tracking-widest ${visibleNodeTypes.has(type) ? 'text-gray-300' : 'text-gray-600 line-through'}`}>
                    {type}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
