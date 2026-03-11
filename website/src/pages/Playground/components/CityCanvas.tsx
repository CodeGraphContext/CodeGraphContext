import { useRef, useEffect, useState, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Stars, Text, Billboard, Environment } from '@react-three/drei';
import * as THREE from 'three';
import { EDGE_STYLES } from './GraphCanvas';

export interface CityCanvasProps {
  data: {
    nodes: Array<{ id: string; label: string; type: string; file: string;[key: string]: any }>;
    edges: Array<{ id: string; source: string; target: string; type: string }>;
  };
  onNodeClick?: (file: string, label: string) => void;
  visibleNodeTypes: Set<string>;
  visibleEdgeTypes: Set<string>;
  customNodeColors?: Record<string, string>;
}

// Mirroring the GitNexus node colors exactly
export const NODE_COLORS: Record<string, string> = {
  file: '#22c55e',
  folder: '#3b82f6',
  class: '#f59e0b',
  interface: '#ec4899',
  function: '#ef5be8',
  method: '#14b8a6',
  struct: '#f97316',
  enum: '#a78bfa',
  module: '#22d3ee',
  namespace: '#7c3aed',
  default: '#6b7280',
};

const getColor = (type: string, custom?: Record<string, string>) => (custom && custom[type.toLowerCase()]) || NODE_COLORS[type.toLowerCase()] || NODE_COLORS.default;

interface LayoutNode {
  id: string;
  node: any; // original node
  children: LayoutNode[];
  width: number;
  depth: number;
  x: number;
  z: number;
  yOffset: number;
  isBuilding: boolean;
  degree: number;
}

const Building = ({ data, onClick, hovered, setHovered, isDimmed, forceLabel, color }: {
  data: LayoutNode;
  onClick?: () => void;
  hovered: boolean;
  setHovered: (id: string | null) => void;
  isDimmed: boolean;
  forceLabel: boolean;
  color: string;
}) => {
  const meshRef = useRef<THREE.Mesh>(null);

  const targetScale = hovered && !isDimmed ? 1.05 : 1;
  const opacity = isDimmed ? 0.3 : 1;
  const displayColor = isDimmed ? '#333333' : color;
  const height = Math.max(2, Math.log1p(data.degree) * 6 + 1);

  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.scale.y = THREE.MathUtils.lerp(meshRef.current.scale.y, targetScale, 0.1);
    }
  });

  return (
    <group position={[data.x, data.yOffset, data.z]}>
      <mesh
        ref={meshRef}
        position={[0, height / 2, 0]}
        onClick={(e) => { e.stopPropagation(); onClick?.(); }}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(data.id); }}
        onPointerOut={() => setHovered(null)}
      >
        <boxGeometry args={[data.width, height, data.depth]} />
        <meshPhysicalMaterial
          color={displayColor}
          emissive={displayColor}
          emissiveIntensity={hovered && !isDimmed ? 0.6 : (isDimmed ? 0.0 : 0.2)}
          roughness={0.1}   // Glossy!
          metalness={0.8}
          clearcoat={1.0}
          clearcoatRoughness={0.1}
          transparent
          opacity={opacity}
        />
        <lineSegments>
          <edgesGeometry args={[new THREE.BoxGeometry(data.width, height, data.depth)]} />
          <lineBasicMaterial color={hovered && !isDimmed ? "#ffffff" : "#000000"} opacity={isDimmed ? 0.1 : 0.5} transparent />
        </lineSegments>
      </mesh>
      {(hovered || forceLabel) && !isDimmed && (
        <Billboard position={[0, height + 2, 0]}>
          <Text
            fontSize={2.5}
            color="#ffffff"
            anchorX="center"
            anchorY="middle"
            outlineWidth={0.2}
            outlineColor="#000000"
            fontWeight="bold"
          >
            {data.node.label}
          </Text>
        </Billboard>
      )}
    </group>
  );
};

