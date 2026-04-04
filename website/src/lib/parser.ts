import JSZip from "jszip";

/**
 * Parses files into a high-fidelity AST graph using a Web Worker.
 * Ensures the main thread stays highly responsive even for 1000+ files.
 */
export function parseFilesIntoGraph(
  files: { path: string, content: string }[], 
  onProgressTracker?: (progressMsg: string, percentage: number) => void
): Promise<{ nodes: any[], links: any[], files: string[] }> {
  return new Promise((resolve, reject) => {
    // Vite built-in worker support
    const worker = new Worker(new URL('./parser.worker.ts', import.meta.url), { type: 'module' });
    
    worker.onmessage = (e) => {
      const { type, payload } = e.data;
      if (type === 'PROGRESS') {
        if (onProgressTracker) onProgressTracker(payload.msg, payload.percent);
      } else if (type === 'DONE') {
        resolve(payload);
        worker.terminate();
      } else if (type === 'ERROR') {
        reject(new Error(payload));
        worker.terminate();
      }
    };
    
    worker.onerror = (e) => {
      reject(e);
      worker.terminate();
    };

    // The main thread sends groups of messages to the worker
    const CHUNK_SIZE = 50;
    for (let i = 0; i < files.length; i += CHUNK_SIZE) {
      const chunk = files.slice(i, i + CHUNK_SIZE);
      worker.postMessage({ type: 'ADD_FILES', files: chunk });
    }
    
    worker.postMessage({ type: 'START' });
  });
}


// UPLOADER UTILITIES
export async function readDirectoryRecursive(dirHandle: any, prefix = "") {
  let files: { path: string, content: string }[] = [];
  for await (const entry of dirHandle.values()) {
    if (entry.kind === 'file') {
      if (entry.name.match(/\.(js|ts|jsx|tsx|py|c|h|cpp|hpp|cc|cs|go|rs|rb|php|swift|kt|kts|dart)$/)) {
        const file = await entry.getFile();
        files.push({ path: `${prefix}/${entry.name}`, content: await file.text() });
      }
    } else if (entry.kind === 'directory') {
      if (!['node_modules', '.git', 'dist', 'build', '.idea', '__pycache__'].includes(entry.name)) {
        files = files.concat(await readDirectoryRecursive(entry, `${prefix}/${entry.name}`));
      }
    }
  }
  return files;
}

export async function unzipFiles(zipBuffer: ArrayBuffer) {
  const jszip = await JSZip.loadAsync(zipBuffer);
  const files: { path: string, content: string }[] = [];
  const promises: any[] = [];
  jszip.forEach((relativePath, zipEntry) => {
    if (!zipEntry.dir && relativePath.match(/\.(js|ts|jsx|tsx|py|c|h|cpp|hpp|cc|cs|go|rs|rb|php|swift|kt|kts|dart)$/) && !relativePath.includes("node_modules") && !relativePath.includes(".git/")) {
      promises.push(zipEntry.async('text').then(content => { files.push({ path: relativePath, content }); }));
    }
  });
  await Promise.all(promises);
  return files;
}

export async function fetchGithubRepoFiles(url: string, onProgress?: (msg: string) => void) {
  const match = url.match(/github\.com\/([^/]+)\/([^/]+)/);
  if (!match) throw new Error("Invalid GitHub URL");
  const [_, owner, repoName] = match;
  let treeUrl = `https://api.github.com/repos/${owner}/${repoName}/git/trees/main?recursive=1`;
  let res = await fetch(treeUrl);
  if (!res.ok) {
     treeUrl = `https://api.github.com/repos/${owner}/${repoName}/git/trees/master?recursive=1`;
     res = await fetch(treeUrl);
  }
  if (!res.ok) throw new Error("Could not fetch repo.");
  const data = await res.json();
  const filePaths = data.tree
    .filter((t: any) => t.type === "blob")
    .map((t: any) => t.path)
    .filter((p: string) => p.match(/\.(js|ts|jsx|tsx|py|c|h|cpp|hpp|cc|cs|go|rs|rb|php|swift|kt|kts|dart)$/) && !p.includes("node_modules") && !p.includes(".git"));
  const files: { path: string, content: string }[] = [];
  for (let i = 0; i < Math.min(filePaths.length, 150); i += 10) {
    const batch = filePaths.slice(i, i + 10);
    await Promise.all(batch.map(async (path: string) => {
      try {
        let r = await fetch(`https://raw.githubusercontent.com/${owner}/${repoName}/main/${path}`);
        if (!r.ok) r = await fetch(`https://raw.githubusercontent.com/${owner}/${repoName}/master/${path}`);
        if (r.ok) files.push({ path, content: await r.text() });
      } catch (err) { }
    }));
  }
  return files;
}
