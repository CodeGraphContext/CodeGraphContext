/**
 * Summary Engine — Generates plain-English summaries for code graph nodes.
 *
 * Supports two modes:
 *  1. Heuristic (default) — client-side name/type/relationship analysis
 *  2. LLM-powered (BYOK) — optional Gemini or Mistral API calls for richer summaries
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export interface GraphNode {
  id: number | string;
  name: string;
  type: string;
  filePath?: string;
  parameters?: string[];
  returnType?: string;
  [key: string]: any;
}

export interface GraphLink {
  source: number | string | GraphNode;
  target: number | string | GraphNode;
  type: string;
  [key: string]: any;
}

export interface NodeSummary {
  description: string;
  architecturePosition: string;
  dependencyImpact: string;
  incomingCount: number;
  outgoingCount: number;
  depth: number;
  neighborTypeBreakdown: Record<string, number>;
}

export type LLMProvider = 'gemini' | 'mistral' | 'none';

export interface LLMConfig {
  provider: LLMProvider;
  apiKey: string;
  model?: string;
}

// ─── Heuristic Helpers ───────────────────────────────────────────────────────

/** Split camelCase, PascalCase, snake_case, kebab-case into words */
function splitIdentifier(name: string): string[] {
  return name
    .replace(/([a-z])([A-Z])/g, '$1 $2')      // camelCase → camel Case
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2') // XMLParser → XML Parser
    .replace(/[_\-./\\]/g, ' ')                 // snake_case, kebab-case, paths
    .split(/\s+/)
    .filter(Boolean)
    .map(w => w.toLowerCase());
}

/** Humanize an identifier into a readable phrase */
function humanize(name: string): string {
  const words = splitIdentifier(name);
  if (words.length === 0) return name;
  // Capitalize first word
  words[0] = words[0].charAt(0).toUpperCase() + words[0].slice(1);
  return words.join(' ');
}

/** Detect common verb prefixes and generate an action description */
function describeAction(name: string): string {
  const words = splitIdentifier(name);
  if (words.length === 0) return `Performs an operation`;

  const verb = words[0];
  const rest = words.slice(1).join(' ');

  const verbMap: Record<string, string> = {
    get: 'Retrieves',
    set: 'Sets',
    is: 'Checks whether',
    has: 'Checks if it has',
    can: 'Determines if it can',
    should: 'Determines if it should',
    create: 'Creates',
    make: 'Creates',
    build: 'Builds',
    init: 'Initializes',
    initialize: 'Initializes',
    setup: 'Sets up',
    handle: 'Handles',
    on: 'Handles',
    process: 'Processes',
    parse: 'Parses',
    validate: 'Validates',
    check: 'Checks',
    update: 'Updates',
    delete: 'Deletes',
    remove: 'Removes',
    add: 'Adds',
    insert: 'Inserts',
    fetch: 'Fetches',
    load: 'Loads',
    save: 'Saves',
    store: 'Stores',
    send: 'Sends',
    emit: 'Emits',
    dispatch: 'Dispatches',
    render: 'Renders',
    display: 'Displays',
    show: 'Shows',
    hide: 'Hides',
    toggle: 'Toggles',
    enable: 'Enables',
    disable: 'Disables',
    convert: 'Converts',
    transform: 'Transforms',
    format: 'Formats',
    calculate: 'Calculates',
    compute: 'Computes',
    find: 'Finds',
    search: 'Searches for',
    filter: 'Filters',
    sort: 'Sorts',
    map: 'Maps',
    reduce: 'Reduces',
    merge: 'Merges',
    split: 'Splits',
    join: 'Joins',
    connect: 'Connects',
    disconnect: 'Disconnects',
    open: 'Opens',
    close: 'Closes',
    start: 'Starts',
    stop: 'Stops',
    run: 'Runs',
    execute: 'Executes',
    test: 'Tests',
    log: 'Logs',
    print: 'Prints',
    debug: 'Debugs',
    export: 'Exports',
    import: 'Imports',
  };

  const action = verbMap[verb];
  if (action && rest) {
    return `${action} ${rest}`;
  }
  if (action) {
    return `${action} the value`;
  }
  return `Performs ${humanize(name).toLowerCase()} operation`;
}