const Island = ({ data, onClick, hovered, setHovered, isDimmed, color }: {
  data: LayoutNode;
  onClick?: () => void;
  hovered: boolean;
  setHovered: (id: string | null) => void;
  isDimmed: boolean;
  color: string;
}) => {
  const isFile = data.node.type === 'file';
  const displayColor = isDimmed ? '#222222' : color;
  const height = 1.0;

  return (
    <group position={[data.x, data.yOffset, data.z]}>
      <mesh
        position={[0, height / 2, 0]}
        onClick={(e) => { e.stopPropagation(); onClick?.(); }}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(data.id); }}
        onPointerOut={() => setHovered(null)}
      >
        <boxGeometry args={[data.width, height, data.depth]} />
        <meshPhysicalMaterial
          color={displayColor}
          opacity={isDimmed ? 0.2 : 0.8}
          transparent
          emissive={displayColor}
          emissiveIntensity={hovered && !isDimmed ? 0.3 : 0.05}
          roughness={0.1}
          metalness={0.5}
          clearcoat={0.5}
        />
        <lineSegments>
          <edgesGeometry args={[new THREE.BoxGeometry(data.width, height, data.depth)]} />
          <lineBasicMaterial color={hovered && !isDimmed ? "#ffffff" : "#000000"} opacity={isDimmed ? 0.1 : 0.3} transparent />
        </lineSegments>
      </mesh>
      {/* Island Label - Always facing camera */}
      {!isDimmed && (
        <Billboard position={[0, -1.0, data.depth / 2 + 2]}>
          <Text
            fontSize={isFile ? 2.5 : 4.0}
            color={isFile ? "#bbf7d0" : "#bfdbfe"}
            anchorX="center"
            anchorY="top"
            outlineWidth={0.3}
            outlineColor="#000000"
            fontWeight="bold"
          >
            {data.node.label}
          </Text>
        </Billboard>
      )}
    </group>
  );
};

const Road = ({ edge, isDimmed }: { edge: { sourcePos: THREE.Vector3, targetPos: THREE.Vector3, type: string }, isDimmed: boolean }) => {
  const color = (EDGE_STYLES[edge.type.toLowerCase()]?.color || "#00f7ff");
  const curve = useMemo(() => {
    const midX = (edge.sourcePos.x + edge.targetPos.x) / 2;
    const midZ = (edge.sourcePos.z + edge.targetPos.z) / 2;
    const dist = edge.sourcePos.distanceTo(edge.targetPos);
    const midY = Math.max(edge.sourcePos.y, edge.targetPos.y) + dist * 0.2 + 2;
    return new THREE.QuadraticBezierCurve3(
      edge.sourcePos,
      new THREE.Vector3(midX, midY, midZ),
      edge.targetPos
    );
  }, [edge]);

  return (
    <mesh>
      <tubeGeometry args={[curve, 20, isDimmed ? 0.02 : 0.06, 8, false]} />
      <meshBasicMaterial color={isDimmed ? "#1a1a1a" : color} transparent opacity={isDimmed ? 0.05 : 0.6} />
    </mesh>
  );
};

// WASD camera movement hook
const CameraController = () => {
  const { camera } = useThree();
  const keys = useRef<{ [key: string]: boolean }>({});

  useEffect(() => {
    const down = (e: KeyboardEvent) => { keys.current[e.key.toLowerCase()] = true; };
    const up = (e: KeyboardEvent) => { keys.current[e.key.toLowerCase()] = false; };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
    };
  }, []);

  useFrame((state, delta) => {
    const controls = state.controls as any;
    if (!controls) return;

    const speed = 100 * delta;
    const dir = new THREE.Vector3();
    const right = new THREE.Vector3();

    // Get forward/right vectors from camera orientation
    camera.getWorldDirection(dir);
    // Project direction onto horizontal plane for "walking" feel
    const flatDir = dir.clone();
    flatDir.y = 0;
    flatDir.normalize();
    
    right.crossVectors(camera.up, flatDir).normalize();

    const moveVec = new THREE.Vector3(0, 0, 0);

    if (keys.current['w']) moveVec.addScaledVector(flatDir, speed);
    if (keys.current['s']) moveVec.addScaledVector(flatDir, -speed);
    if (keys.current['a']) moveVec.addScaledVector(right, speed);
    if (keys.current['d']) moveVec.addScaledVector(right, -speed);

    if (moveVec.lengthSq() > 0) {
      camera.position.add(moveVec);
      if (controls.target) {
        controls.target.add(moveVec);
        controls.update();
      }
    }
  });
  return null;
};


