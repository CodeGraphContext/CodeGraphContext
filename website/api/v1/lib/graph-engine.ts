// website/api/v1/lib/graph-engine.ts
import JSZip from "jszip";

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  file?: string;
  properties?: Record<string, any>;
}

export interface GraphEdge {
  from: string;
  to: string;
  type: string;
  properties?: Record<string, any>;
}

export class GraphEngine {
  public nodes = new Map<string, GraphNode>();
  public nameIndex = new Map<string, string[]>();
  public outEdges = new Map<string, GraphEdge[]>();
  public inEdges = new Map<string, GraphEdge[]>();
  public metadata: any = {};

  constructor() {}

  public async loadFromZip(zipBuffer: Buffer | ArrayBuffer) {
    const zip = await JSZip.loadAsync(zipBuffer);
    const nodesFile = zip.file("nodes.jsonl");
    const edgesFile = zip.file("edges.jsonl");
    const metadataFile = zip.file("metadata.json");

    if (!nodesFile || !edgesFile) {
      throw new Error("Invalid CGC bundle: nodes.jsonl and edges.jsonl are required.");
    }

    if (metadataFile) {
      try {
        const metaText = await metadataFile.async("text");
        this.metadata = JSON.parse(metaText);
      } catch (err) {}
    }

    const nodesText = await nodesFile.async("text");
    const nodeLines = nodesText.split("\n");
    for (const line of nodeLines) {
      if (!line.trim()) continue;
      try {
        const data = JSON.parse(line);
        const id = String(data._id ?? data.id);
        const labels = data._labels ?? [];
        const type = labels[0] ? (labels[0].charAt(0).toUpperCase() + labels[0].slice(1)) : 'Other';
        const name = String(data.name ?? data.path ?? 'Unknown');
        const file = String(data.file ?? data.path ?? '');

        const properties: Record<string, any> = {};
        for (const k of Object.keys(data)) {
          if (k !== '_labels' && k !== '_id' && k !== 'id' && k !== '_label') {
            properties[k] = data[k];
          }
        }

        const node: GraphNode = { id, name, type, file, properties };
        this.nodes.set(id, node);

        const nameLower = name.toLowerCase();
        if (!this.nameIndex.has(nameLower)) this.nameIndex.set(nameLower, []);
        this.nameIndex.get(nameLower)!.push(id);

        const parts = name.split(/[./\\]/);
        const simpleName = parts[parts.length - 1].toLowerCase();
        if (simpleName !== nameLower && simpleName.length > 0) {
          if (!this.nameIndex.has(simpleName)) this.nameIndex.set(simpleName, []);
          this.nameIndex.get(simpleName)!.push(id);
        }
      } catch (err) {}
    }

    const edgesText = await edgesFile.async("text");
    const edgeLines = edgesText.split("\n");
    for (const line of edgeLines) {
      if (!line.trim()) continue;
      try {
        const data = JSON.parse(line);
        const from = String(data.from);
        const to = String(data.to);
        const type = String(data.type).toUpperCase();
        const properties = data.properties ?? {};

        const edge: GraphEdge = { from, to, type, properties };

        if (!this.outEdges.has(from)) this.outEdges.set(from, []);
        this.outEdges.get(from)!.push(edge);

        if (!this.inEdges.has(to)) this.inEdges.set(to, []);
        this.inEdges.get(to)!.push(edge);
      } catch (err) {}
    }
  }

  public findDefinitions(target: string): GraphNode[] {
    const targetLower = target.toLowerCase();
    const ids = this.nameIndex.get(targetLower);
    if (!ids) return [];
    
    return ids
      .map(id => this.nodes.get(id))
      .filter((n): n is GraphNode => n !== undefined);
  }

  public findCallers(target: string): { symbol: GraphNode; callers: GraphNode[] }[] {
    const definitions = this.findDefinitions(target);
    const results: { symbol: GraphNode; callers: GraphNode[] }[] = [];

    for (const symbol of definitions) {
      const incoming = this.inEdges.get(symbol.id) || [];
      const callers: GraphNode[] = [];

      for (const edge of incoming) {
        if (edge.type === 'CALLS') {
          const callerNode = this.nodes.get(edge.from);
          if (callerNode) callers.push(callerNode);
        }
      }
      results.push({ symbol, callers });
    }
    return results;
  }

  public findCallees(target: string): { symbol: GraphNode; callees: GraphNode[] }[] {
    const definitions = this.findDefinitions(target);
    const results: { symbol: GraphNode; callees: GraphNode[] }[] = [];

    for (const symbol of definitions) {
      const outgoing = this.outEdges.get(symbol.id) || [];
      const callees: GraphNode[] = [];

      for (const edge of outgoing) {
        if (edge.type === 'CALLS') {
          const calleeNode = this.nodes.get(edge.to);
          if (calleeNode) callees.push(calleeNode);
        }
      }
      results.push({ symbol, callees });
    }
    return results;
  }

  public search(query: string, limit = 30): GraphNode[] {
    const queryLower = query.toLowerCase();
    const matches: { node: GraphNode; score: number }[] = [];

    for (const node of this.nodes.values()) {
      const nameLower = node.name.toLowerCase();
      const fileLower = (node.file || "").toLowerCase();

      let score = 0;
      if (nameLower === queryLower) score = 100;
      else if (nameLower.startsWith(queryLower)) score = 80;
      else if (nameLower.includes(queryLower)) score = 50;
      else if (fileLower.includes(queryLower)) score = 20;

      if (score > 0) matches.push({ node, score });
    }

    return matches
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(m => m.node);
  }

  public getFileStructure(): { files: string[]; structure: Record<string, GraphNode[]> } {
    const files: string[] = [];
    const structure: Record<string, GraphNode[]> = {};

    for (const node of this.nodes.values()) {
      if (node.type.toLowerCase() === 'file') {
        files.push(node.name);
      }
    }

    for (const node of this.nodes.values()) {
      if (node.file && node.type.toLowerCase() !== 'file' && node.type.toLowerCase() !== 'directory') {
        if (!structure[node.file]) structure[node.file] = [];
        structure[node.file].push(node);
      }
    }

    return {
      files: files.sort(),
      structure
    };
  }
}
