// lib/cgc-exporter.ts
// Client-side utility for packaging, downloading, and publishing CodeGraphContext (.cgc) bundles

import JSZip from "jszip";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  file?: string;
  val?: number;
  properties?: Record<string, any>;
}

interface GraphLink {
  id?: string;
  source: string | { id: string };
  target: string | { id: string };
  type: string;
}

export async function packageCgcBundle(
  repoName: string,
  nodes: GraphNode[],
  links: GraphLink[],
  version: string = "1.0.0",
  extraMetadata?: Record<string, any>
): Promise<Blob> {
  const zip = new JSZip();

  // 1. Format nodes.jsonl
  const nodesJsonl = nodes
    .map(node => {
      const labels = [node.type.toLowerCase()];
      const props = node.properties || {};
      return JSON.stringify({
        _id: Number(node.id) || node.id,
        _labels: labels,
        name: node.name,
        type: node.type,
        file: node.file || "",
        val: node.val || 2,
        ...props
      });
    })
    .join("\n") + "\n";
  zip.file("nodes.jsonl", nodesJsonl);

  // 2. Format edges.jsonl
  const edgesJsonl = links
    .map((link, idx) => {
      const fromId = typeof link.source === "object" ? link.source.id : link.source;
      const toId = typeof link.target === "object" ? link.target.id : link.target;
      return JSON.stringify({
        from: Number(fromId) || fromId,
        to: Number(toId) || toId,
        type: (link.type || "CONTAINS").toLowerCase(),
        id: idx
      });
    })
    .join("\n") + "\n";
  zip.file("edges.jsonl", edgesJsonl);

  // 3. Format metadata.json
  let standardisedName = "";
  if (repoName.includes("/")) {
    const owner = repoName.split('/')[0];
    const repo = repoName.split('/')[1];
    const branch = extraMetadata?.branch || "main";
    const commit = extraMetadata?.commit || extraMetadata?.version || version || "latest";
    const cleanCommit = commit.length === 40 && /^[0-9a-fA-F]+$/.test(commit) ? commit.substring(0, 7) : commit;
    standardisedName = `${owner}__${repo}__${branch}__${cleanCommit}.cgc`;
  } else {
    standardisedName = `${repoName}.cgc`;
  }

  const metadata = {
    format_version: "1.0.0",
    generator: "WASMv0.0.1",
    exported_at: new Date().toISOString(),
    name: standardisedName,
    graph_metrics: {
      total_nodes: nodes.length,
      total_edges: links.length
    },
    // UI dynamic context keys
    repo: repoName,
    version: version,
    ...extraMetadata
  };
  zip.file("metadata.json", JSON.stringify(metadata, null, 2));

  // Generate the zip blob
  return await zip.generateAsync({ type: "blob" });
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function publishCgcBundle(
  blob: Blob,
  repoName: string,
  version: string
): Promise<{ success: boolean; message: string; entry?: any }> {
  const url = `/api/publish?repo=${encodeURIComponent(repoName)}&version=${encodeURIComponent(version)}`;
  
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/octet-stream"
    },
    body: blob
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    console.error("[CGC Registry API Error]:", errData);
    const errMsg = errData.error || `Server returned status ${response.status}`;
    const details = errData.details ? ` (${errData.details})` : "";
    throw new Error(`${errMsg}${details}`);
  }

  return await response.json();
}