export const CityCanvas: React.FC<CityCanvasProps> = ({
  data, onNodeClick, visibleNodeTypes, visibleEdgeTypes, customNodeColors
}) => {
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [clickedNodeId, setClickedNodeId] = useState<string | null>(null);
  const [isControlsOpen, setControlsOpen] = useState<boolean>(true);

  const { layoutNodes, edgeData, adjacency } = useMemo(() => {
    const activeNodes = new Map();
    data.nodes.forEach(n => {
      if (visibleNodeTypes.has(n.type)) {
        activeNodes.set(n.id, n);
      }
    });

    const degrees: Record<string, number> = {};
    const parentMap = new Map<string, string>(); // child -> parent
    const adjacency = new Map<string, Set<string>>(); // standard call/dep connections

    data.edges.forEach(e => {
      degrees[e.source] = (degrees[e.source] || 0) + 1;
      degrees[e.target] = (degrees[e.target] || 0) + 1;

      // Detect hierarchy (e.g. folder contains file, file contains class)
      if (e.type.toLowerCase() === 'contains' || e.type.toLowerCase() === 'defines') {
        if (activeNodes.has(e.source) && activeNodes.has(e.target)) {
          parentMap.set(e.target, e.source);
        }
      } else if (visibleEdgeTypes.has(e.type)) {
        if (!adjacency.has(e.source)) adjacency.set(e.source, new Set());
        if (!adjacency.has(e.target)) adjacency.set(e.target, new Set());
        adjacency.get(e.source)!.add(e.target);
        adjacency.get(e.target)!.add(e.source);
      }
    });

    // Build hierarchy tree
    const rootNodes = new Set<string>();
    const childrenMap = new Map<string, string[]>();

    activeNodes.forEach((node, id) => {
      const parent = parentMap.get(id);
      if (parent) {
        if (!childrenMap.has(parent)) childrenMap.set(parent, []);
        childrenMap.get(parent)!.push(id);
      } else {
        rootNodes.add(id);
      }
    });

    const allLayoutNodes = new Map<string, LayoutNode>();

    // Bottom-Up size calculation
    const calcSize = (id: string): LayoutNode => {
      if (allLayoutNodes.has(id)) return allLayoutNodes.get(id)!;

      const node = activeNodes.get(id)!;
      const childrenIds = childrenMap.get(id) || [];
      const children = childrenIds.map(calcSize);

      const isStructural = node.type === 'folder' || node.type === 'file' || node.type === 'module';
      const isBuilding = !isStructural || children.length === 0;

      let width = 3;
      let depth = 3;

      if (!isBuilding && children.length > 0) {
        const cols = Math.ceil(Math.sqrt(children.length));
        let maxRowWidth = 0;
        let totalDepth = 0;

        let currentRowWidth = 0;
        let currentRowDepth = 0;

        children.forEach((c, idx) => {
          currentRowWidth += c.width + 4;
          currentRowDepth = Math.max(currentRowDepth, c.depth + 4);

          if ((idx + 1) % cols === 0 || idx === children.length - 1) {
            maxRowWidth = Math.max(maxRowWidth, currentRowWidth);
            totalDepth += currentRowDepth;
            currentRowWidth = 0;
            currentRowDepth = 0;
          }
        });

        width = maxRowWidth + 8;
        depth = totalDepth + 8;
      }

      const lNode: LayoutNode = {
        id, node, children, width, depth, x: 0, z: 0, yOffset: 0,
        isBuilding, degree: degrees[id] || 0
      };
      allLayoutNodes.set(id, lNode);
      return lNode;
    };

    const roots = Array.from(rootNodes).map(calcSize);

    // Top-Down position assignment
    const assignPos = (lnode: LayoutNode, px: number, pz: number, py: number) => {
      lnode.x = px;
      lnode.z = pz;
      lnode.yOffset = py;

      if (lnode.children.length > 0) {
        const cols = Math.ceil(Math.sqrt(lnode.children.length));
        let startX = px - lnode.width / 2 + 4;
        let startZ = pz - lnode.depth / 2 + 4;

        let currX = startX;
        let currZ = startZ;
        let rowMaxDepth = 0;

        lnode.children.forEach((c, idx) => {
          const childX = currX + c.width / 2;
          const childZ = currZ + c.depth / 2;

          assignPos(c, childX, childZ, py + (lnode.isBuilding ? 0 : 1));

          currX += c.width + 4;
          rowMaxDepth = Math.max(rowMaxDepth, c.depth + 4);

          if ((idx + 1) % cols === 0) {
            currX = startX;
            currZ += rowMaxDepth;
            rowMaxDepth = 0;
          }
        });
      }
    };

    // Arrange roots
    const rootCols = Math.ceil(Math.sqrt(roots.length));
    let rX = 0, rZ = 0, rowD = 0;

    roots.forEach((rt, idx) => {
      assignPos(rt, rX + rt.width / 2, rZ + rt.depth / 2, 0);
      rX += rt.width + 12;
      rowD = Math.max(rowD, rt.depth + 12);
      if ((idx + 1) % rootCols === 0) {
        rX = 0;
        rZ += rowD;
        rowD = 0;
      }
    });

    // Center everything
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    Array.from(allLayoutNodes.values()).forEach(n => {
      if (n.x - n.width / 2 < minX) minX = n.x - n.width / 2;
      if (n.x + n.width / 2 > maxX) maxX = n.x + n.width / 2;
      if (n.z - n.depth / 2 < minZ) minZ = n.z - n.depth / 2;
      if (n.z + n.depth / 2 > maxZ) maxZ = n.z + n.depth / 2;
    });

    const cx = (minX + maxX) / 2 || 0;
    const cz = (minZ + maxZ) / 2 || 0;

    Array.from(allLayoutNodes.values()).forEach(n => {
      n.x -= cx;
      n.z -= cz;
    });

    const flatNodes = Array.from(allLayoutNodes.values());

    const eData: Array<{ source: string, target: string, type: string, sourcePos: THREE.Vector3, targetPos: THREE.Vector3 }> = [];
    data.edges.filter(e => visibleEdgeTypes.has(e.type) && e.type.toLowerCase() !== 'contains' && e.type.toLowerCase() !== 'defines').forEach(e => {
      const src = allLayoutNodes.get(e.source);
      const tgt = allLayoutNodes.get(e.target);
      if (src && tgt) {
        let srcY = src.yOffset + (src.isBuilding ? Math.max(2, Math.log1p(src.degree) * 6 + 1) : 1);
        let tgtY = tgt.yOffset + (tgt.isBuilding ? Math.max(2, Math.log1p(tgt.degree) * 6 + 1) : 1);
        eData.push({
          source: e.source,
          target: e.target,
          type: e.type,
          sourcePos: new THREE.Vector3(src.x, srcY, src.z),
          targetPos: new THREE.Vector3(tgt.x, tgtY, tgt.z),
        });
      }
    });

    return { layoutNodes: flatNodes, edgeData: eData, adjacency };
  }, [data, visibleNodeTypes, visibleEdgeTypes]);

  // Determine which nodes should be fully visible based on clicks
  const connectedNodes = useMemo(() => {
    if (!clickedNodeId) return null;
    const set = new Set<string>();
    set.add(clickedNodeId);
    const neighbors = adjacency.get(clickedNodeId);
    if (neighbors) {
      neighbors.forEach(n => set.add(n));
    }

    // 1. Highlight children of all active nodes (recursive descent)
    // This ensures that if a file/folder is connected, all its buildings light up
    const initialActive = Array.from(set);
    for (const active of initialActive) {
      const stack = [active];
      while (stack.length > 0) {
        const curr = stack.pop()!;
        for (const e of data.edges) {
          if ((e.type.toLowerCase() === 'contains' || e.type.toLowerCase() === 'defines') && e.source === curr) {
            if (!set.has(e.target)) {
              set.add(e.target);
              stack.push(e.target);
            }
          }
        }
      }
    }

    // 2. Highlight parent containers of everything to keep the hierarchy context
    const allActive = Array.from(set);
    for (const active of allActive) {
      let currentId: string | null = active;
      while (currentId) {
        let parentId: string | null = null;
        for (const e of data.edges) {
          if ((e.type.toLowerCase() === 'contains' || e.type.toLowerCase() === 'defines') && e.target === currentId) {
            parentId = e.source;
            break;
          }
        }
        if (parentId) {
          set.add(parentId);
          currentId = parentId;
        } else {
          break;
        }
      }
    }

    return set;
  }, [clickedNodeId, adjacency, data.edges]);

  return (
    <div className="relative w-full h-full bg-[#06060a]">
      <Canvas
        camera={{ position: [0, 80, 120], fov: 60 }}
        onPointerMissed={() => setClickedNodeId(null)}
      >
        <CameraController />
        <fog attach="fog" args={['#06060a', 150, 1500]} />
        <ambientLight intensity={1.5} />
        <hemisphereLight groundColor="#0a0a10" color="#ffffff" intensity={1.0} />
        <directionalLight position={[20, 50, 20]} intensity={2.5} color="#ffffff" castShadow />
        <pointLight position={[-20, 20, -20]} intensity={2.0} color="#7c3aed" />

        {/* Base Grid */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.5, 0]}>
          <planeGeometry args={[2000, 2000]} />
          <meshStandardMaterial color="#0a0a10" roughness={0.8} />
        </mesh>
        <gridHelper args={[2000, 400, '#2a2a3a', '#101018']} position={[0, -0.4, 0]} />

        {layoutNodes.map(ln => {
          const isDimmed = connectedNodes !== null && !connectedNodes.has(ln.id);
          const forceLabel = connectedNodes !== null && connectedNodes.has(ln.id) && ln.isBuilding;

          if (ln.isBuilding) {
            return (
              <Building
                key={ln.id}
                data={ln}
                color={getColor(ln.node.type, customNodeColors)}
                hovered={hoveredNodeId === ln.id}
                setHovered={setHoveredNodeId}
                isDimmed={isDimmed}
                forceLabel={forceLabel}
                onClick={() => {
                  setClickedNodeId(ln.id);
                  if (onNodeClick) onNodeClick(ln.node.file, ln.node.label);
                }}
              />
            );
          } else {
            return (
              <Island
                key={ln.id}
                data={ln}
                color={getColor(ln.node.type, customNodeColors)}
                hovered={hoveredNodeId === ln.id}
                setHovered={setHoveredNodeId}
                isDimmed={isDimmed}
                onClick={() => {
                  setClickedNodeId(ln.id);
                  if (onNodeClick) onNodeClick(ln.node.file, ln.node.label);
                }}
              />
            );
          }
        })}

        {edgeData.map((e, idx) => {
          const isDimmededge = connectedNodes !== null && (!connectedNodes.has(e.source) || !connectedNodes.has(e.target));
          return <Road key={`edge-${idx}`} edge={e} isDimmed={isDimmededge} />;
        })}

        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          minDistance={10}
          maxDistance={400}
          maxPolarAngle={Math.PI / 2 - 0.05}
          makeDefault // Required for manual camera updates to not fight controls
        />
        <Stars radius={200} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />
        <Environment preset="city" />
      </Canvas>

      <div className="absolute top-6 left-1/2 -translate-x-1/2 bg-[#12121c]/90 border border-[#7c3aed]/50 px-6 py-2 rounded-full text-[#7c3aed] text-sm font-bold tracking-widest uppercase backdrop-blur-md shadow-[0_0_20px_rgba(124,58,237,0.3)] pointer-events-none z-10">
        CodeCity Explorer (Beta)
      </div>
      <div className="absolute bottom-6 right-6 flex flex-col items-end gap-2 text-right select-none z-10">
        <div className="bg-[#12121c]/80 border border-[#7c3aed]/30 px-4 py-3 rounded-lg backdrop-blur-sm shadow-lg pointer-events-auto transition-all duration-300">
          <div 
            className="flex justify-between items-center cursor-pointer group"
            onClick={() => setControlsOpen(!isControlsOpen)}
          >
            <div className="text-[#a78bfa] text-[10px] font-bold tracking-[0.2em] uppercase transition-colors group-hover:text-white">
              Navigation Controls
            </div>
            <div className="text-[#a78bfa] ml-4 transition-transform duration-300 group-hover:text-white">
              {isControlsOpen ? '▼' : '▲'}
            </div>
          </div>
          
          {isControlsOpen && (
            <div className="flex flex-col gap-2 text-xs font-mono mt-3 pt-3 border-t border-[#7c3aed]/30">
              <div className="flex justify-between gap-6 items-center">
                <span className="text-gray-400">Fly Camera</span>
                <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">W A S D</span>
              </div>
              <div className="flex justify-between gap-6 items-center">
                <span className="text-gray-400">Orbit / Look</span>
                <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">L-Click Drag</span>
              </div>
              <div className="flex justify-between gap-6 items-center">
                <span className="text-gray-400">Zoom</span>
                <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">Scroll</span>
              </div>
              <div className="flex justify-between gap-6 items-center">
                <span className="text-gray-400">Isolate Node</span>
                <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">Click Building</span>
              </div>
              <div className="flex justify-between gap-6 items-center">
                <span className="text-gray-400">Reset View</span>
                <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">Click Void</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