/** Generate description based on node type */
function describeByType(node: GraphNode): string {
  const name = humanize(node.name);
  switch (node.type) {
    case 'Repository':
      return `Root repository node representing the entire codebase "${node.name}".`;
    case 'Directory':
      return `Directory "${node.name}" containing related source files and modules.`;
    case 'File':
      return `Source file "${node.name}" that defines code entities used across the project.`;
    case 'Class':
      return `Class "${name}" — a blueprint that encapsulates data and behavior.`;
    case 'Interface':
      return `Interface "${name}" — defines a contract that other types must implement.`;
    case 'Trait':
      return `Trait "${name}" — provides reusable behavior that can be mixed into classes.`;
    case 'Function':
      return `Function that ${describeAction(node.name).toLowerCase()}.`;
    case 'Module':
      return `Module "${name}" — a logical grouping of related functionality.`;
    case 'Variable':
      return `Variable "${name}" — stores a value used within its scope.`;
    case 'Enum':
      return `Enum "${name}" — defines a set of named constant values.`;
    case 'Struct':
      return `Struct "${name}" — a value type that groups related data fields.`;
    case 'Macro':
      return `Macro "${name}" — a compile-time code generation directive.`;
    case 'Record':
      return `Record "${name}" — an immutable data carrier type.`;
    case 'Union':
      return `Union "${name}" — a type that can hold one of several variant types.`;
    case 'Property':
      return `Property "${name}" — an accessor that gets or sets a value.`;
    case 'Annotation':
      return `Annotation "${name}" — provides metadata for code elements.`;
    case 'Parameter':
      return `Parameter "${name}" — an input value passed to a function or method.`;
    default:
      return `Code element "${name}" of type ${node.type}.`;
  }
}

// ─── Core Summary Generator ─────────────────────────────────────────────────

export function generateNodeSummary(
  node: GraphNode,
  allNodes: GraphNode[],
  allLinks: GraphLink[]
): NodeSummary {
  const nodeId = node.id;

  // Compute incoming and outgoing edges
  const incoming = allLinks.filter(l => {
    const targetId = typeof l.target === 'object' ? l.target.id : l.target;
    return targetId === nodeId;
  });
  const outgoing = allLinks.filter(l => {
    const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
    return sourceId === nodeId;
  });

  // Neighbor type breakdown
  const neighborTypeBreakdown: Record<string, number> = {};
  const neighborIds = new Set<number | string>();
  [...incoming, ...outgoing].forEach(link => {
    const otherId = typeof link.source === 'object'
      ? link.source.id === nodeId ? (typeof link.target === 'object' ? link.target.id : link.target) : link.source.id
      : link.source === nodeId ? (typeof link.target === 'object' ? link.target.id : link.target) : link.source;
    neighborIds.add(otherId);
  });
  neighborIds.forEach(nId => {
    const neighbor = allNodes.find(n => n.id === nId);
    if (neighbor) {
      neighborTypeBreakdown[neighbor.type] = (neighborTypeBreakdown[neighbor.type] || 0) + 1;
    }
  });

  // Compute depth in hierarchy via CONTAINS edges
  let depth = 0;
  let currentId: number | string | undefined = nodeId;
  const visited = new Set<number | string>();
  while (currentId !== undefined && !visited.has(currentId)) {
    visited.add(currentId);
    const parentLink = allLinks.find(l => {
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;
      return targetId === currentId && l.type === 'CONTAINS';
    });
    if (parentLink) {
      depth++;
      currentId = typeof parentLink.source === 'object' ? parentLink.source.id : parentLink.source;
    } else {
      break;
    }
  }

  // Generate description
  const description = describeByType(node);

  // Architecture position (breadcrumb path)
  const breadcrumb: string[] = [node.name];
  currentId = nodeId;
  const visitedPath = new Set<number | string>();
  while (currentId !== undefined && !visitedPath.has(currentId)) {
    visitedPath.add(currentId);
    const parentLink = allLinks.find(l => {
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;
      return targetId === currentId && l.type === 'CONTAINS';
    });
    if (parentLink) {
      const parentId = typeof parentLink.source === 'object' ? parentLink.source.id : parentLink.source;
      const parentNode = allNodes.find(n => n.id === parentId);
      if (parentNode) {
        breadcrumb.unshift(parentNode.name);
        currentId = parentId;
      } else {
        break;
      }
    } else {
      break;
    }
  }
  const architecturePosition = breadcrumb.join(' › ');

  // Dependency impact
  const totalAffected = outgoing.length;
  const totalDependsOn = incoming.length;
  let dependencyImpact = '';
  if (totalAffected > 10) {
    dependencyImpact = `High impact — ${totalAffected} downstream elements depend on this. Changes here could cascade widely.`;
  } else if (totalAffected > 3) {
    dependencyImpact = `Moderate impact — ${totalAffected} elements are connected downstream.`;
  } else if (totalAffected > 0) {
    dependencyImpact = `Low impact — only ${totalAffected} element${totalAffected > 1 ? 's' : ''} depend${totalAffected === 1 ? 's' : ''} on this.`;
  } else {
    dependencyImpact = `Leaf node — nothing directly depends on this element.`;
  }
  if (totalDependsOn > 0) {
    dependencyImpact += ` Relies on ${totalDependsOn} upstream element${totalDependsOn > 1 ? 's' : ''}.`;
  }

  return {
    description,
    architecturePosition,
    dependencyImpact,
    incomingCount: incoming.length,
    outgoingCount: outgoing.length,
    depth,
    neighborTypeBreakdown,
  };
}

