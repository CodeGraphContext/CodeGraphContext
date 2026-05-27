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

  // Extract and clean extraMetadata to prevent contaminating the strict standardized schema
  const cleanExtra = { ...extraMetadata };
  delete cleanExtra.generator;
  delete cleanExtra.timestamp;
  delete cleanExtra.format_version;
  delete cleanExtra.exported_at;
  delete cleanExtra.graph_metrics;
  delete cleanExtra.name;

  const metadata = {
    ...cleanExtra,
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
    version: version
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
  try {
    // 1. Base64 encode the ZIP blob on the client-side using FileReader
    const base64 = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(",")[1]);
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });

    // 2. Compute SHA256 and size of the base64 payload natively
    const base64Buffer = new TextEncoder().encode(base64);
    const hashBuffer = await window.crypto.subtle.digest('SHA-256', base64Buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const sha256 = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    const size = base64Buffer.length;

    // 3. Stage 1: Handshake
    const handshakeResponse = await fetch('/api/publish', {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Publish-Stage": "handshake"
      },
      body: JSON.stringify({
        repo: repoName,
        version: version,
        sha256,
        size
      })
    });

    if (!handshakeResponse.ok) {
      const errData = await handshakeResponse.json().catch(() => ({}));
      throw new Error(errData.error || `Handshake failed with status ${handshakeResponse.status}`);
    }

    const handshakeData = await handshakeResponse.json();

    // 4. PUT the payload directly to Hugging Face S3 LFS if required (bypasses Vercel completely!)
    if (handshakeData.uploadRequired) {
      const uploadRes = await fetch(handshakeData.uploadUrl, {
        method: "PUT",
        headers: handshakeData.uploadHeaders || {},
        body: base64
      });

      if (!uploadRes.ok) {
        throw new Error(`Failed to upload bundle to LFS storage: ${uploadRes.statusText}`);
      }
    }

    // 5. Stage 2: Commit
    const commitResponse = await fetch('/api/publish', {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Publish-Stage": "commit"
      },
      body: JSON.stringify({
        repo: repoName,
        version: version,
        sha256,
        size,
        displaySize: `${(blob.size / 1024 / 1024).toFixed(2)}MB`
      })
    });

    if (!commitResponse.ok) {
      const errData = await commitResponse.json().catch(() => ({}));
      throw new Error(errData.error || `Commit failed with status ${commitResponse.status}`);
    }

    return await commitResponse.json();

  } catch (err: any) {
    console.error("[CGC Registry Publish Error]:", err);
    throw new Error(err.message || "An unexpected error occurred during publishing.");
  }
}
