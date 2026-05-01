import ForceGraph2D from "react-force-graph-2d";
import ForceGraph3D from "react-force-graph-3d";
import * as THREE from "three";
import { useCallback, useRef, useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, ZoomIn, ZoomOut, Maximize, FileCode, Search,
  Eye, EyeOff, Settings2, Palette, Star,
  ChevronRight, ChevronDown, Folder, FolderOpen,
  PanelLeftClose, PanelLeftOpen,
  Layers, Check, X, Code2, Sun, Moon, ChevronUp
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useTheme } from "next-themes";
import FlowchartSVG from "./FlowchartSVG";

const PALETTE = {
  dark: {
    bg: '#020202',
    panelBg: '#0d0d0d',
    text: '#ffffff',
    textSecondary: '#d4d4d8',
    mutedText: '#9ca3af',
    dimText: '#6b7280',
    border: 'rgba(255,255,255,0.07)',
    nodeLabel: 'rgba(255,255,255,0.9)',
    nodeLabelDim: 'rgba(255,255,255,0.1)',
    gridColor: '#0d0d14',
    canvasBg: '#020202',
    hoverBg: 'white/5',
    legendBg: 'bg-black/50 hover:bg-black/70',
    controlBg: 'bg-black/60',
    badgeBg: 'bg-black/40',
    viewportGradient: 'bg-[radial-gradient(circle_at_center,_#0a0a0a_0%,_#000_100%)]',
  },
  light: {
    bg: '#f5f5f7',
    panelBg: '#ffffff',
    text: '#1a1a1a',
    textSecondary: '#374151',
    mutedText: '#6b7280',
    dimText: '#9ca3af',
    border: 'rgba(0,0,0,0.1)',
    nodeLabel: 'rgba(0,0,0,0.85)',
    nodeLabelDim: 'rgba(0,0,0,0.08)',
    gridColor: '#e5e5ea',
    canvasBg: '#f5f5f7',
    hoverBg: 'black/5',
    legendBg: 'bg-white/80 hover:bg-white/90',
    controlBg: 'bg-white/80',
    badgeBg: 'bg-white/80',
    viewportGradient: 'bg-[radial-gradient(circle_at_center,_#f0f0f2_0%,_#e8e8ec_100%)]',
  },
} as const;

const DEFAULT_NODE_COLORS: Record<string, string> = {
  Repository: '#ffffff',
  Directory: '#f59e0b',
  File: '#42a5f5',
  Class: '#66bb6a',
  Interface: '#26a69a',
  Trait: '#81c784',
  Function: '#ffca28',
  Module: '#ef5350',
  Variable: '#ffa726',
  Enum: '#7e57c2',
  Struct: '#5c6bc0',
  Macro: '#ff7043',
  Record: '#4db6ac',
  Union: '#8d6e63',
  Property: '#dce775',
  Annotation: '#ec407a',
  Parameter: '#90a4ae',
  Other: '#78909c'
};

const DEFAULT_EDGE_COLORS: Record<string, string> = {
  CONTAINS: '#ffffff',
  CALLS: '#ab47bc',
  IMPORTS: '#42a5f5',
  INHERITS: '#66bb6a',
  IMPLEMENTS: '#26a69a',
  INCLUDES: '#81c784',
  HAS_PARAMETER: '#ffca28'
};

// ─── Visualization Modes ─────────────────────────────────────────────────────
type VisualizationMode = 'classic' | 'icon' | 'neon' | 'galaxy' | 'mermaid' | 'city3d' | 'graph3d';

const VISUALIZATION_MODES: { id: VisualizationMode; name: string; description: string; previewColor: string }[] = [
  { id: 'classic', name: 'Classic', description: 'Standard colored circles', previewColor: '#42a5f5' },
  { id: 'mermaid', name: 'Flowchart', description: 'SVG diagram with Bezier edges', previewColor: '#26c6da' },
  { id: 'icon', name: 'Icon', description: 'Emoji icons by node type', previewColor: '#ffca28' },
  { id: 'city3d', name: 'City 3D', description: '3D cityscape with buildings', previewColor: '#ff9800' },
  { id: 'graph3d', name: '3D Graph', description: 'Force-directed 3D with spheres', previewColor: '#42a5f5' },
  { id: 'neon', name: 'Neon Glow', description: 'Cyberpunk neon bloom effect', previewColor: '#00ff88' },
  { id: 'galaxy', name: 'Galaxy', description: 'Orbital rings by connections', previewColor: '#7e57c2' },
];

const EMOJI_MAP: Record<string, string> = {
  Repository: '🌐', Module: '🧩', Directory: '📁', File: '📄',
  Class: '🏛️', Struct: '🧊', Interface: '🔌', Trait: '🧬',
  Enum: '🔢', Annotation: '🏷️', Function: '⚙️',
  Macro: '🔧', Record: '📋', Union: '🔗', Property: '🏠',
};

// ─── City 3D Island Layout ───────────────────────────────────────────────────
interface CityPlatform {
  x: number; z: number; w: number; h: number;
  depth: number; name: string; path: string;
}

function countTreeLeaves(node: TreeNode, nodesByFile: Map<string, any[]>): number {
  if (!node.isDir) return Math.max(1, (nodesByFile.get(node.path) || []).length);
  if (node.children.length === 0) return 1;
  return node.children.reduce((sum, child) => sum + countTreeLeaves(child, nodesByFile), 0);
}

const PLATFORM_LAYER_H = 1.0;
const PLATFORM_PAD = 2.5;