// ─── Dependency Lists ────────────────────────────────────────────────────────

export interface DependencyEntry {
  nodeId: number | string;
  nodeName: string;
  nodeType: string;
  edgeType: string;
}

export function getIncomingDependencies(
  nodeId: number | string,
  allNodes: GraphNode[],
  allLinks: GraphLink[]
): DependencyEntry[] {
  return allLinks
    .filter(l => {
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;
      return targetId === nodeId;
    })
    .map(l => {
      const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
      const sourceNode = allNodes.find(n => n.id === sourceId);
      return {
        nodeId: sourceId,
        nodeName: sourceNode?.name || String(sourceId),
        nodeType: sourceNode?.type || 'Unknown',
        edgeType: l.type,
      };
    });
}

export function getOutgoingDependencies(
  nodeId: number | string,
  allNodes: GraphNode[],
  allLinks: GraphLink[]
): DependencyEntry[] {
  return allLinks
    .filter(l => {
      const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
      return sourceId === nodeId;
    })
    .map(l => {
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;
      const targetNode = allNodes.find(n => n.id === targetId);
      return {
        nodeId: targetId,
        nodeName: targetNode?.name || String(targetId),
        nodeType: targetNode?.type || 'Unknown',
        edgeType: l.type,
      };
    });
}

// ─── BYOK LLM Summaries ─────────────────────────────────────────────────────

const LLM_STORAGE_KEY = 'cgc-llm-config';

export function saveLLMConfig(config: LLMConfig): void {
  localStorage.setItem(LLM_STORAGE_KEY, JSON.stringify(config));
}

export function loadLLMConfig(): LLMConfig {
  try {
    const stored = localStorage.getItem(LLM_STORAGE_KEY);
    if (stored) return JSON.parse(stored);
  } catch { /* ignore */ }
  return { provider: 'none', apiKey: '' };
}

export function clearLLMConfig(): void {
  localStorage.removeItem(LLM_STORAGE_KEY);
}

export async function generateLLMSummary(
  node: GraphNode,
  allNodes: GraphNode[],
  allLinks: GraphLink[],
  config: LLMConfig
): Promise<string | null> {
  if (config.provider === 'none' || !config.apiKey) return null;

  // Build a compact context about the node
  const incoming = getIncomingDependencies(node.id, allNodes, allLinks);
  const outgoing = getOutgoingDependencies(node.id, allNodes, allLinks);

  const prompt = `You are a code analysis assistant. Given this code element, provide a concise 2-3 sentence plain English summary explaining what it does, its role in the codebase, and why it matters.

Code element:
- Name: ${node.name}
- Type: ${node.type}
- File: ${node.filePath || 'unknown'}
${node.parameters ? `- Parameters: ${node.parameters.join(', ')}` : ''}
${node.returnType ? `- Returns: ${node.returnType}` : ''}

Dependencies (what it uses): ${outgoing.slice(0, 10).map(d => `${d.nodeName} (${d.nodeType})`).join(', ') || 'none'}
Dependents (what uses it): ${incoming.slice(0, 10).map(d => `${d.nodeName} (${d.nodeType})`).join(', ') || 'none'}

Respond with ONLY the summary, no markdown formatting.`;

  try {
    if (config.provider === 'gemini') {
      return await callGemini(prompt, config.apiKey, config.model);
    } else if (config.provider === 'mistral') {
      return await callMistral(prompt, config.apiKey, config.model);
    }
  } catch (err) {
    console.error(`LLM summary failed (${config.provider}):`, err);
    return null;
  }

  return null;
}

