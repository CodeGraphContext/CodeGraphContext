import { useRef, useState, useCallback, useEffect, useMemo } from "react";

const NODE_W = 200;
const NODE_H = 40;
const LEVEL_GAP = 280;
const NODE_GAP = 16;
const SLOT_R = 3.5;

interface Props {
  data: { nodes: any[]; links: any[] };
  width: number;
  height: number;
  nodeColors: Record<string, string>;
  edgeColors: Record<string, string>;
  isDark?: boolean;
}

interface EdgeInfo {
  key: string;
  type: string;
  d: string;
  mx: number;
  my: number;
}

export default function FlowchartSVG({
  data,
  width,
  height,
  nodeColors,
  edgeColors,
  isDark = true,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  const [expanded, setExpanded] = useState<Set<number>>(() => new Set());
  const [positions, setPositions] = useState(
    new Map<number, { x: number; y: number }>(),
  );
  const [hoverEdge, setHoverEdge] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [hoverNode, setHoverNode] = useState<number | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(0.65);
  const [dragId, setDragId] = useState<number | null>(null);
  const [showOrphans, setShowOrphans] = useState(false);

  const isPanning = useRef(false);
  const panStart = useRef({ x: 0, y: 0, px: 0, py: 0 });
  const dragStart = useRef<{
    mx: number;
    my: number;
    nx: number;
    ny: number;
  } | null>(null);
  const dirtyNodes = useRef(new Set<number>());
  const pathCache = useRef(
    new Map<string, { d: string; mx: number; my: number }>(),
  );

  /* ── Containment tree ─────────────────────────────────────────────── */

  const { childMap, parentMap, crossLinks } = useMemo(() => {
    const cm = new Map<number, number[]>();
    const pm = new Map<number, number>();
    const cl: { sourceId: number; targetId: number; type: string }[] = [];
    for (const link of data.links) {
      const s =
        typeof link.source === "object" ? link.source.id : link.source;
      const t =
        typeof link.target === "object" ? link.target.id : link.target;
      if (link.type === "CONTAINS") {
        if (!cm.has(s)) cm.set(s, []);
        cm.get(s)!.push(t);
        pm.set(t, s);
      } else {
        cl.push({ sourceId: s, targetId: t, type: link.type });
      }
    }
    return { childMap: cm, parentMap: pm, crossLinks: cl };
  }, [data.links]);

  const nodeMap = useMemo(() => {
    const m = new Map<number, any>();
    for (const n of data.nodes) m.set(n.id, n);
    return m;
  }, [data.nodes]);

  const roots = useMemo(
    () =>
      data.nodes
        .filter((n: any) => !parentMap.has(n.id))
        .map((n: any) => n.id as number),
    [data.nodes, parentMap],
  );

  useEffect(() => {
    setExpanded(new Set(roots));
  }, [roots]);

  const orphanIds = useMemo(
    () => new Set(roots.filter((r) => !(childMap.get(r) || []).some((k) => nodeMap.has(k)))),
    [roots, childMap, nodeMap],
  );

  /* ── Visible nodes (progressive expansion) ────────────────────────── */

  const visibleIds = useMemo(() => {
    const vis = new Set<number>();
    const q = [...roots];
    while (q.length) {
      const id = q.shift()!;
      if (!nodeMap.has(id)) continue;
      if (orphanIds.has(id) && !showOrphans) continue;
      vis.add(id);
      if (expanded.has(id))
        for (const k of childMap.get(id) || []) q.push(k);
    }
    return vis;
  }, [roots, expanded, childMap, nodeMap, orphanIds, showOrphans]);

  /* ── Layout: left-to-right tree ────────────────────────────────────── */

  useEffect(() => {
    const subtreeH = (id: number): number => {
      if (!expanded.has(id) || !visibleIds.has(id)) return NODE_H;
      const kids = (childMap.get(id) || []).filter((k) => visibleIds.has(k));
      if (!kids.length) return NODE_H;
      return kids.reduce((s, k) => s + subtreeH(k) + NODE_GAP, -NODE_GAP);
    };

    const pos = new Map<number, { x: number; y: number }>();
    const place = (id: number, x: number, yCenter: number) => {
      pos.set(id, { x, y: yCenter - NODE_H / 2 });
      if (!expanded.has(id)) return;
      const kids = (childMap.get(id) || []).filter((k) => visibleIds.has(k));
      if (!kids.length) return;
      const total = subtreeH(id);
      let oy = yCenter - total / 2;
      for (const kid of kids) {
        const kh = subtreeH(kid);
        place(kid, x + LEVEL_GAP, oy + kh / 2);
        oy += kh + NODE_GAP;
      }
    };

    const treeRoots = roots.filter((r) => visibleIds.has(r) && !orphanIds.has(r));
    const totalH = treeRoots.reduce(
      (s, r) => s + subtreeH(r) + NODE_GAP * 3,
      0,
    );
    let y = -totalH / 2;
    for (const r of treeRoots) {
      const rh = subtreeH(r);
      place(r, 40, y + rh / 2);
      y += rh + NODE_GAP * 3;
    }

    if (showOrphans) {
      const orphans = roots.filter((r) => orphanIds.has(r) && visibleIds.has(r));
      let maxX = 40;
      for (const [, p] of pos) {
        if (p.x + NODE_W > maxX) maxX = p.x + NODE_W;
      }
      const orphanStartX = maxX + LEVEL_GAP;
      const COLS = 2;
      const COL_W = NODE_W + 20;
      const ROW_H = NODE_H + NODE_GAP;
      const gridTop = -totalH / 2;
      for (let i = 0; i < orphans.length; i++) {
        const col = i % COLS;
        const row = Math.floor(i / COLS);
        pos.set(orphans[i], { x: orphanStartX + col * COL_W, y: gridTop + row * ROW_H });
      }
    }

    pathCache.current.clear();
    setPositions(pos);
  }, [visibleIds, expanded, childMap, roots, orphanIds, showOrphans]);

  /* ── Visible links ─────────────────────────────────────────────────── */

  const visLinks = useMemo(() => {
    const out: {
      key: string;
      sourceId: number;
      targetId: number;
      type: string;
    }[] = [];
    for (const id of visibleIds) {
      if (!expanded.has(id)) continue;
      for (const k of (childMap.get(id) || []).filter((k) =>
        visibleIds.has(k),
      ))
        out.push({
          key: `c-${id}-${k}`,
          sourceId: id,
          targetId: k,
          type: "CONTAINS",
        });
    }
    for (const cl of crossLinks) {
      if (visibleIds.has(cl.sourceId) && visibleIds.has(cl.targetId))
        out.push({
          key: `x-${cl.sourceId}-${cl.targetId}-${cl.type}`,
          ...cl,
        });
    }
    return out;
  }, [visibleIds, expanded, childMap, crossLinks]);

  /* ── Edge paths with dirty-flag caching ────────────────────────────── */

  const edges = useMemo((): EdgeInfo[] => {
    const out: EdgeInfo[] = [];
    for (const lk of visLinks) {
      const sp = positions.get(lk.sourceId);
      const tp = positions.get(lk.targetId);
      if (!sp || !tp) continue;

      const needsUpdate =
        dirtyNodes.current.has(lk.sourceId) ||
        dirtyNodes.current.has(lk.targetId) ||
        !pathCache.current.has(lk.key);

      if (needsUpdate) {
        const sx = sp.x + NODE_W;
        const sy = sp.y + NODE_H / 2;
        const tx = tp.x;
        const ty = tp.y + NODE_H / 2;
        const mx = (sx + tx) / 2;
        pathCache.current.set(lk.key, {
          d: `M${sx},${sy} C${mx},${sy} ${mx},${ty} ${tx},${ty}`,
          mx,
          my: (sy + ty) / 2,
        });
      }

      const cached = pathCache.current.get(lk.key)!;
      out.push({
        key: lk.key,
        type: lk.type,
        d: cached.d,
        mx: cached.mx,
        my: cached.my,
      });
    }
    dirtyNodes.current.clear();
    return out;
  }, [visLinks, positions]);

  /* ── Z-ordered edges (selected on top) ─────────────────────────────── */

  const sortedEdges = useMemo(
    () =>
      [...edges].sort(
        (a, b) =>
          (a.key === selectedEdge ? 2 : a.key === hoverEdge ? 1 : 0) -
          (b.key === selectedEdge ? 2 : b.key === hoverEdge ? 1 : 0),
      ),
    [edges, selectedEdge, hoverEdge],
  );

  /* ── Wheel zoom (passive: false) ───────────────────────────────────── */

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const fn = (e: WheelEvent) => {
      e.preventDefault();
      setZoom((z) =>
        Math.min(4, Math.max(0.04, z * (e.deltaY > 0 ? 0.92 : 1.08))),
      );
    };
    el.addEventListener("wheel", fn, { passive: false });
    return () => el.removeEventListener("wheel", fn);
  }, []);

  /* ── Mouse handlers ────────────────────────────────────────────────── */

  const onBgDown = useCallback(
    (e: React.MouseEvent) => {
      isPanning.current = true;
      panStart.current = {
        x: e.clientX,
        y: e.clientY,
        px: pan.x,
        py: pan.y,
      };
    },
    [pan],
  );

  const onMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isPanning.current) {
        setPan({
          x:
            panStart.current.px +
            (e.clientX - panStart.current.x) / zoom,
          y:
            panStart.current.py +
            (e.clientY - panStart.current.y) / zoom,
        });
      }
      if (dragId !== null && dragStart.current) {
        const dx = (e.clientX - dragStart.current.mx) / zoom;
        const dy = (e.clientY - dragStart.current.my) / zoom;
        setPositions((prev) => {
          const next = new Map(prev);
          next.set(dragId, {
            x: dragStart.current!.nx + dx,
            y: dragStart.current!.ny + dy,
          });
          return next;
        });
        dirtyNodes.current.add(dragId);
      }
    },
    [dragId, zoom],
  );

  const onMouseUp = useCallback(() => {
    isPanning.current = false;
    setDragId(null);
    dragStart.current = null;
  }, []);

  const grabNode = useCallback(
    (id: number, e: React.MouseEvent) => {
      e.stopPropagation();
      isPanning.current = false;
      const pos = positions.get(id);
      if (!pos) return;
      setDragId(id);
      dragStart.current = {
        mx: e.clientX,
        my: e.clientY,
        nx: pos.x,
        ny: pos.y,
      };
    },
    [positions],
  );

  const toggleExpand = useCallback((id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const hasKids = useCallback(
    (id: number) => (childMap.get(id) || []).some((k) => nodeMap.has(k)),
    [childMap, nodeMap],
  );
  const kidCount = useCallback(
    (id: number) =>
      (childMap.get(id) || []).filter((k) => nodeMap.has(k)).length,
    [childMap, nodeMap],
  );

  /* ── Render ────────────────────────────────────────────────────────── */

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      style={{
        background: isDark ? "#020202" : "#f5f5f7",
        cursor: isPanning.current ? "grabbing" : "grab",
      }}
      onMouseDown={onBgDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
    >
      <defs>
        <pattern
          id="fc-grid"
          width={40}
          height={40}
          patternUnits="userSpaceOnUse"
          patternTransform={`translate(${pan.x * zoom + width / 2},${pan.y * zoom + height / 2}) scale(${zoom})`}
        >
          <path
            d="M 40 0 L 0 0 0 40"
            fill="none"
            stroke={isDark ? "#0d0d14" : "#e5e5ea"}
            strokeWidth={0.6}
          />
        </pattern>
        <filter
          id="edgeglow"
          x="-20%"
          y="-20%"
          width="140%"
          height="140%"
        >
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      <rect width={width} height={height} fill="url(#fc-grid)" style={{ pointerEvents: 'none' }} />

      <g
        transform={`translate(${width / 2 + pan.x * zoom},${height / 2 + pan.y * zoom}) scale(${zoom})`}
        style={{ pointerEvents: 'auto' }}
      >
        {/* ── Edges ── */}
        {sortedEdges.map((edge) => {
          const isHov = edge.key === hoverEdge;
          const isSel = edge.key === selectedEdge;
          const isContains = edge.type === "CONTAINS";
          const base = edgeColors[edge.type] || "#555";
          const color = isSel
            ? "#fb923c"
            : isHov
              ? "#f59e0b"
              : isContains
                ? (isDark ? "#4a4a5a" : "#9a9aaa")
                : base;
          const sw = isSel ? 3 : isHov ? 2.5 : isContains ? 1.6 : 2;
          const op = isSel ? 1 : isHov ? 0.95 : isContains ? 0.7 : 0.85;

          return (
            <g key={edge.key}>
              {/* invisible wide hit area */}
              <path
                d={edge.d}
                fill="none"
                stroke="transparent"
                strokeWidth={14}
                onMouseEnter={() => setHoverEdge(edge.key)}
                onMouseLeave={() => setHoverEdge(null)}
                onClick={() =>
                  setSelectedEdge((p) =>
                    p === edge.key ? null : edge.key,
                  )
                }
                style={{ cursor: "pointer" }}
              >
                <title>{edge.type}</title>
              </path>
              {/* visible curve */}
              <path
                d={edge.d}
                fill="none"
                stroke={color}
                strokeWidth={sw}
                opacity={op}
                strokeLinecap="round"
                filter={isSel || isHov ? "url(#edgeglow)" : undefined}
                strokeDasharray={isContains ? undefined : "6 3"}
                style={{
                  pointerEvents: "none",
                  transition: "stroke-width .15s, opacity .15s",
                }}
              />
              {/* edge type label on hover/select */}
              {(isHov || isSel) && !isContains && (
                <g style={{ pointerEvents: "none" }}>
                  <rect
                    x={edge.mx - 32}
                    y={edge.my - 10}
                    width={64}
                    height={20}
                    rx={4}
                    fill={isDark ? "#0a0a12" : "#ffffff"}
                    stroke={color}
                    strokeWidth={0.8}
                    opacity={0.92}
                  />
                  <text
                    x={edge.mx}
                    y={edge.my + 1}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={9}
                    fontWeight={700}
                    fontFamily="Inter,system-ui,sans-serif"
                    fill={color}
                    style={{ letterSpacing: "0.06em" }}
                  >
                    {edge.type}
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* ── Nodes ── */}
        {Array.from(visibleIds).map((id) => {
          const node = nodeMap.get(id);
          const pos = positions.get(id);
          if (!node || !pos) return null;

          const color = nodeColors[node.type] || "#78909c";
          const isHov = id === hoverNode;
          const isExp = expanded.has(id);
          const hk = hasKids(id);
          const kc = kidCount(id);

          return (
            <g
              key={id}
              transform={`translate(${pos.x},${pos.y})`}
              onMouseDown={(e) => grabNode(id, e)}
              onMouseEnter={() => setHoverNode(id)}
              onMouseLeave={() => setHoverNode(null)}
              style={{
                cursor: dragId === id ? "grabbing" : "pointer",
              }}
            >
              {/* hover glow */}
              {isHov && (
                <rect
                  x={-3}
                  y={-3}
                  width={NODE_W + 6}
                  height={NODE_H + 6}
                  rx={9}
                  fill="none"
                  stroke={color}
                  strokeWidth={1.5}
                  opacity={0.25}
                  filter="url(#edgeglow)"
                />
              )}
              {/* body */}
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={6}
                fill={isHov ? (isDark ? "#181822" : "#f0f0f5") : (isDark ? "#0e0e14" : "#ffffff")}
                stroke={color}
                strokeWidth={isHov ? 1.8 : 1}
                opacity={0.95}
              />
              {/* left connection slot */}
              <circle
                cx={0}
                cy={NODE_H / 2}
                r={SLOT_R}
                fill={color}
                opacity={0.5}
              />
              {/* right connection slot */}
              <circle
                cx={NODE_W}
                cy={NODE_H / 2}
                r={SLOT_R}
                fill={color}
                opacity={0.5}
              />
              {/* name label */}
              <text
                x={12}
                y={16}
                fontSize={12}
                fontFamily="Inter,system-ui,sans-serif"
                fontWeight={600}
                fill={isDark ? "#d4d4d8" : "#1a1a1a"}
                style={{ pointerEvents: "none" }}
              >
                {(node.name || "Unknown").length > 22
                  ? (node.name || "").slice(0, 20) + "…"
                  : node.name || "Unknown"}
              </text>
              {/* type badge */}
              <text
                x={12}
                y={33}
                fontSize={8}
                fontFamily="Inter,system-ui,sans-serif"
                fontWeight={700}
                fill={color}
                opacity={0.55}
                style={{
                  pointerEvents: "none",
                  letterSpacing: "0.08em",
                }}
              >
                {(node.type || "").toUpperCase()}
              </text>
              {/* expand / collapse button */}
              {hk && (
                <g
                  onClick={(e) => toggleExpand(id, e)}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    x={NODE_W - 30}
                    y={(NODE_H - 18) / 2}
                    width={24}
                    height={18}
                    rx={4}
                    fill={isExp ? color + "22" : color + "11"}
                    stroke={color}
                    strokeWidth={0.5}
                  />
                  <text
                    x={NODE_W - 18}
                    y={NODE_H / 2 + 1}
                    fontSize={11}
                    fontWeight={700}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill={color}
                    style={{ pointerEvents: "none" }}
                  >
                    {isExp ? "−" : "+" + kc}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </g>

      {/* Orphan modules toggle (fixed position, not affected by pan/zoom) */}
      {orphanIds.size > 0 && (
        <g
          transform={`translate(${width - 200}, 16)`}
          onClick={() => setShowOrphans((v) => !v)}
          style={{ cursor: "pointer" }}
        >
          <rect
            width={180}
            height={28}
            rx={14}
            fill={showOrphans ? (isDark ? "#1e1e2e" : "#e8e8f0") : (isDark ? "#111118" : "#f0f0f5")}
            stroke={showOrphans ? "#f59e0b55" : (isDark ? "#ffffff18" : "#00000018")}
            strokeWidth={1}
          />
          <text
            x={90}
            y={15}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={10}
            fontWeight={700}
            fontFamily="Inter,system-ui,sans-serif"
            fill={showOrphans ? "#f59e0b" : (isDark ? "#666" : "#888")}
            style={{ letterSpacing: "0.06em" }}
          >
            {showOrphans
              ? `HIDE ${orphanIds.size} EXTERNAL`
              : `SHOW ${orphanIds.size} EXTERNAL`}
          </text>
        </g>
      )}
    </svg>
  );
}