function layoutCityIslands(
  items: TreeNode[],
  rect: { x: number; z: number; w: number; h: number },
  nodesByFile: Map<string, any[]>,
  positions: Map<number, { x: number; z: number; platformTop: number }>,
  platforms: CityPlatform[],
  depth: number = 0
) {
  if (items.length === 0) return;
  const weights = items.map(item => countTreeLeaves(item, nodesByFile));
  const total = weights.reduce((a, b) => a + b, 0) || 1;
  const isHoriz = rect.w >= rect.h;
  let offset = 0;
  const GAP = 3;

  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const ratio = weights[i] / total;
    let cr: { x: number; z: number; w: number; h: number };
    if (isHoriz) {
      const w = rect.w * ratio;
      cr = { x: rect.x + offset, z: rect.z, w: Math.max(w - GAP, 1), h: rect.h };
      offset += w;
    } else {
      const h = rect.h * ratio;
      cr = { x: rect.x, z: rect.z + offset, w: rect.w, h: Math.max(h - GAP, 1) };
      offset += h;
    }
    if (item.isDir) {
      platforms.push({ x: cr.x, z: cr.z, w: cr.w, h: cr.h, depth, name: item.name, path: item.path });
      const inner = {
        x: cr.x + PLATFORM_PAD, z: cr.z + PLATFORM_PAD,
        w: Math.max(cr.w - PLATFORM_PAD * 2, 1),
        h: Math.max(cr.h - PLATFORM_PAD * 2, 1),
      };
      layoutCityIslands(item.children, inner, nodesByFile, positions, platforms, depth + 1);
    } else {
      const nodes = nodesByFile.get(item.path) || [];
      if (nodes.length === 0) return;
      const platformTop = depth * PLATFORM_LAYER_H;
      const cols = Math.max(1, Math.ceil(Math.sqrt(nodes.length)));
      const rows = Math.ceil(nodes.length / cols);
      const cellW = cr.w / cols;
      const cellH = cr.h / rows;
      nodes.forEach((node: any, idx: number) => {
        positions.set(node.id, {
          x: cr.x + cellW * ((idx % cols) + 0.5),
          z: cr.z + cellH * (Math.floor(idx / cols) + 0.5),
          platformTop,
        });
      });
    }
  }
}

const CITY_HEIGHTS: Record<string, number> = {
  Class: 14, Interface: 12, Trait: 12, Struct: 13, Enum: 10,
  Function: 7, Module: 6, File: 2.5, Variable: 2, Annotation: 3,
  Parameter: 1.5, Other: 4, Repository: 0, Directory: 0,
};