async function callGemini(prompt: string, apiKey: string, model?: string): Promise<string> {
  const modelId = model || 'gemini-2.0-flash';
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelId}:generateContent?key=${apiKey}`;
  
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        maxOutputTokens: 200,
        temperature: 0.3,
      },
    }),
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Gemini API error: ${res.status} — ${error}`);
  }

  const data = await res.json();
  return data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
}

async function callMistral(prompt: string, apiKey: string, model?: string): Promise<string> {
  const modelId = model || 'mistral-small-latest';
  const url = 'https://api.mistral.ai/v1/chat/completions';

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: modelId,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 200,
      temperature: 0.3,
    }),
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Mistral API error: ${res.status} — ${error}`);
  }

  const data = await res.json();
  return data?.choices?.[0]?.message?.content || '';
}

// ─── Domain Clustering ───────────────────────────────────────────────────────

export interface DomainCluster {
  id: string;
  label: string;
  nodeIds: (number | string)[];
  color: string;
  x?: number;
  y?: number;
}

const CLUSTER_COLORS = [
  '#a855f7', '#22d3ee', '#4ade80', '#f59e0b', '#ef4444',
  '#ec4899', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316',
  '#14b8a6', '#6366f1', '#e879f9', '#facc15', '#fb923c',
];

/**
 * Groups nodes into domain clusters based on their directory structure.
 * Each top-level directory becomes a "domain."
 */
export function buildDomainClusters(
  nodes: GraphNode[],
  links: GraphLink[]
): DomainCluster[] {
  // Group by top-level directory
  const dirGroups = new Map<string, (number | string)[]>();

  nodes.forEach(node => {
    let dir = 'root';
    if (node.filePath) {
      const parts = node.filePath.replace(/\\/g, '/').split('/').filter(Boolean);
      // Use top 1-2 directory levels as domain
      if (parts.length >= 2) {
        dir = parts.slice(0, 2).join('/');
      } else if (parts.length === 1) {
        dir = parts[0];
      }
    } else {
      // Fallback: use CONTAINS edges to find parent directory
      const parentLink = links.find(l => {
        const targetId = typeof l.target === 'object' ? l.target.id : l.target;
        return targetId === node.id && l.type === 'CONTAINS';
      });
      if (parentLink) {
        const parentId = typeof parentLink.source === 'object' ? parentLink.source.id : parentLink.source;
        const parentNode = nodes.find(n => n.id === parentId);
        if (parentNode && (parentNode.type === 'Directory' || parentNode.type === 'Module')) {
          dir = parentNode.name;
        }
      }
    }

    if (!dirGroups.has(dir)) {
      dirGroups.set(dir, []);
    }
    dirGroups.get(dir)!.push(node.id);
  });

  // Convert to clusters
  const clusters: DomainCluster[] = [];
  let colorIdx = 0;
  dirGroups.forEach((nodeIds, dir) => {
    if (nodeIds.length < 1) return;
    clusters.push({
      id: dir,
      label: humanize(dir.split('/').pop() || dir),
      nodeIds,
      color: CLUSTER_COLORS[colorIdx % CLUSTER_COLORS.length],
    });
    colorIdx++;
  });

  return clusters.sort((a, b) => b.nodeIds.length - a.nodeIds.length);
}

/**
 * Get inter-cluster edges for the domain view.
 */
export function getClusterEdges(
  clusters: DomainCluster[],
  links: GraphLink[]
): { source: string; target: string; count: number }[] {
  const nodeToCluster = new Map<number | string, string>();
  clusters.forEach(c => {
    c.nodeIds.forEach(nId => nodeToCluster.set(nId, c.id));
  });

  const edgeCounts = new Map<string, number>();
  links.forEach(l => {
    const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
    const targetId = typeof l.target === 'object' ? l.target.id : l.target;
    const sourceCluster = nodeToCluster.get(sourceId);
    const targetCluster = nodeToCluster.get(targetId);
    if (sourceCluster && targetCluster && sourceCluster !== targetCluster) {
      const key = `${sourceCluster}||${targetCluster}`;
      edgeCounts.set(key, (edgeCounts.get(key) || 0) + 1);
    }
  });

  return Array.from(edgeCounts.entries()).map(([key, count]) => {
    const [source, target] = key.split('||');
    return { source, target, count };
  });
}