const CITY_ARC_SEGMENTS = 24;

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
  const { theme, setTheme } = useTheme();
  const isDark = theme !== 'light';
  const pal = isDark ? PALETTE.dark : PALETTE.light;

  const fgRef = useRef<any>();
  const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight });
  const [hoverNode, setHoverNode] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [focusSet, setFocusSet] = useState<{ nodes: Set<number>, links: Set<any> } | null>(null);

  // Code viewer state
  const [codeContent, setCodeContent] = useState<string | null>(null);
  const [codeError, setCodeError] = useState<string | null>(null);
  const [codePanelWidth, setCodePanelWidth] = useState(420);
  const [codePanelTab, setCodePanelTab] = useState<'code' | 'entities'>('code');
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const isCodeResizing = useRef(false);
  const codeResizeStartX = useRef(0);
  const codeResizeStartW = useRef(420);
  const codeBodyRef = useRef<HTMLDivElement>(null);

  // Legend collapsible state
  const [legendCollapsed, setLegendCollapsed] = useState(false);

  const fileContents: Record<string, string> = data.fileContents || {};

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
  const [graphMode, setGraphMode] = useState<VisualizationMode>('classic');
  const [showModeMenu, setShowModeMenu] = useState(false);
  const modeMenuRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target as Node)) {
        setShowModeMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
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

  const { degreeMap, maxDegree } = useMemo(() => {
    const dm = new Map<number, number>();
    for (const link of filteredData.links) {
      const sId = typeof link.source === 'object' ? link.source.id : link.source;
      const tId = typeof link.target === 'object' ? link.target.id : link.target;
      dm.set(sId, (dm.get(sId) || 0) + 1);
      dm.set(tId, (dm.get(tId) || 0) + 1);
    }
    let max = 0;
    for (const v of dm.values()) { if (v > max) max = v; }
    return { degreeMap: dm, maxDegree: max };
  }, [filteredData]);

  const nodeCanvasObject = useCallback((node: any, ctx: any, globalScale: number) => {
    if (!visibleNodeTypes.has(node.type)) return;
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;

    const isHovered = hoverNode && node.id === hoverNode.id;
    const isFocused = focusSet ? focusSet.nodes.has(node.id) : true;
    const baseColor = nodeColors[node.type] || nodeColors.Other;
    const radius = node.val * 0.8 * nodeSize * graphAwareNodeScale;
    const opacity = isFocused ? (isHovered ? 1 : 0.9) : 0.05;
    const isMassive = filteredData.nodes.length > 3000;

    if (!Number.isFinite(radius)) return;

    if (isMassive && !isFocused && !isHovered) {
      ctx.fillStyle = getRGBA(baseColor, opacity);
      ctx.fillRect(node.x - radius, node.y - radius, radius * 2, radius * 2);
      return;
    }

    switch (graphMode) {
      case 'icon': {
        if (isHovered || (selectedFile && node.file === selectedFile && node.type === 'File')) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, radius * (isHovered ? 2.5 : 2.0), 0, 2 * Math.PI, false);
          ctx.fillStyle = getRGBA(baseColor, isHovered ? (isFocused ? 0.3 : 0.1) : 0.1);
          ctx.fill();
        }
        ctx.save();
        const emojiSize = Math.max(14 / globalScale, (node.val || 1) * 2);
        ctx.font = `${emojiSize}px serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.globalAlpha = isFocused ? 1.0 : 0.3;
        ctx.fillText(EMOJI_MAP[node.type] || '❓', node.x, node.y);
        ctx.restore();
        break;
      }

      case 'neon': {
        if (isHovered || (selectedFile && node.file === selectedFile && node.type === 'File')) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, radius * 3, 0, 2 * Math.PI, false);
          ctx.fillStyle = getRGBA(baseColor, 0.06);
          ctx.fill();
        }
        ctx.save();
        ctx.shadowColor = baseColor;
        ctx.shadowBlur = isFocused ? 20 : 3;
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
        ctx.fillStyle = isFocused ? baseColor : getRGBA(baseColor, opacity);
        ctx.fill();
        ctx.shadowBlur = isFocused ? 10 : 0;
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius * 0.4, 0, 2 * Math.PI, false);
        ctx.fillStyle = isFocused ? (isDark ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.5)') : getRGBA(isDark ? '#ffffff' : '#000000', opacity * 0.5);
        ctx.fill();
        ctx.restore();
        break;
      }

      case 'galaxy': {
        const degree = degreeMap.get(node.id) || 0;
        const ringCount = clamp(degree, 1, 5);

        if (isFocused) {
          const haloRadius = radius * 4;
          const grad = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, haloRadius);
          grad.addColorStop(0, getRGBA(baseColor, isHovered ? 0.4 : 0.25));
          grad.addColorStop(0.4, getRGBA(baseColor, 0.08));
          grad.addColorStop(1, getRGBA(baseColor, 0));
          ctx.beginPath();
          ctx.arc(node.x, node.y, haloRadius, 0, 2 * Math.PI, false);
          ctx.fillStyle = grad;
          ctx.fill();

          for (let i = 0; i < ringCount; i++) {
            const ringR = radius * (1 + (i + 1) * 0.8);
            const ringAlpha = 0.35 - i * 0.06;
            ctx.beginPath();
            ctx.arc(node.x, node.y, ringR, 0, 2 * Math.PI, false);
            ctx.strokeStyle = getRGBA(baseColor, Math.max(ringAlpha, 0.05));
            ctx.lineWidth = isHovered ? 0.8 : 0.5;
            ctx.stroke();
          }
        } else {
          ctx.beginPath();
          ctx.arc(node.x, node.y, radius * 2, 0, 2 * Math.PI, false);
          ctx.fillStyle = getRGBA(baseColor, 0.02);
          ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(node.x, node.y, isFocused ? radius * 0.5 : radius * 0.3, 0, 2 * Math.PI, false);
        ctx.fillStyle = isFocused ? (isDark ? '#ffffff' : '#1a1a1a') : getRGBA(isDark ? '#ffffff' : '#000000', opacity * 0.5);
        ctx.fill();
        break;
      }

      default: {
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
        break;
      }
    }

    const showLabel = isHovered || (isFocused && globalScale > (isMassive ? 5.0 : 2.0));

    if (showLabel) {
      const fontSize = Math.max(2, Math.round((isHovered ? 14 : 10) / globalScale));
      const labelY = graphMode === 'icon'
        ? node.y + Math.max(14 / globalScale, (node.val || 1) * 2) / 2 + fontSize / 2 + 2
        : node.y + radius + fontSize / 2 + 4;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = isFocused ? pal.nodeLabel : pal.nodeLabelDim;
      ctx.font = `${isHovered ? 'bold' : 'normal'} ${fontSize}px Inter, sans-serif`;
      if (isFocused && !isMassive) { ctx.shadowColor = isDark ? 'black' : 'white'; ctx.shadowBlur = 4; }
      ctx.fillText(node.name || 'Unknown', node.x, labelY);
      if (isFocused && !isMassive) ctx.shadowBlur = 0;
    }
  }, [filteredData.nodes.length, focusSet, graphAwareNodeScale, hoverNode, nodeColors, nodeSize, selectedFile, visibleNodeTypes, graphMode, degreeMap, pal, isDark]);

  const cityNodeThreeObject = useCallback((node: any) => {
    if (!visibleNodeTypes.has(node.type)) return new THREE.Object3D();
    // Directories and Repository are represented by platforms, not buildings
    if (node.type === 'Directory' || node.type === 'Repository') return new THREE.Object3D();

    const color = nodeColors[node.type] || nodeColors.Other;
    const degree = degreeMap.get(node.id) || 0;
    const baseH = CITY_HEIGHTS[node.type] || 4;
    const bHeight = Math.max(1.5, (baseH + degree * 0.5) * nodeSize * 0.5);
    const bWidth = Math.max(1.8, 2.2 + (node.val || 2) * 0.15);
    const pTop = node.__platformTop || 0;

    // Main building body
    const geo = new THREE.BoxGeometry(bWidth, bHeight, bWidth);
    const mat = new THREE.MeshPhongMaterial({
      color: new THREE.Color(color),
      shininess: 40,
      specular: new THREE.Color(0x222222),
    });
    const building = new THREE.Mesh(geo, mat);
    building.position.y = pTop + bHeight / 2;

    // Wireframe edge overlay
    const edgeGeo = new THREE.EdgesGeometry(geo);
    const edgeMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.08 });
    const wireframe = new THREE.LineSegments(edgeGeo, edgeMat);
    wireframe.position.y = pTop + bHeight / 2;

    // Glowing rooftop cap
    const roofGeo = new THREE.BoxGeometry(bWidth + 0.2, 0.2, bWidth + 0.2);
    const roofMat = new THREE.MeshPhongMaterial({
      color: new THREE.Color(color),
      emissive: new THREE.Color(color),
      emissiveIntensity: 0.6,
    });
    const roof = new THREE.Mesh(roofGeo, roofMat);
    roof.position.y = pTop + bHeight;

    const group = new THREE.Group();
    group.add(building);
    group.add(wireframe);
    group.add(roof);
    return group;
  }, [nodeColors, nodeSize, degreeMap, visibleNodeTypes]);

  const graph3dNodeThreeObject = useCallback((node: any) => {
    if (!visibleNodeTypes.has(node.type)) return new THREE.Object3D();

    const color = nodeColors[node.type] || nodeColors.Other;
    const degree = degreeMap.get(node.id) || 0;
    const radius = Math.max(1.5, (node.val || 2) * 0.6 * nodeSize + degree * 0.15);

    const sphereGeo = new THREE.SphereGeometry(radius, 16, 12);
    const sphereMat = new THREE.MeshPhongMaterial({
      color: new THREE.Color(color),
      emissive: new THREE.Color(color),
      emissiveIntensity: 0.35,
      transparent: true,
      opacity: 0.92,
      shininess: 80,
    });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);

    const glowGeo = new THREE.SphereGeometry(radius * 1.4, 16, 12);
    const glowMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(color),
      transparent: true,
      opacity: 0.08,
      side: THREE.BackSide,
    });
    const glow = new THREE.Mesh(glowGeo, glowMat);

    const group = new THREE.Group();
    group.add(sphere);
    group.add(glow);

    return group;
  }, [nodeColors, nodeSize, degreeMap, visibleNodeTypes]);

  const graph3dLinkColor = useCallback((link: any) => {
    const baseColor = edgeColors[link.type] || '#ffffff';
    return baseColor;
  }, [edgeColors]);

  // Arc data stored during city3dData computation, drawn in city3dSetup
  const cityArcsRef = useRef<{ sx: number; sz: number; sy: number; tx: number; tz: number; ty: number; color: string }[]>([]);

  const cityPlatformsRef = useRef<CityPlatform[]>([]);
  const cityGridSizeRef = useRef(100);
  const city3dSetup = useRef(false);

  useEffect(() => {
    if (graphMode !== 'city3d') {
      city3dSetup.current = false;
      return;
    }
    const timer = setTimeout(() => {
      const fg = fgRef.current;
      if (!fg?.scene || city3dSetup.current) return;
      const scene = fg.scene();

      // Remove old city objects on re-render
      const toRemove = scene.children.filter((c: any) => c.name?.startsWith('city_'));
      toRemove.forEach((c: any) => scene.remove(c));

      const gs = cityGridSizeRef.current;

      // Grid floor
      const gridC1 = isDark ? 0x334455 : 0xbbbbcc;
      const gridC2 = isDark ? 0x1a1a2e : 0xddddee;
      const grid = new THREE.GridHelper(gs * 3, 60, gridC1, gridC2);
      grid.name = 'city_grid';
      grid.position.y = -0.5;
      scene.add(grid);

      // Main repo island
      const repoGeo = new THREE.BoxGeometry(gs + 8, 1.0, gs + 8);
      const repoMat = new THREE.MeshPhongMaterial({
        color: isDark ? 0x1a3a1a : 0x98d498,
        transparent: true, opacity: 0.7, shininess: 30,
      });
      const repoMesh = new THREE.Mesh(repoGeo, repoMat);
      repoMesh.name = 'city_repo';
      repoMesh.position.set(0, -0.5, 0);
      scene.add(repoMesh);

      // Repo island border
      const repoEdges = new THREE.EdgesGeometry(repoGeo);
      const repoLine = new THREE.LineSegments(repoEdges, new THREE.LineBasicMaterial({
        color: isDark ? 0x44aa44 : 0x2e7d32, transparent: true, opacity: 0.5,
      }));
      repoLine.name = 'city_repo_edge';
      repoLine.position.copy(repoMesh.position);
      scene.add(repoLine);

      // Folder island platforms
      const PLAT_COLORS_DARK = [0x2d5a27, 0x357a2e, 0x3d8a35, 0x45a03c, 0x4db543];
      const PLAT_COLORS_LIGHT = [0x66bb6a, 0x81c784, 0xa5d6a7, 0xc8e6c9, 0xe8f5e9];
      const platColors = isDark ? PLAT_COLORS_DARK : PLAT_COLORS_LIGHT;

      for (const plat of cityPlatformsRef.current) {
        const pH = 0.6;
        const baseY = plat.depth * PLATFORM_LAYER_H;
        const cx = plat.x + plat.w / 2;
        const cz = plat.z + plat.h / 2;
        const color = platColors[Math.min(plat.depth, platColors.length - 1)];

        const geo = new THREE.BoxGeometry(plat.w, pH, plat.h);
        const mat = new THREE.MeshPhongMaterial({
          color, transparent: true, opacity: 0.75, shininess: 20,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.name = `city_plat_${plat.path}`;
        mesh.position.set(cx, baseY + pH / 2, cz);
        scene.add(mesh);

        // Platform border
        const edgeGeo = new THREE.EdgesGeometry(geo);
        const edgeMat = new THREE.LineBasicMaterial({
          color: isDark ? 0x66cc66 : 0x388e3c, transparent: true, opacity: 0.4,
        });
        const edgeLine = new THREE.LineSegments(edgeGeo, edgeMat);
        edgeLine.name = `city_plat_edge_${plat.path}`;
        edgeLine.position.copy(mesh.position);
        scene.add(edgeLine);
      }

      // Draw arc edges directly in the scene
      for (const arc of cityArcsRef.current) {
        const dx = arc.tx - arc.sx;
        const dz = arc.tz - arc.sz;
        const dist = Math.sqrt(dx * dx + dz * dz);
        if (dist < 0.1) continue;
        const peakY = Math.max(arc.sy, arc.ty) + Math.min(35, Math.max(4, dist * 0.3));

        const pts = new Float32Array(CITY_ARC_SEGMENTS * 3);
        for (let i = 0; i < CITY_ARC_SEGMENTS; i++) {
          const t = i / (CITY_ARC_SEGMENTS - 1);
          pts[i * 3]     = arc.sx + dx * t;
          pts[i * 3 + 2] = arc.sz + dz * t;
          // Quadratic bezier Y: start rooftop → peak → end rooftop
          pts[i * 3 + 1] = (1 - t) * (1 - t) * arc.sy + 2 * (1 - t) * t * peakY + t * t * arc.ty;
        }
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(pts, 3));
        const mat = new THREE.LineBasicMaterial({ color: arc.color, transparent: true, opacity: 0.3 });
        const line = new THREE.Line(geo, mat);
        line.name = 'city_arc';
        scene.add(line);
      }

      // Lights for Phong materials
      const existingLights = scene.children.filter((c: any) => c.isLight);
      if (existingLights.length < 3) {
        const ambient = new THREE.AmbientLight(0xffffff, 0.6);
        ambient.name = 'city_ambient';
        scene.add(ambient);
        const dir = new THREE.DirectionalLight(0xffffff, 0.8);
        dir.name = 'city_dir';
        dir.position.set(gs, gs, gs);
        scene.add(dir);
        const dir2 = new THREE.DirectionalLight(0x8888ff, 0.3);
        dir2.name = 'city_dir2';
        dir2.position.set(-gs, gs * 0.5, -gs);
        scene.add(dir2);
      }

      // Position camera for a good initial isometric-ish view of the city
      const cam = fg.camera();
      if (cam) {
        cam.position.set(gs * 0.45, gs * 0.4, gs * 0.55);
        cam.lookAt(0, 5, 0);
      }

      city3dSetup.current = true;
    }, 400);
    return () => clearTimeout(timer);
  }, [graphMode, isDark]);

  const handleZoom = (inOut: number) => {
    if (graphMode === 'city3d' || graphMode === 'graph3d') return;
    fgRef.current?.zoom(fgRef.current.zoom() * inOut, 400);
  };

  const toggleNodeType = (type: string) => {
    const next = new Set(visibleNodeTypes);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    setVisibleNodeTypes(next);
  };

  const fileTree = useMemo(() => buildTree(data.files || []), [data.files]);

  const city3dData = useMemo(() => {
    if (graphMode !== 'city3d') return filteredData;

    const nodesByFile = new Map<string, any[]>();
    for (const node of filteredData.nodes) {
      const fp = node.file || '__unattached__';
      if (!nodesByFile.has(fp)) nodesByFile.set(fp, []);
      nodesByFile.get(fp)!.push(node);
    }

    const positions = new Map<number, { x: number; z: number; platformTop: number }>();
    const platforms: CityPlatform[] = [];
    const gridSize = Math.max(80, Math.sqrt(filteredData.nodes.length) * 7);
    const rootRect = { x: -gridSize / 2, z: -gridSize / 2, w: gridSize, h: gridSize };
    layoutCityIslands(fileTree, rootRect, nodesByFile, positions, platforms, 0);

    cityPlatformsRef.current = platforms;
    cityGridSizeRef.current = gridSize;
    city3dSetup.current = false; // force scene rebuild

    // Track which nodes are inside the city (placed by layout)
    const cityNodeIds = new Set(positions.keys());

    // Orphan nodes placed off-screen below the grid (hidden)
    const orphans = filteredData.nodes.filter((n: any) => !positions.has(n.id));
    orphans.forEach((node: any) => {
      positions.set(node.id, { x: 0, z: 0, platformTop: -100 });
    });

    // Build node lookup for building top Y computation
    const nodeMap = new Map<number, any>();
    const fixedNodes = filteredData.nodes.map((node: any) => {
      const pos = positions.get(node.id);
      const fixed = pos
        ? { ...node, fx: pos.x, fy: pos.platformTop === -100 ? -100 : 0, fz: pos.z, __platformTop: pos.platformTop }
        : { ...node, fx: 0, fy: -100, fz: 0, __platformTop: 0 };
      nodeMap.set(fixed.id, fixed);
      return fixed;
    });

    // Compute building rooftop Y for a node
    const roofY = (n: any) => {
      if (!n || n.type === 'Directory' || n.type === 'Repository') return 0;
      const deg = degreeMap.get(n.id) || 0;
      const baseH = CITY_HEIGHTS[n.type] || 4;
      const bH = Math.max(1.5, (baseH + deg * 0.5) * nodeSize * 0.5);
      return (n.__platformTop || 0) + bH;
    };

    // Precompute arcs for scene rendering (bypass library link handling)
    const arcs: typeof cityArcsRef.current = [];
    for (const l of filteredData.links) {
      const t = (l.type || '').toUpperCase();
      if (t === 'CONTAINS') continue;
      const sId = typeof l.source === 'object' ? l.source.id : l.source;
      const tId = typeof l.target === 'object' ? l.target.id : l.target;
      if (!cityNodeIds.has(sId) || !cityNodeIds.has(tId)) continue;
      const sn = nodeMap.get(sId);
      const tn = nodeMap.get(tId);
      if (!sn || !tn) continue;
      const color = edgeColors[t] || (isDark ? '#88ff88' : '#388e3c');
      arcs.push({ sx: sn.fx, sz: sn.fz, sy: roofY(sn), tx: tn.fx, tz: tn.fz, ty: roofY(tn), color });
    }
    cityArcsRef.current = arcs;

    // Pass empty links to ForceGraph3D — we draw arcs ourselves
    return { nodes: fixedNodes, links: [] as any[] };
  }, [graphMode, filteredData, fileTree, degreeMap, nodeSize, edgeColors, isDark]);

  const loadFileCode = useCallback((path: string) => {
    const content = fileContents[path];
    if (content != null) {
      setCodeContent(content);
      setCodeError(null);
      setCodePanelTab('code');
    } else {
      setCodeContent(null);
      setCodeError('Source not available');
      setCodePanelTab('entities');
    }
  }, [fileContents]);

  const onFileClick = (path: string | null, targetLine?: number) => {
    if (!path) {
      setSelectedFile(null);
      setFocusSet(null);
      setCodeContent(null);
      setCodeError(null);
      setHighlightLine(null);
      return;
    }

    setHighlightLine(targetLine || null);

    if (path !== selectedFile) {
      setSelectedFile(path);
      loadFileCode(path);
    } else if (targetLine) {
      setCodePanelTab('code');
      setTimeout(() => {
        const el = codeBodyRef.current?.querySelector(`[data-line="${targetLine}"]`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    }

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

  const onGraphNodeClick = (node: any) => {
    const filePath = node.file || node.properties?.path || node.properties?.file;
    if (!filePath) return;
    const lineNum = node.line_number ?? node.properties?.line_number;
    onFileClick(filePath, lineNum ? Number(lineNum) : undefined);
  };

  useEffect(() => {
    if (highlightLine && codeContent && codePanelTab === 'code') {
      setTimeout(() => {
        const el = codeBodyRef.current?.querySelector(`[data-line="${highlightLine}"]`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 150);
    }
  }, [highlightLine, codeContent, codePanelTab]);

  const fileEntities = useMemo(() => {
    if (!selectedFile) return [];
    return data.nodes.filter((n: any) => n.file === selectedFile && n.type !== 'File');
  }, [data.nodes, selectedFile]);

  const onCodeDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    isCodeResizing.current = true;
    codeResizeStartX.current = e.clientX;
    codeResizeStartW.current = codePanelWidth;
    const onMove = (ev: MouseEvent) => {
      if (!isCodeResizing.current) return;
      const delta = codeResizeStartX.current - ev.clientX;
      setCodePanelWidth(Math.min(800, Math.max(280, codeResizeStartW.current + delta)));
    };
    const onUp = () => {
      isCodeResizing.current = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const getLinkColor = useCallback((link: any) => {
    const isFocused = focusSet ? focusSet.links.has(link) : true;
    const baseColor = edgeColors[link.type] || '#ffffff';

    if (graphMode === 'galaxy') {
      return isFocused
        ? (baseColor.startsWith('#') ? getRGBA(baseColor, 0.25) : 'rgba(255,255,255,0.25)')
        : 'rgba(255, 255, 255, 0.03)';
    }
    if (graphMode === 'neon') {
      return isFocused ? baseColor : 'rgba(255, 255, 255, 0.01)';
    }
    if (!isFocused) return 'rgba(255, 255, 255, 0.02)';
    return baseColor;
  }, [focusSet, edgeColors, graphMode]);

  const effectiveSidebarW = collapsed ? 0 : sidebarWidth;
  const effectiveCodePanelW = selectedFile ? codePanelWidth : 0;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 overflow-hidden flex font-sans"
      style={{ backgroundColor: pal.bg }}
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
              className="flex flex-col h-full w-full z-[70] shadow-2xl overflow-hidden"
              style={{ backgroundColor: pal.panelBg, borderRight: `1px solid ${pal.border}` }}
            >
              {/* Header */}
              <div className="px-4 pt-4 pb-2 flex-shrink-0">
                <Button
                  onClick={onClose}
                  variant="ghost"
                  className={`w-full justify-start mb-4 rounded-xl transition-colors text-sm ${isDark ? 'text-gray-400 hover:text-white hover:bg-white/5 border border-white/5' : 'text-gray-600 hover:text-black hover:bg-black/5 border border-black/10'}`}
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back to Dashboard
                </Button>

                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-bold flex items-center gap-2 tracking-tight uppercase" style={{ color: pal.text }}>
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
                    className={`w-full rounded-lg py-1.5 pl-9 pr-3 text-[13px] focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all ${isDark ? 'bg-white/5 border border-white/8 text-white placeholder:text-gray-600' : 'bg-black/5 border border-black/10 text-gray-900 placeholder:text-gray-400'}`}
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
                              {graphMode === 'icon' && (
                                <span className="text-[16px]">{EMOJI_MAP[type] || '❓'}</span>
                              )}
                              <span className={`text-sm ${visibleNodeTypes.has(type) ? (isDark ? 'text-gray-200' : 'text-gray-700') : 'text-gray-600'}`}>{type}</span>
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
              <div className={`px-4 py-3 text-[10px] flex justify-between uppercase tracking-widest font-black flex-shrink-0 ${isDark ? 'border-t border-white/5 bg-black/40 text-gray-500' : 'border-t border-black/5 bg-gray-50 text-gray-500'}`}>
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
          className={`absolute left-0 top-1/2 -translate-y-1/2 z-[80] transition-all rounded-r-xl p-2 shadow-2xl ${isDark ? 'bg-[#0d0d0d] border border-white/10 hover:border-blue-500/40 hover:bg-white/5 text-gray-400 hover:text-white' : 'bg-white border border-black/10 hover:border-blue-500/40 hover:bg-black/5 text-gray-500 hover:text-black'}`}
        >
          <PanelLeftOpen className="w-4 h-4" />
        </button>
      )}

      {/* ── VIEWPORT ── */}
      <div className={`flex-1 relative overflow-hidden ${isDark ? 'bg-[radial-gradient(circle_at_center,_#0a0a0a_0%,_#000_100%)]' : 'bg-[radial-gradient(circle_at_center,_#f0f0f2_0%,_#e8e8ec_100%)]'}`}>

        {/* Top Right Badges */}
        <div className="absolute top-6 right-6 z-[60] flex flex-col md:flex-row items-end md:items-center gap-3">
          {/* Theme Toggle */}
          <button
            onClick={() => setTheme(isDark ? 'light' : 'dark')}
            className={`flex items-center justify-center w-9 h-9 rounded-full border backdrop-blur-md shadow-2xl transition-all ${isDark ? 'bg-black/40 hover:bg-white/10 border-white/10 text-yellow-300' : 'bg-white/80 hover:bg-white border-black/10 text-gray-700'}`}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          {/* Mode Selector Dropdown */}
          <div ref={modeMenuRef} className="relative">
            <button
              onClick={() => setShowModeMenu(v => !v)}
              className={`flex items-center gap-2 text-[11px] uppercase tracking-widest font-bold px-4 py-2 border rounded-full transition-all backdrop-blur-md shadow-2xl cursor-pointer ${isDark ? 'bg-black/40 hover:bg-white/10 text-white border-white/10' : 'bg-white/80 hover:bg-white text-gray-800 border-black/10'}`}
            >
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              {VISUALIZATION_MODES.find(m => m.id === graphMode)?.name}
              <ChevronDown className={`w-3 h-3 text-gray-400 transition-transform ${showModeMenu ? 'rotate-180' : ''}`} />
            </button>
            <AnimatePresence>
              {showModeMenu && (
                <motion.div
                  initial={{ opacity: 0, y: -8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.96 }}
                  transition={{ duration: 0.15 }}
                  className={`absolute right-0 top-full mt-2 backdrop-blur-xl border rounded-2xl shadow-2xl overflow-hidden min-w-[280px] py-1.5 z-[100] ${isDark ? 'bg-black/90 border-white/10' : 'bg-white/95 border-black/10'}`}
                >
                  {VISUALIZATION_MODES.map(mode => (
                    <button
                      key={mode.id}
                      onClick={() => { setGraphMode(mode.id); setShowModeMenu(false); }}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 transition-all cursor-pointer ${
                        graphMode === mode.id
                          ? (isDark ? 'bg-white/10 text-white' : 'bg-black/10 text-black')
                          : (isDark ? 'text-gray-400 hover:text-white hover:bg-white/5' : 'text-gray-500 hover:text-black hover:bg-black/5')
                      }`}
                    >
                      <div
                        className="w-3 h-3 rounded-full flex-shrink-0"
                        style={{ backgroundColor: mode.previewColor, boxShadow: `0 0 8px ${mode.previewColor}` }}
                      />
                      <div className="text-left flex-1 min-w-0">
                        <div className="text-[12px] font-bold tracking-wide">{mode.name}</div>
                        <div className="text-[10px] text-gray-500">{mode.description}</div>
                      </div>
                      {graphMode === mode.id && (
                        <Check className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                      )}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <a
            href="https://github.com/CodeGraphContext/CodeGraphContext"
            target="_blank"
            rel="noopener noreferrer"
            className={`flex items-center gap-2 text-[11px] uppercase tracking-widest font-bold px-4 py-2 border rounded-full transition-all backdrop-blur-md shadow-2xl ${isDark ? 'bg-black/40 hover:bg-white/10 text-white border-white/10' : 'bg-white/80 hover:bg-white text-gray-800 border-black/10'}`}
          >
            <Star className="w-3.5 h-3.5 text-yellow-400 fill-yellow-400" />
            Star on GitHub
          </a>
          <div className={`text-[11px] uppercase tracking-widest font-bold px-4 py-2 border rounded-full backdrop-blur-md shadow-2xl ${isDark ? 'bg-black/40 text-gray-400 border-white/10' : 'bg-white/80 text-gray-500 border-black/10'}`}>
            Made by <a href="https://github.com/shashankss1205" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 transition-colors">shashankss1205</a>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="absolute top-6 left-6 z-[60] flex flex-col gap-4">
          <div className={`flex flex-col border backdrop-blur-xl rounded-2xl overflow-hidden shadow-2xl ${isDark ? 'bg-black/60 border-white/10' : 'bg-white/80 border-black/10'}`}>
            <button onClick={() => handleZoom(1.4)} className={`p-3 transition-colors ${isDark ? 'hover:bg-white/10 text-gray-300 border-b border-white/5' : 'hover:bg-black/5 text-gray-600 border-b border-black/5'}`}><ZoomIn className="w-5 h-5" /></button>
            <button onClick={() => fgRef.current?.zoomToFit(600, 100)} className={`p-3 transition-colors ${isDark ? 'hover:bg-white/10 text-gray-300 border-b border-white/5' : 'hover:bg-black/5 text-gray-600 border-b border-black/5'}`}><Maximize className="w-5 h-5" /></button>
            <button onClick={() => handleZoom(0.7)} className={`p-3 transition-colors ${isDark ? 'hover:bg-white/10 text-gray-300' : 'hover:bg-black/5 text-gray-600'}`}><ZoomOut className="w-5 h-5" /></button>
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

        {graphMode === 'city3d' ? (
          <>
            <ForceGraph3D
              ref={fgRef}
              graphData={city3dData}
              width={dimensions.width - effectiveSidebarW - effectiveCodePanelW}
              height={dimensions.height}
              backgroundColor={pal.canvasBg}
              nodeThreeObject={cityNodeThreeObject}
              nodeThreeObjectExtend={false}
              nodeLabel={(n: any) => `${n.type}: ${n.name}`}
              linkVisibility={false}
              onNodeClick={onGraphNodeClick}
              onBackgroundClick={() => onFileClick(null)}
              onNodeHover={setHoverNode}
              d3VelocityDecay={0.9}
              d3AlphaDecay={0.1}
              cooldownTicks={0}
              warmupTicks={0}
            />
            {/* Navigation controls overlay */}
            <div
              className="absolute bottom-6 right-6 z-[60] rounded-xl px-5 py-4 text-[11px] font-mono select-none pointer-events-none"
              style={{ backgroundColor: isDark ? 'rgba(0,0,0,0.75)' : 'rgba(255,255,255,0.85)', border: `1px solid ${pal.border}`, backdropFilter: 'blur(8px)' }}
            >
              <div className="text-[10px] font-black uppercase tracking-[0.15em] mb-3" style={{ color: pal.mutedText }}>Navigation Controls</div>
              {[
                ['Orbit / Look', 'L-Click Drag'],
                ['Zoom', 'Scroll'],
                ['Isolate Node', 'Click Building'],
                ['Reset View', 'Click Void'],
              ].map(([label, key]) => (
                <div key={label} className="flex items-center justify-between gap-6 py-[3px]">
                  <span style={{ color: pal.dimText }}>{label}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold" style={{ backgroundColor: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)', color: pal.text }}>{key}</span>
                </div>
              ))}
            </div>
          </>
        ) : graphMode === 'graph3d' ? (
          <ForceGraph3D
            ref={fgRef}
            graphData={filteredData}
            width={dimensions.width - effectiveSidebarW - effectiveCodePanelW}
            height={dimensions.height}
            backgroundColor={pal.canvasBg}
            nodeThreeObject={graph3dNodeThreeObject}
            nodeThreeObjectExtend={false}
            nodeLabel={(n: any) => `${n.type}: ${n.name}`}
            linkColor={graph3dLinkColor}
            linkWidth={lineWidth * 0.5}
            linkOpacity={0.4}
            linkDirectionalParticles={filteredData.links.length > 500 ? 0 : 1}
            linkDirectionalParticleWidth={1.5}
            linkDirectionalParticleSpeed={0.004}
            onNodeClick={onGraphNodeClick}
            onBackgroundClick={() => onFileClick(null)}
            onNodeHover={setHoverNode}
            d3VelocityDecay={0.4}
            d3AlphaDecay={0.05}
            cooldownTicks={80}
          />
        ) : graphMode === 'mermaid' ? (
          <FlowchartSVG
            data={filteredData}
            width={dimensions.width - effectiveSidebarW - effectiveCodePanelW}
            height={dimensions.height}
            nodeColors={nodeColors}
            edgeColors={edgeColors}
            isDark={isDark}
          />
        ) : (
          <ForceGraph2D
            ref={fgRef}
            graphData={filteredData}
            width={dimensions.width - effectiveSidebarW - effectiveCodePanelW}
            height={dimensions.height}
            nodeLabel="name"
            linkColor={getLinkColor}
            linkWidth={
              graphMode === 'galaxy' ? 0.7
              : graphMode === 'neon' ? lineWidth * 1.2
              : lineWidth
            }
            linkDirectionalParticles={
              graphMode === 'galaxy'
                ? 0
                : (l: any) => (focusSet ? (focusSet.links.has(l) ? 2 : 0) : (filteredData.links.length > 500 ? 0 : 1))
            }
            linkDirectionalParticleWidth={lineWidth * 1.5}
            linkDirectionalParticleSpeed={0.005}
            nodeCanvasObject={nodeCanvasObject}
            nodePointerAreaPaint={(node: any, color: string, ctx: any, globalScale: number) => {
              const radius = (node.val || 1) * 0.8 * nodeSize * graphAwareNodeScale;
              const hitSize = graphMode === 'icon'
                ? Math.max(14 / globalScale, (node.val || 1) * 2)
                : radius * 1.5;
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, hitSize, 0, 2 * Math.PI, false);
              ctx.fill();
            }}
            onNodeClick={onGraphNodeClick}
            onBackgroundClick={() => onFileClick(null)}
            onNodeHover={setHoverNode}
            d3VelocityDecay={0.4}
            d3AlphaDecay={0.05}
            cooldownTicks={50}
          />
        )}

        {/* Legend Overlay */}
        {!showConfig && (
          <div
            className={`absolute bottom-6 z-[60] backdrop-blur-3xl border rounded-2xl shadow-2xl pointer-events-auto ${isDark ? 'bg-black/50 border-white/10' : 'bg-white/80 border-black/10'}`}
            style={{ right: selectedFile ? codePanelWidth + 24 : 24 }}
          >
            <div
              className={`flex items-center justify-between px-5 pt-4 ${legendCollapsed ? 'pb-4' : 'pb-2'} cursor-pointer transition-colors rounded-t-2xl ${isDark ? 'hover:bg-white/5' : 'hover:bg-black/5'}`}
              onClick={() => setLegendCollapsed(v => !v)}
            >
              <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2">
                <span>Graph Legend</span>
              </p>
              <div className="flex items-center gap-2">
                <span
                  className="text-blue-400/50 text-[10px] font-bold uppercase tracking-widest cursor-pointer"
                  onClick={(e) => { e.stopPropagation(); setShowConfig(true); }}
                >
                  Filters
                </span>
                <ChevronUp className={`w-3 h-3 text-gray-500 transition-transform ${legendCollapsed ? 'rotate-180' : ''}`} />
              </div>
            </div>
            {!legendCollapsed && (
              <div className="flex flex-wrap gap-x-5 gap-y-3 justify-end px-5 pb-4 max-w-lg">
                {Object.keys(DEFAULT_NODE_COLORS).map(type => (
                  <div key={type} className="flex items-center gap-2">
                    {graphMode === 'icon' ? (
                      <span className="text-[12px]">{EMOJI_MAP[type] || '❓'}</span>
                    ) : (
                      <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: nodeColors[type], boxShadow: `0 0 8px ${nodeColors[type]}` }} />
                    )}
                    <span className={`text-[10px] font-bold uppercase tracking-widest ${visibleNodeTypes.has(type) ? (isDark ? 'text-gray-300' : 'text-gray-700') : 'text-gray-500 line-through'}`}>
                      {type}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── CODE VIEWER PANEL ── */}
      <AnimatePresence>
        {selectedFile && (
          <motion.div
            key="code-panel"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: codePanelWidth, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="relative h-full flex-shrink-0 flex z-[70] shadow-2xl overflow-hidden"
            style={{ backgroundColor: pal.panelBg, borderLeft: `1px solid ${pal.border}` }}
          >
            {/* drag handle (left edge) */}
            <div
              onMouseDown={onCodeDragStart}
              className="absolute left-0 top-0 h-full w-1 cursor-col-resize z-[80] group flex items-center justify-center"
            >
              <div className="w-0.5 h-full bg-white/5 group-hover:bg-blue-500/50 transition-colors duration-150" />
            </div>

            <div className="flex flex-col w-full overflow-hidden">
              {/* header */}
              <div className="flex items-center justify-between px-4 py-3 flex-shrink-0" style={{ borderBottom: `1px solid ${pal.border}` }}>
                <div className="flex items-center gap-2 min-w-0">
                  <Code2 className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  <span className="text-[13px] font-bold truncate" style={{ color: pal.text }}>
                    {selectedFile.split('/').pop()}
                  </span>
                </div>
                <button
                  onClick={() => onFileClick(null)}
                  className={`p-1.5 rounded-lg transition-colors flex-shrink-0 ${isDark ? 'text-gray-500 hover:text-white hover:bg-white/10' : 'text-gray-400 hover:text-black hover:bg-black/10'}`}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* path breadcrumb + tabs */}
              <div className="flex items-center gap-0 px-4 py-0 text-[10px] font-mono flex-shrink-0" style={{ borderBottom: `1px solid ${pal.border}` }}>
                <span className="text-gray-500 truncate flex-1 py-1.5">{selectedFile}</span>
                <div className="flex ml-2 flex-shrink-0">
                  <button
                    onClick={() => setCodePanelTab('code')}
                    className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-colors ${codePanelTab === 'code' ? 'text-blue-400 border-b-2 border-blue-400' : (isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600')}`}
                  >
                    Code
                  </button>
                  <button
                    onClick={() => setCodePanelTab('entities')}
                    className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-colors ${codePanelTab === 'entities' ? 'text-blue-400 border-b-2 border-blue-400' : (isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600')}`}
                  >
                    Entities
                  </button>
                </div>
              </div>

              {/* body */}
              <div ref={codeBodyRef} className="flex-1 overflow-auto custom-scrollbar">
                {codePanelTab === 'code' ? (
                  codeContent !== null ? (
                    <pre className={`p-4 text-[12px] leading-[1.65] font-mono whitespace-pre overflow-x-auto ${isDark ? 'text-gray-300' : 'text-gray-800'}`}>
                      {codeContent.split('\n').map((line, i) => {
                        const lineNum = i + 1;
                        const isHL = highlightLine === lineNum;
                        return (
                          <div
                            key={i}
                            data-line={lineNum}
                            className={`flex ${isHL ? (isDark ? 'bg-yellow-400/10' : 'bg-yellow-300/20') : (isDark ? 'hover:bg-white/[0.03]' : 'hover:bg-black/[0.03]')}`}
                          >
                            <span className={`inline-block w-10 text-right pr-4 select-none flex-shrink-0 ${isHL ? 'text-yellow-400 font-bold' : (isDark ? 'text-gray-600' : 'text-gray-400')}`}>{lineNum}</span>
                            <span>{line || ' '}</span>
                          </div>
                        );
                      })}
                    </pre>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-40 text-gray-500 text-[12px]">
                      <p>{codeError || 'No source available'}</p>
                    </div>
                  )
                ) : (
                  <div className="p-4">
                    <div className="space-y-1">
                      {fileEntities.map((n: any) => {
                        const lineNum = n.line_number ?? n.properties?.line_number;
                        return (
                          <div
                            key={n.id}
                            onClick={() => { if (lineNum && codeContent) { setHighlightLine(Number(lineNum)); setCodePanelTab('code'); } }}
                            className={`flex items-center gap-2 py-1.5 px-2 rounded-lg ${isDark ? 'hover:bg-white/5' : 'hover:bg-black/5'} ${lineNum && codeContent ? 'cursor-pointer' : ''}`}
                          >
                            {graphMode === 'icon' ? (
                              <span className="text-[14px] flex-shrink-0">{EMOJI_MAP[n.type] || '❓'}</span>
                            ) : (
                              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: nodeColors[n.type] || '#78909c' }} />
                            )}
                            <span className="text-[12px] font-medium truncate" style={{ color: pal.textSecondary }}>{n.name}</span>
                            <span className="text-[9px] uppercase tracking-wider ml-auto flex-shrink-0" style={{ color: pal.dimText }}>
                              {n.type}{lineNum ? `:${lineNum}` : ''}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* footer */}
              <div className={`px-4 py-2 text-[10px] text-gray-500 uppercase tracking-widest font-black flex-shrink-0 ${isDark ? 'border-t border-white/5 bg-black/40' : 'border-t border-black/5 bg-gray-50'}`}>
                {fileEntities.length} entities
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
