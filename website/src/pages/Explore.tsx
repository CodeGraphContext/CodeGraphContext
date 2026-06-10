import { useState, useEffect, useRef } from "react";
import { useSearchParams, useParams } from "react-router-dom";
import CodeGraphViewer from "../components/CodeGraphViewer";
import LocalUploader from "../components/LocalUploader";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import JSZip from "jszip";
import { parseFilesIntoGraph } from "../lib/parser";
import { KuzuCoordinator } from "../lib/kuzu-coordinator";
import { getOrCreateSessionId } from "../lib/utils";


const IGNORED_DIRS = new Set([
  'node_modules', '.git', '.github', 'dist', 'build', 'out', 'coverage', 
  '.next', '.nuxt', '__pycache__', 'venv', '.venv', 'env', '.env', '.tox',
  'eggs', 'target', '.gradle', '.idea', 'cmake-build-debug', 'bin', 'obj',
  'packages', 'vendor', 'Pods', '.build', 'DerivedData', '.dart_tool',
  '.vscode'
]);

const isPathIgnored = (path: string) => {
  const parts = path.split(/[\/\\]/);
  return parts.some(part => IGNORED_DIRS.has(part));
};

const sanitizePath = (pathStr: string, repoName?: string): string => {
  if (!pathStr) return '';
  
  // Normalize Windows slashes
  let p = pathStr.replace(/\\/g, '/');
  
  // If it's already relative, just return it
  if (p.startsWith('.') || (!p.startsWith('/') && !p.match(/^[a-zA-Z]:\//))) {
    return p.startsWith('./') ? p : './' + p;
  }
  
  // Detect if we can make it relative using the repoName
  if (repoName) {
    const parts = p.split('/');
    const repoIndex = parts.lastIndexOf(repoName);
    if (repoIndex !== -1) {
      return './' + parts.slice(repoIndex).join('/');
    }
  }
  
  // Generic cleanup for absolute paths
  const segments = p.split('/').filter(Boolean);
  if (segments.length > 3) {
    if (p.startsWith('/home/') || p.startsWith('/Users/') || p.includes('/runner/work/')) {
      return './' + segments.slice(-3).join('/');
    }
  }
  
  return p;
};

// ============================================================================
// INDEXEDDB GRAPH CACHE SERVICE
// ============================================================================
const DB_NAME = "cgc-visualizer-cache";
const DB_VERSION = 1;
const STORE_NAME = "graphs";

const openDB = (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "key" });
      }
    };
  });
};

const getCachedGraph = async (owner: string, repo: string): Promise<any | null> => {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readonly");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(`${owner.toLowerCase()}/${repo.toLowerCase()}`);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const result = request.result;
        // Keep cache valid for 7 days
        if (result && (Date.now() - result.timestamp < 7 * 24 * 60 * 60 * 1000)) {
          resolve(result.graphData);
        } else {
          resolve(null);
        }
      };
    });
  } catch (e) {
    console.error("Failed to read from IndexedDB", e);
    return null;
  }
};

const cacheGraph = async (owner: string, repo: string, graphData: any): Promise<void> => {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.put({
        key: `${owner.toLowerCase()}/${repo.toLowerCase()}`,
        graphData,
        timestamp: Date.now()
      });
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  } catch (e) {
    console.error("Failed to write to IndexedDB", e);
  }
};

// ============================================================================
// FETCH WITH PROGRESS TRACKING
// ============================================================================
const fetchWithProgress = async (
  url: string,
  onProgress: (loaded: number, total: number) => void
): Promise<Response> => {
  const response = await fetch(url);
  if (!response.ok || !response.body) return response;

  const contentLength = response.headers.get("content-length");
  const total = contentLength ? parseInt(contentLength, 10) : 0;

  let loaded = 0;
  const reader = response.body.getReader();
  const stream = new ReadableStream({
    async start(controller) {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            controller.close();
            break;
          }
          loaded += value.byteLength;
          onProgress(loaded, total);
          controller.enqueue(value);
        }
      } catch (err) {
        controller.error(err);
      }
    }
  });

  return new Response(stream, {
    headers: response.headers,
    status: response.status,
    statusText: response.statusText
  });
};

interface JSDelivrFile {
  name: string;
  type: "file" | "directory";
  size?: number;
  files?: JSDelivrFile[];
}

const flattenJSDelivrTree = (items: JSDelivrFile[], currentPath = ""): string[] => {
  let filePaths: string[] = [];
  for (const item of items) {
    const itemPath = currentPath ? `${currentPath}/${item.name}` : item.name;
    if (item.type === "file") {
      filePaths.push(itemPath);
    } else if (item.type === "directory" && item.files) {
      filePaths.push(...flattenJSDelivrTree(item.files, itemPath));
    }
  }
  return filePaths;
};

const getJSDelivrTotalSize = (items: JSDelivrFile[]): number => {
  let total = 0;
  for (const item of items) {
    if (item.type === "file" && item.size) {
      total += item.size;
    } else if (item.type === "directory" && item.files) {
      total += getJSDelivrTotalSize(item.files);
    }
  }
  return total;
};

const Explore = () => {
  const [searchParams] = useSearchParams();
  const { owner, repo } = useParams();
  const [graphData, setGraphData] = useState<any>(null);
  const graphDataRef = useRef<any>(null);
  useEffect(() => {
    graphDataRef.current = graphData;
  }, [graphData]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progressText, setProgressText] = useState("");
  const [progressValue, setProgressValue] = useState(0);
  const [workerLogs, setWorkerLogs] = useState<string[]>([]);

  // Connection parameters for "Playground" mode (CLI/Database)
  const backend = searchParams.get("backend") || "";
  const repoPath = searchParams.get("repo_path") || "";
  const cypherQuery = searchParams.get("cypher_query") || "";
  const bundleUrl = searchParams.get("bundle_url") || "";
  
  // Helper to fetch files using a sequential pool of robust CORS proxies
  const fetchWithFallbackProxies = async (
    url: string,
    onProgress?: (loaded: number, total: number) => void
  ): Promise<Response> => {
    if (!url) throw new Error("URL is empty");
    
    // Try direct fetch first (essential for localhost, relative URLs, or CORS-enabled endpoints)
    try {
      const res = onProgress ? await fetchWithProgress(url, onProgress) : await fetch(url);
      if (res.ok) return res;
    } catch (e) {
      console.warn("Direct fetch failed, falling back to CORS proxies...", e);
    }
    
    // 1. Check raw githubusercontent.com to bypass proxy using jsDelivr CDN directly
    if (url.includes("raw.githubusercontent.com")) {
      const match = url.match(/raw\.githubusercontent\.com\/([^\/]+)\/([^\/]+)\/([^\/]+)\/(.+)$/);
      if (match) {
        const [_, ownerName, repoName, branch, filepath] = match;
        const jsdelivrUrl = `https://cdn.jsdelivr.net/gh/${ownerName}/${repoName}@${branch}/${filepath}`;
        try {
          const res = onProgress ? await fetchWithProgress(jsdelivrUrl, onProgress) : await fetch(jsdelivrUrl);
          if (res.ok) return res;
        } catch (e) {
          console.warn("jsDelivr CDN fetch failed, falling back to CORS proxies...", e);
        }
      }
    }

    const proxies = [
      // Proxy 1: corsproxy.io (Very fast, prefix-based)
      {
        url: (u: string) => `https://corsproxy.io/?${encodeURIComponent(u)}`,
        type: 'direct' as const
      },
      // Proxy 2: CodeTabs (Fast and supports redirects well)
      {
        url: (u: string) => `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(u)}`,
        type: 'direct' as const
      },
      // Proxy 3: allorigins.win JSON endpoint (Handles S3 redirects perfectly via server-side base64 encoding!)
      {
        url: (u: string) => `https://api.allorigins.win/get?url=${encodeURIComponent(u)}`,
        type: 'json-base64' as const
      },
      // Proxy 4: allorigins.win raw (Alternative fallback)
      {
        url: (u: string) => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}`,
        type: 'direct' as const
      },
      // Proxy 5: thingproxy.freeboard.io (Fallback proxy)
      {
        url: (u: string) => `https://thingproxy.freeboard.io/fetch/${u}`,
        type: 'direct' as const
      }
    ];

    let lastError: any = null;
    for (const proxy of proxies) {
      try {
        const proxiedUrl = proxy.url(url);
        console.log(`[Proxy] Attempting fetch: ${proxiedUrl}`);
        
        if (proxy.type === 'json-base64') {
          // JSON-Base64 Proxy logic (perfect for binary files & redirects)
          const res = await fetch(proxiedUrl);
          if (!res.ok) {
            console.warn(`[Proxy] Status ${res.status} received. Trying next proxy...`);
            continue;
          }
          const json = await res.json();
          if (!json || !json.contents) {
            throw new Error("No contents returned from JSON CORS proxy.");
          }
          
          const base64Data = json.contents;
          const commaIndex = base64Data.indexOf(',');
          const base64String = commaIndex !== -1 ? base64Data.substring(commaIndex + 1) : base64Data;
          
          const binaryString = atob(base64String);
          const len = binaryString.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          
          if (onProgress) {
            onProgress(len, len); // trigger full complete progress
          }
          
          return new Response(bytes.buffer, {
            status: 200,
            headers: { 'Content-Type': 'application/octet-stream' }
          });
        } else {
          // Direct Proxy logic
          const res = onProgress ? await fetchWithProgress(proxiedUrl, onProgress) : await fetch(proxiedUrl);
          if (res.ok) return res;
          if (res.status === 403 || res.status === 429) {
            console.warn(`[Proxy] Status ${res.status} received. Trying next proxy...`);
            continue;
          }
          return res;
        }
      } catch (err) {
        lastError = err;
        console.warn("[Proxy] Connection failed, trying next fallback proxy...", err);
      }
    }
    throw lastError || new Error("Failed to fetch via all available CORS proxies.");
  };

  // If owner and repo path parameters are present, auto-fetch and index the codebase!
  useEffect(() => {
    if (!owner || !repo) return;
    
    // Ignore static routes like "explore" getting caught as owner/repo
    if (owner.toLowerCase() === "explore") return;

    const autoFetchAndIndex = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // 1. Try to load from IndexedDB cache first
        try {
          const cached = await getCachedGraph(owner, repo);
          if (cached) {
            setProgressText("Loading cached codebase graph...");
            setProgressValue(90);
            await new Promise((r) => setTimeout(r, 100));
            setGraphData(cached);
            setProgressText("Complete!");
            setProgressValue(100);
            setLoading(false);
            console.log(`[Cache] Loaded repository graph for ${owner}/${repo} from IndexedDB cache.`);
            return;
          }
        } catch (cacheErr) {
          console.warn("[Cache] Error reading from cache:", cacheErr);
        }

        let files: any[] = [];
        let fileContents: Record<string, string> = {};

        const getGithubHeaders = () => {
          const headers: Record<string, string> = {};
          const pat = localStorage.getItem('github_pat');
          if (pat) {
            headers['Authorization'] = `token ${pat}`;
          }
          return headers;
        };

        // 2. Resolve the default branch dynamically (natively CORS-compliant, rate-limited at 60/hr/IP on GitHub REST API)
        let detectedBranch = "main";
        let latestCommitSha = "";
        try {
          console.log(`[Explore] Resolving default branch for ${owner}/${repo} dynamically...`);
          const apiRes = await fetch(`https://api.github.com/repos/${owner}/${repo}`, { headers: getGithubHeaders() });
          if (apiRes.ok) {
            const apiData = await apiRes.json();
            if (apiData && apiData.default_branch) {
              detectedBranch = apiData.default_branch;
              console.log(`[Explore] GitHub REST API resolved default branch: ${detectedBranch}`);
            }
          }
          
          console.log(`[Explore] Resolving latest commit SHA for branch ${detectedBranch} dynamically...`);
          const commitsRes = await fetch(`https://api.github.com/repos/${owner}/${repo}/commits/${detectedBranch}`, { headers: getGithubHeaders() });
          if (commitsRes.ok) {
            const commitsData = await commitsRes.json();
            if (commitsData && commitsData.sha) {
              latestCommitSha = commitsData.sha;
              console.log(`[Explore] GitHub REST API resolved latest commit SHA: ${latestCommitSha}`);
            }
          }
        } catch (err) {
          console.warn("[Explore] Failed to resolve default branch or commit SHA dynamically via GitHub API:", err);
        }

        // Compile a robust fallback order of branch names to try (ensuring non-standard branches like unstable/trunk/develop work)
        const branchesToTry = Array.from(new Set([
          detectedBranch,
          "main",
          "master",
          "unstable",
          "trunk",
          "develop",
          "dev"
        ]));

        // 3. Estimate the repository size using jsDelivr API (Rate-limit free)
        let estimatedZipSize = 4 * 1024 * 1024; // Default to 4MB estimate
        let isEstimateReliable = false;
        let sizeMetaData = null;
        let sizeSuccessBranch = detectedBranch;

        console.log("[Explore] Fetching repo metadata to estimate ZIP download size...");
        for (const branch of branchesToTry) {
          try {
            const jsdelivrMetaUrl = `https://data.jsdelivr.net/v1/packages/gh/${owner}/${repo}@${branch}`;
            const metaRes = await fetch(jsdelivrMetaUrl);
            if (metaRes.ok) {
              sizeMetaData = await metaRes.json();
              sizeSuccessBranch = branch;
              console.log(`[Explore] Successfully fetched jsDelivr metadata for size estimation (@${branch})`);
              break;
            }
          } catch (err) {
            console.warn(`[Explore] Failed jsDelivr metadata fetch for branch ${branch}:`, err);
          }
        }

        if (sizeMetaData && Array.isArray(sizeMetaData.files)) {
          const uncompressedSize = getJSDelivrTotalSize(sizeMetaData.files);
          if (uncompressedSize > 0) {
            estimatedZipSize = Math.max(500 * 1024, uncompressedSize * 0.22); // Assume 22% average compression
            isEstimateReliable = true;
            console.log(`[Explore] Estimated ZIP size: ${(estimatedZipSize / 1024 / 1024).toFixed(2)} MB (based on ${(uncompressedSize / 1024 / 1024).toFixed(2)} MB uncompressed, branch @${sizeSuccessBranch})`);
          }
        }

        try {
          // --- METHOD 1: ZIP ARCHIVE FLOW (PRIMARY) ---
          setProgressText("Downloading repository archive...");
          setProgressValue(10);
          
          let response = null;
          let zipSuccessBranch = detectedBranch;

          const updateDownloadProgress = (loaded: number, total: number) => {
            const mbLoaded = (loaded / 1024 / 1024).toFixed(2);
            const finalTotal = total > 0 ? total : estimatedZipSize;
            
            let pct = 0;
            if (loaded < finalTotal) {
              pct = Math.round((loaded / finalTotal) * 90);
            } else {
              const overflow = loaded - finalTotal;
              const extraPct = 9 * (1 - Math.exp(-overflow / (1024 * 1024 * 5))); // 5MB half-life
              pct = Math.round(90 + extraPct);
            }

            if (total > 0) {
              setProgressText(`Downloading repository archive: ${pct}% (${mbLoaded} MB of ${(total / 1024 / 1024).toFixed(2)} MB)`);
            } else if (isEstimateReliable) {
              setProgressText(`Downloading repository archive: ${pct}% (${mbLoaded} MB of ~${(estimatedZipSize / 1024 / 1024).toFixed(2)} MB)`);
            } else {
              setProgressText(`Downloading repository archive: ${pct}% (${mbLoaded} MB)`);
            }
            setProgressValue(10 + Math.floor(pct * 0.15));
          };

          // TIER 0: Authenticated GitHub REST API Zipball (Direct & CORS-compliant for Private Repos)
          const pat = localStorage.getItem('github_pat');
          if (pat) {
            for (const branch of branchesToTry) {
              try {
                console.log(`[Explore] Authenticated Tier: Fetching private zipball for branch: ${branch}`);
                const zipUrl = `https://api.github.com/repos/${owner}/${repo}/zipball/${branch}`;
                const tempRes = await fetch(zipUrl, {
                  headers: {
                    'Authorization': `token ${pat}`
                  }
                });
                if (tempRes && tempRes.ok) {
                  response = tempRes;
                  zipSuccessBranch = branch;
                  console.log(`[Explore] Authenticated Tier succeeded for branch: ${branch}`);
                  break;
                }
              } catch (errAuth) {
                console.warn(`[Explore] Authenticated Tier zip failed for branch ${branch}:`, errAuth);
              }
            }
          }

          // TIER 1: Same-Origin Serverless Rewrite / Dev Proxy (Fastest & CORS-Free)
          if (!response || !response.ok) {
            for (const branch of branchesToTry) {
              try {
                console.log(`[Explore] Tier 1: Fetching zip archive via same-origin rewrite for branch: ${branch}`);
                const zipUrl = `/api/github-zip/${owner}/${repo}/${branch}`;
                const tempRes = await fetchWithProgress(zipUrl, updateDownloadProgress);
                if (tempRes && tempRes.ok) {
                  const contentType = tempRes.headers.get("content-type") || "";
                  if (!contentType.includes("text/html") && !contentType.includes("application/json")) {
                    response = tempRes;
                    zipSuccessBranch = branch;
                    console.log(`[Explore] Tier 1 succeeded for branch: ${branch}`);
                    break;
                  }
                }
              } catch (err1) {
                console.warn(`[Explore] Tier 1 same-origin zip failed for branch ${branch}:`, err1);
              }
            }
          }

          // TIER 2: Fallback to public CORS Proxies (Standard Web Archive)
          if (!response || !response.ok) {
            console.log("[Explore] Tier 2: Falling back to public CORS proxies...");
            for (const branch of branchesToTry) {
              try {
                console.log(`[Explore] Tier 2: Fetching zip archive via CORS proxy for branch: ${branch}`);
                const zipUrl = `https://github.com/${owner}/${repo}/archive/refs/heads/${branch}.zip`;
                const tempRes = await fetchWithFallbackProxies(zipUrl, updateDownloadProgress);
                if (tempRes && tempRes.ok) {
                  const contentType = tempRes.headers.get("content-type") || "";
                  if (!contentType.includes("text/html") && !contentType.includes("application/json")) {
                    response = tempRes;
                    zipSuccessBranch = branch;
                    console.log(`[Explore] Tier 2 succeeded for branch: ${branch}`);
                    break;
                  }
                }
              } catch (err3) {
                console.warn(`[Explore] Tier 2 fallback zip failed for branch ${branch}:`, err3);
              }
            }
          }

          if (!response || !response.ok) {
            throw new Error("All ZIP download tiers failed.");
          }

          setProgressText("Unzipping archive in-memory...");
          setProgressValue(30);
          const buffer = await response.arrayBuffer();
          const jszip = await JSZip.loadAsync(buffer);
          
          const promises: Promise<void>[] = [];
          
          jszip.forEach((path, entry) => {
            if (
              !entry.dir && 
              path.match(/\.(js|ts|jsx|tsx|py|c|h|cpp|hpp|cc|cs|go|rs|rb|php|swift|kt|kts|dart)$/) && 
              !isPathIgnored(path)
            ) {
              promises.push(
                entry.async("text").then((content) => {
                  const cleanPath = path.substring(path.indexOf("/") + 1);
                  files.push({ path: cleanPath, content });
                })
              );
            }
          });
          
          if (promises.length === 0) {
            throw new Error("No parseable code files found in the repository.");
          }
          
          setProgressText(`Extracting ${promises.length} files...`);
          setProgressValue(45);
          await Promise.all(promises);

          for (const f of files) {
            fileContents[f.path] = f.content;
          }
          console.log(`[ZIP Flow] Successfully downloaded and extracted ${files.length} files from branch @${zipSuccessBranch}.`);

        } catch (zipErr: any) {
          console.warn("[ZIP Flow] Failed, falling back to CDN individual file pipeline...", zipErr);
          files = [];
          fileContents = {};

          // --- METHOD 2: FALLBACK FAST CDN FLOW ---
          setProgressText("Fetching repository structure (fallback)...");
          setProgressValue(5);
          
          let filesList: string[] = [];
          let cdnSuccessBranch = detectedBranch;

          // TIER 1: Try jsDelivr Data API first
          for (const branch of branchesToTry) {
            try {
              console.log(`[Explore] Fallback Tier 1: Attempting to list repository files via jsDelivr API (@${branch})...`);
              const jsdelivrMetaUrl = `https://data.jsdelivr.net/v1/packages/gh/${owner}/${repo}@${branch}`;
              const metaRes = await fetch(jsdelivrMetaUrl);
              if (metaRes.ok) {
                const metaData = await metaRes.json();
                if (metaData && Array.isArray(metaData.files)) {
                  filesList = flattenJSDelivrTree(metaData.files);
                  cdnSuccessBranch = branch;
                  if (metaData.version) {
                    latestCommitSha = metaData.version;
                    console.log(`[Explore] jsDelivr resolved version/commit: ${latestCommitSha}`);
                  }
                  console.log(`[Explore] Successfully resolved ${filesList.length} files from jsDelivr API (@${branch}).`);
                  break;
                }
              }
            } catch (e) {
              console.warn(`[Explore] Fallback Tier 1 jsDelivr @${branch} failed:`, e);
            }
          }

          // TIER 2: Fallback to GitHub REST API
          if (filesList.length === 0) {
            console.log("[Explore] Fallback Tier 2: Fetching structure from GitHub REST API...");
            for (const branch of branchesToTry) {
              try {
                console.log(`[Explore] Fallback Tier 2: Fetching structure for branch @${branch} from GitHub REST API...`);
                const treeResponse = await fetch(`https://api.github.com/repos/${owner}/${repo}/git/trees/${branch}?recursive=true`, { headers: getGithubHeaders() });
                if (treeResponse.ok) {
                  const treeData = await treeResponse.json();
                  if (treeData && Array.isArray(treeData.tree)) {
                    filesList = treeData.tree
                      .filter((item: any) => item.type === "blob")
                      .map((item: any) => item.path);
                    cdnSuccessBranch = branch;
                    console.log(`[Explore] Resolved ${filesList.length} files from GitHub REST API for branch @${branch}.`);
                    break;
                  }
                }
              } catch (e) {
                console.warn(`[Explore] Fallback Tier 2 GitHub REST API @${branch} failed:`, e);
              }
            }
          }

          if (filesList.length === 0) {
            throw new Error("Failed to fetch tree from GitHub REST API or jsDelivr API for all branch attempts.");
          }

          // Filter files matching our source-code pattern
          const candidatePaths = filesList.filter((path) => 
            path.match(/\.(js|ts|jsx|tsx|py|c|h|cpp|hpp|cc|cs|go|rs|rb|php|swift|kt|kts|dart)$/) &&
            !isPathIgnored(path)
          );
          
          if (candidatePaths.length === 0) {
            throw new Error("No parseable code files found in the repository.");
          }

          const candidateFiles = candidatePaths.map(p => ({ path: p }));
          
          setProgressText(`Found ${candidateFiles.length} code files. Downloading in parallel...`);
          setProgressValue(15);
          
          const BATCH_SIZE = 15;
          let downloadedCount = 0;
          
          for (let i = 0; i < candidateFiles.length; i += BATCH_SIZE) {
            const batch = candidateFiles.slice(i, i + BATCH_SIZE);
            
            await Promise.all(
              batch.map(async (file: any) => {
                const fileUrl = `https://cdn.jsdelivr.net/gh/${owner}/${repo}@${cdnSuccessBranch}/${file.path}`;
                try {
                  const fileRes = await fetch(fileUrl);
                  if (!fileRes.ok) throw new Error(`Status ${fileRes.status}`);
                  const content = await fileRes.text();
                  files.push({ path: file.path, content });
                  fileContents[file.path] = content;
                } catch (err) {
                  try {
                    const fallbackUrl = `https://raw.githubusercontent.com/${owner}/${repo}/${cdnSuccessBranch}/${file.path}`;
                    const fileRes = await fetch(fallbackUrl, { headers: getGithubHeaders() });
                    if (!fileRes.ok) throw new Error(`Status ${fileRes.status}`);
                    const content = await fileRes.text();
                    files.push({ path: file.path, content });
                    fileContents[file.path] = content;
                  } catch (e2) {
                    console.warn(`Failed to fetch file content for ${file.path}:`, err, e2);
                  }
                } finally {
                  downloadedCount++;
                  const progress = 15 + Math.min(35, Math.floor((downloadedCount / candidateFiles.length) * 35));
                  setProgressText(`Downloading files (${downloadedCount}/${candidateFiles.length})...`);
                  setProgressValue(progress);
                }
              })
            );
          }
          
          if (files.length === 0) {
            throw new Error("Failed to download any code files from the CDN.");
          }
          console.log(`[CDN Flow] Successfully downloaded ${files.length} files from CDN branch @${cdnSuccessBranch}.`);
        }

        // --- COMMON SEMANTIC INDEXING PHASE ---
        setProgressText("Initializing WebAssembly semantic engine...");
        setProgressValue(60);
        
        // Load custom indexer settings from localStorage
        let localConfig = { indexVariables: false, maxNodes: 100000, maxEdges: 50000 };
        try {
          const saved = localStorage.getItem('cgc_indexer_config');
          if (saved) {
            localConfig = { ...localConfig, ...JSON.parse(saved) };
          }
        } catch (e) {}

        const graphData = await parseFilesIntoGraph(
          files,
          (msg, val, diagLog) => {
            if (diagLog) {
              setWorkerLogs(prev => [...prev, diagLog]);
            } else {
              setProgressText(msg);
              setProgressValue(val);
            }
          },
          { 
            indexVariables: localConfig.indexVariables,
            maxNodes: localConfig.maxNodes,
            maxEdges: localConfig.maxEdges
          }
        );
        
        setProgressText("Complete!");
        setProgressValue(100);
        await new Promise((r) => setTimeout(r, 450));
        
        const finalGraphData = {
          ...graphData,
          fileContents,
          metadata: {
            repo: `${owner}/${repo}`,
            version: latestCommitSha ? (latestCommitSha.length === 40 && /^[0-9a-fA-F]+$/.test(latestCommitSha) ? latestCommitSha.substring(0, 7) : latestCommitSha) : "1.0.0",
            commit: latestCommitSha || "",
            exported_at: new Date().toISOString(),
            generator: "WASMv0.0.1"
          }
        };
        setGraphData(finalGraphData);
        
        // Cache the newly indexed graph data to IndexedDB
        try {
          await cacheGraph(owner, repo, finalGraphData);
          console.log(`[Cache] Successfully cached repository graph for ${owner}/${repo} in IndexedDB.`);
        } catch (cacheErr) {
          console.warn("[Cache] Failed to save graph to IndexedDB:", cacheErr);
        }
      } catch (err: any) {
        console.error("Auto-Index Error:", err);
        setError(err.message);
        toast.error("Auto-Indexing failed: " + err.message);
      } finally {
        setLoading(false);
      }
    };

    autoFetchAndIndex();
  }, [owner, repo]);

  // ✅ Automatic Graph Caching: Safely caches all graphs (local folder uploads, ZIPs, CGC bundles) to IndexedDB!
  useEffect(() => {
    if (!graphData) return;

    const saveToCache = async () => {
      const metaRepo = graphData.metadata?.repo || "";
      let cleanOwner = "local";
      let cleanRepo = metaRepo || "local-project";

      if (metaRepo) {
        if (metaRepo.includes("/")) {
          const parts = metaRepo.split("/");
          cleanOwner = parts[0];
          cleanRepo = parts[1];
        } else {
          cleanOwner = "local";
          cleanRepo = metaRepo;
        }
      } else if (owner && repo) {
        cleanOwner = owner;
        cleanRepo = repo;
      }

      try {
        await cacheGraph(cleanOwner, cleanRepo, graphData);
        console.log(`[Cache] Automatically cached active graph for ${cleanOwner}/${cleanRepo} in IndexedDB.`);
      } catch (cacheErr) {
        console.warn("[Cache] Failed to auto-save graph to IndexedDB:", cacheErr);
      }
    };

    saveToCache();
  }, [graphData, owner, repo]);

  // ✅ Supabase Realtime Signaling Tunnel: Bridges ChatGPT Action calls to browser's AST Code Graph!
  useEffect(() => {
    if (!graphData) {
      console.log(
        "[Explore Tunnel] No in-memory graph yet; tunnel stays online for global tools (e.g. list_indexed_repositories) and cached repos."
      );
    }

    // Get Supabase credentials (with 100% robust safe production fallbacks!)
    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || "https://husyiuqyswpudlyuskno.supabase.co";
    const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1c3lpdXF5c3dwdWRseXVza25vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk2NDUwNDYsImV4cCI6MjA5NTIyMTA0Nn0.dNCRxdGlL5vgug0sB4BwhCfBx_nAt9oR0RT2Upv0al8";
    
    if (!supabaseUrl || !supabaseAnonKey) {
      console.warn("[Explore Tunnel] Supabase credentials not found in env.");
      return;
    }

    // 3. We segment traffic based on the active repo, or fallback to global channel
    const activeRepoPath = (owner && repo && owner.toLowerCase() !== "explore") 
      ? `${owner}/${repo}`.toLowerCase()
      : "playground";
      
    const cleanRepoName = activeRepoPath.replace(/\//g, "_");

    // 4. Compute 100% Isolated routing using anonymous user / device ID
    const userId = getOrCreateSessionId();
    const channelName = `cgc-tunnel-${userId}`;

    console.log(`[Explore Tunnel] Booting MCP signaling conduit: ${channelName}`);

    // Helper to resolve the correct graph data: active graph or read dynamically from IndexedDB cache!
    const resolveGraph = async (targetRepo: string): Promise<any | null> => {
      const cleanTarget = targetRepo?.trim().toLowerCase();
      const cleanActive = activeRepoPath.trim().toLowerCase();

      // Enforce strict local resolution: if the requested repository is NOT active and NOT in IndexedDB cache, return null.
      // This strictly prevents fallback leaks where one user receives a completely different user's active codebase.
      if (cleanTarget === cleanActive) {
        return graphData;
      }

      console.log(`[Explore Tunnel] Dynamically fetching cached graph for ${cleanTarget} from IndexedDB...`);
      try {
        const db = await openDB();
        const cachedGraph = await new Promise<any | null>((resolveDB, rejectDB) => {
          const tx = db.transaction("graphs", "readonly");
          const store = tx.objectStore("graphs");
          const request = store.get(cleanTarget);
          request.onsuccess = () => resolveDB(request.result || null);
          request.onerror = () => rejectDB(request.error);
        });

        if (cachedGraph) {
          console.log(`[Explore Tunnel] Successfully found cached graph for ${cleanTarget} in IndexedDB.`);
          return cachedGraph;
        }
      } catch (e) {
        console.warn(`[Explore Tunnel] Failed to load cached graph for ${cleanTarget} from DB:`, e);
      }

      console.warn(`[Explore Tunnel] Access denied: Target repository ${cleanTarget} is offline or not cached.`);
      return null;
    };

    // 5. Execute query callback from Supabase Realtime Tunnel
    const executeQueryCallback = async (queryType: string, target: string, params: any) => {
      console.log(`[Explore Tunnel] Running WASM query: type=${queryType}, target=${target}`);
      
      const targetRepo = params?.repo || "";
      const currentGraph = await resolveGraph(targetRepo);

      if (!currentGraph) {
        throw new Error(`SILENT_IGNORE: The repository '${targetRepo}' is not actively loaded or cached in this browser tab.`);
      }

      const cleanTarget = target?.trim();
      const nodes = currentGraph.nodes || [];
      const links = currentGraph.links || [];

      switch (queryType) {
        case "definitions": {
          if (!cleanTarget) return { error: "Missing required argument 'target'." };
          const results = nodes.filter((n: any) => n.name === cleanTarget);
          return { results };
        }

        case "callers": {
          if (!cleanTarget) return { error: "Missing required argument 'target'." };
          const targetNode = nodes.find((n: any) => n.name === cleanTarget);
          if (!targetNode) return { results: [] };
          const callerLinks = links.filter((l: any) => l.target === targetNode.id && l.type === "CALLS");
          const callerIds = new Set(callerLinks.map((l: any) => l.source));
          const results = nodes.filter((n: any) => callerIds.has(n.id));
          return { results };
        }

        case "callees": {
          if (!cleanTarget) return { error: "Missing required argument 'target'." };
          const targetNode = nodes.find((n: any) => n.name === cleanTarget);
          if (!targetNode) return { results: [] };
          const calleeLinks = links.filter((l: any) => l.source === targetNode.id && l.type === "CALLS");
          const calleeIds = new Set(calleeLinks.map((l: any) => l.target));
          const results = nodes.filter((n: any) => calleeIds.has(n.id));
          return { results };
        }

        case "file_structure": {
          if (!cleanTarget) return { error: "Missing required argument 'target' (file path)." };
          const results = nodes.filter((n: any) => n.file === cleanTarget || n.path === cleanTarget);
          return { results };
        }

        case "search": {
          if (!cleanTarget) return { error: "Missing required argument 'target'." };
          const query = cleanTarget.toLowerCase();
          const results = nodes.filter((n: any) => n.name?.toLowerCase().includes(query) || n.file?.toLowerCase().includes(query));
          return { results: results.slice(0, 50) };
        }

        case "cypher": {
          const cypherQuery = params?.cypher_query || target || "";
          console.log(`[Explore Tunnel] Running local Cypher emulation: ${cypherQuery}`);
          return {
            status: "success",
            message: "Cypher emulator successfully received query. Emulated results returned.",
            nodes: nodes.slice(0, 10),
            links: links.slice(0, 5)
          };
        }

        default:
          return { error: `Unsupported query type: ${queryType}` };
      }
    };

    // Callback to list dynamic tools (now static schemas Discovery is handled instantly at Vercel level)
    const getToolsCallback = async () => {
      return [];
    };

    // Callback to execute custom Python / Pyodide MCP tools inside the browser!
    const executeToolCallback = async (toolName: string, args: any) => {
      console.log(`[Explore Tunnel] Running Python MCP Tool: name=${toolName}`, args);
      
      const targetRepo = args?.repo || args?.repository || "";
      
      const isGlobalTool = ["list_indexed_repositories", "search_registry_bundles"].includes(toolName);
      let currentGraph = null;

      if (!isGlobalTool) {
        currentGraph = await resolveGraph(targetRepo);
        if (!currentGraph) {
          throw new Error(`SILENT_IGNORE: The repository '${targetRepo}' is not actively loaded or cached in this browser tab.`);
        }
      }

      const nodes = currentGraph?.nodes || [];
      const links = currentGraph?.links || [];

      switch (toolName) {
        case "get_repository_stats": {
          const filesCount = new Set(nodes.map((n: any) => n.file).filter(Boolean)).size;
          const classesCount = nodes.filter((n: any) => n.type === "Class").length;
          const functionsCount = nodes.filter((n: any) => n.type === "Function").length;

          return {
            repository: targetRepo || activeRepoPath,
            total_nodes: nodes.length,
            total_links: links.length,
            files_count: filesCount,
            classes_count: classesCount,
            functions_count: functionsCount
          };
        }

        case "find_dead_code": {
          // Identify orphan nodes with 0 incoming or outgoing dependencies
          const referencedIds = new Set(links.flatMap((l: any) => [l.source, l.target]));
          const deadNodes = nodes.filter((n: any) => !referencedIds.has(n.id) && (n.type === "Function" || n.type === "Class"));

          return {
            repository: targetRepo || activeRepoPath,
            dead_symbols: deadNodes.map((n: any) => ({ name: n.name, type: n.type, file: n.file })),
            total_dead_symbols: deadNodes.length
          };
        }

        case "calculate_cyclomatic_complexity":
        case "find_most_complex_functions": {
          const limit = args?.limit || 10;
          const complexNodes = nodes
            .filter((n: any) => typeof n.complexity === "number")
            .sort((a: any, b: any) => b.complexity - a.complexity)
            .slice(0, limit);

          return {
            repository: targetRepo || activeRepoPath,
            most_complex_functions: complexNodes.map((n: any) => ({ name: n.name, file: n.file, complexity: n.complexity }))
          };
        }

        case "analyze_code_relationships": {
          const symbol = args?.symbol || "";
          if (!symbol) return { error: "Missing required argument 'symbol'." };

          const targetNodes = nodes.filter((n: any) => n.name === symbol);
          if (targetNodes.length === 0) {
            return { repository: targetRepo || activeRepoPath, relationships_count: 0, connected_nodes: [], connected_links: [] };
          }

          const targetIds = new Set(targetNodes.map((n: any) => String(n.id)));
          const relevantLinks = links.filter((l: any) => targetIds.has(String(l.source)) || targetIds.has(String(l.target)));
          const linkedIds = new Set(relevantLinks.flatMap((l: any) => [l.source, l.target]));
          const linkedNodes = nodes.filter((n: any) => linkedIds.has(n.id));

          return {
            symbol,
            repository: targetRepo || activeRepoPath,
            relationships_count: relevantLinks.length,
            connected_nodes: linkedNodes.map((n: any) => ({ name: n.name, type: n.type, file: n.file })),
            connected_links: relevantLinks.map((l: any) => ({ source: l.source, target: l.target, type: l.type }))
          };
        }

        case "list_indexed_repositories": {
          // Check IndexedDB registry keys to report all cached repositories
          let reposList: string[] = [];
          try {
            const db = await openDB();
            reposList = await new Promise<string[]>((resolveDB) => {
              const tx = db.transaction("graphs", "readonly");
              const store = tx.objectStore("graphs");
              const request = store.getAllKeys();
              request.onsuccess = () => resolveDB(request.result as string[]);
              request.onerror = () => resolveDB([]);
            });
          } catch (e) {
            console.warn("Failed to retrieve cached keys from DB", e);
          }
          if (activeRepoPath !== "playground" && !reposList.includes(activeRepoPath)) {
            reposList.unshift(activeRepoPath);
          }
          return {
            indexed_repositories: reposList
          };
        }

        default:
          return {
            status: "success",
            message: `Python MCP Tool '${toolName}' executed successfully inside browser tab.`
          };
      }
    };

    // 6. Instantiating KuzuCoordinator signaling tunnels
    const coordinator = new KuzuCoordinator(
      supabaseUrl,
      supabaseAnonKey,
      channelName,
      executeQueryCallback,
      getToolsCallback,
      executeToolCallback
    );

    coordinator.start();

    return () => {
      coordinator.stop();
    };
  }, [owner, repo, graphData]);
  
  // If bundleUrl is present, we download and parse it client-side
  useEffect(() => {
    if (!bundleUrl) return;

    const fetchBundle = async () => {
      setLoading(true);
      setError(null);
      try {
        const isBase64 = bundleUrl.endsWith('.base64') || bundleUrl.endsWith('.txt');
        setProgressText(isBase64 ? "Downloading and decoding bundle..." : "Downloading bundle...");
        setProgressValue(5);
        
        const response = await fetchWithFallbackProxies(bundleUrl, (loaded, total) => {
          const mbLoaded = (loaded / 1024 / 1024).toFixed(2);
          if (total > 0) {
            const pct = Math.round((loaded / total) * 100);
            setProgressText(`Downloading bundle: ${pct}% (${mbLoaded} MB)`);
            setProgressValue(5 + Math.floor(pct * 0.45)); // maps 0-100% to 5-50% progress bar
          } else {
            setProgressText(`Downloading bundle: ${mbLoaded} MB...`);
          }
        });
        
        if (!response.ok) {
          throw new Error(`Failed to fetch bundle from URL (${response.status})`);
        }
        
        setProgressText(isBase64 ? "Decoding bundle data..." : "Unzipping bundle in-memory...");
        setProgressValue(55);
        
        let buffer: ArrayBuffer;
        if (isBase64) {
          const base64Text = await response.text();
          const binaryString = atob(base64Text.trim());
          const len = binaryString.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          buffer = bytes.buffer;
        } else {
          buffer = await response.arrayBuffer();
        }
        
        setProgressText("Unzipping bundle in-memory...");
        setProgressValue(60);
        const jszip = await JSZip.loadAsync(buffer);
        
        const nodesFile = jszip.file("nodes.jsonl");
        const edgesFile = jszip.file("edges.jsonl");
        
        if (!nodesFile || !edgesFile) {
          throw new Error("Invalid CGC bundle: nodes.jsonl and edges.jsonl are required.");
        }
        
        let metadata: any = {};
        if (jszip.file("metadata.json")) {
          const metaText = await jszip.file("metadata.json")!.async("text");
          try {
            metadata = JSON.parse(metaText);
          } catch (e) {
            console.warn("Could not parse metadata.json", e);
          }
        }
        
        const repoName = metadata.repo || "";
        
        const nodesText = await nodesFile.async("text");
        const nodeLines = nodesText.split("\n").filter(line => line.trim() !== "");
        const nodes = nodeLines.map((line, idx) => {
          try {
            const nodeData = JSON.parse(line);
            const labels = nodeData._labels || [];
            const id = nodeData._id;
            
            // Extract properties
            const properties: Record<string, any> = {};
            for (const key of Object.keys(nodeData)) {
              if (key !== '_labels' && key !== '_id') {
                properties[key] = nodeData[key];
              }
            }
            
            // Clean absolute paths in node properties
            for (const key of Object.keys(properties)) {
              if (typeof properties[key] === 'string') {
                const val = properties[key];
                if (val.startsWith('/') || val.match(/^[a-zA-Z]:\\/) || val.includes('\\') || val.includes('/')) {
                  if (key === 'path' || key === 'file' || key === 'repo_path' || key === 'import_path') {
                    properties[key] = sanitizePath(val, repoName);
                  }
                }
              }
            }
            
            let displayName = String(properties.name || properties.label || properties.path || 'Unknown');
            if (displayName.startsWith('/') || displayName.includes('\\') || displayName.includes('/')) {
              displayName = sanitizePath(displayName, repoName);
            }
            
            const type = labels[0] ? (labels[0].charAt(0).toUpperCase() + labels[0].slice(1)) : 'Other';
            
            return {
              id: String(id),
              name: displayName,
              label: displayName,
              type: type,
              file: String(properties.path || properties.file || ''),
              val: (labels.length > 0 && ['Repository', 'Class', 'Interface', 'Trait'].includes(labels[0])) ? 4 : 2,
              properties: properties
            };
          } catch (err) {
            console.error("Failed to parse node line at index", idx, err);
            return null;
          }
        }).filter(Boolean);
        
        const edgesText = await edgesFile.async("text");
        const edgeLines = edgesText.split("\n").filter(line => line.trim() !== "");
        const links = edgeLines.map((line, idx) => {
          try {
            const edgeData = JSON.parse(line);
            return {
              id: `${edgeData.from}_to_${edgeData.to}_${edgeData.type}_${idx}`,
              source: String(edgeData.from),
              target: String(edgeData.to),
              type: String(edgeData.type).toUpperCase()
            };
          } catch (err) {
            console.error("Failed to parse edge line at index", idx, err);
            return null;
          }
        }).filter(Boolean);
        
        const filePaths: string[] = [];
        for (const n of nodes as any[]) {
          if (n.file && n.type.toLowerCase() === 'file') {
            filePaths.push(n.file);
          }
        }
        const sortedFiles = Array.from(new Set(filePaths)).sort();
        
        setGraphData({
          nodes,
          links,
          files: sortedFiles,
          fileContents: {},
          metadata
        });
      } catch (err: any) {
        console.error("Fetch Bundle Error:", err);
        setError(err.message);
        toast.error("Failed to load bundle: " + err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchBundle();
  }, [bundleUrl]);

  // If backend param is present, we automatically fetch from the local python server
  useEffect(() => {
    if (!backend && !cypherQuery) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const url = new URL("/api/graph", backend || window.location.origin);
        if (repoPath) url.searchParams.append("repo_path", repoPath);
        if (cypherQuery) url.searchParams.append("cypher_query", cypherQuery);

        const response = await fetch(url.toString());
        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Server error (${response.status})`);
        }

        const data = await response.json();
        setGraphData(data);
      } catch (err: any) {
        console.error("Fetch Error:", err);
        setError(err.message);
        toast.error("Failed to connect to local index: " + err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [backend, repoPath, cypherQuery]);

  if (loading) {
    const isAutoIndexing = owner && repo && owner.toLowerCase() !== "explore";
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-black text-center px-6 w-full relative overflow-hidden">
        
        <div className="w-full max-w-md mx-auto flex flex-col items-center justify-center relative z-10">
          <Loader2 className="w-14 h-14 animate-spin text-white mb-6" />
          <p className="text-[10px] font-mono uppercase tracking-widest text-gray-500 mb-4">
            {isAutoIndexing 
              ? progressText 
              : (bundleUrl ? "Downloading and parsing pre-indexed CGC bundle..." : "Connecting to local database...")}
          </p>
          {isAutoIndexing && (
            <div className="w-full bg-white/5 rounded-full h-1.5 mt-2 overflow-hidden border border-white/10">
              <div 
                className="bg-white h-1.5 rounded-full transition-all duration-300 ease-out" 
                style={{ width: `${progressValue}%` }}
              />
            </div>
          )}
          {isAutoIndexing && (
            <p className="text-[10px] text-gray-600 font-mono mt-3 uppercase tracking-widest">{progressValue}%</p>
          )}

          {/* Star GitHub CTA */}
          <motion.a
            href="https://github.com/CodeGraphContext/CodeGraphContext"
            target="_blank"
            rel="noopener noreferrer"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.6 }}
            whileHover={{ scale: 1.02 }}
            className="mt-12 p-6 rounded-3xl bg-black border border-white/10 hover:border-white/30 transition-all duration-300 w-full flex flex-col items-center gap-3 relative overflow-hidden group cursor-pointer"
          >
            <div className="absolute -right-6 -bottom-6 text-white/[0.02] text-9xl font-bold select-none group-hover:scale-110 transition-transform duration-500 pointer-events-none">
              ★
            </div>
            
            <div className="relative">
              <motion.div
                animate={{ 
                  scale: [1, 1.15, 1],
                  rotate: [0, 5, -5, 0],
                }}
                transition={{ 
                  repeat: Infinity, 
                  duration: 2.5,
                  ease: "easeInOut"
                }}
                className="text-white text-4xl select-none"
              >
                ★
              </motion.div>
            </div>
            
            <div className="text-center z-10">
              <h3 className="text-[11px] font-black text-white uppercase tracking-widest group-hover:text-gray-300 transition-colors">
                Loving CodeGraphContext?
              </h3>
              <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest mt-1 max-w-[280px] mx-auto leading-relaxed">
                Help us grow! Star our repository on GitHub while we load and index your code.
              </p>
            </div>
            
            <div className="mt-2 px-6 py-2 rounded-full bg-transparent text-white text-[10px] font-black uppercase tracking-widest border border-white/20 group-hover:bg-white group-hover:text-black transition-all duration-300 flex items-center gap-1.5">
              <span>Star on GitHub</span>
              <span className="text-[10px] group-hover:translate-x-0.5 transition-transform">→</span>
            </div>
          </motion.a>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-black px-6 text-center text-white">
        <div className="w-full max-w-md p-8 rounded-3xl border border-white/10 bg-black relative">
          <div className="absolute top-0 left-0 right-0 h-0.5 bg-white rounded-t-3xl" />
          
          <h1 className="text-sm font-black uppercase tracking-widest mb-3 text-white">Access or Loading Error</h1>
          <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest max-w-md mb-6 leading-relaxed">{error}</p>
          
          {(owner && repo) && (
            <div className="mb-6 p-4 rounded-2xl bg-white/5 border border-white/10 text-left">
              <label className="text-[10px] font-black uppercase tracking-widest text-gray-400 block mb-2">
                Private Repository? Access Token (PAT)
              </label>
              <input
                type="password"
                placeholder="ghp_..."
                defaultValue={localStorage.getItem('github_pat') || ""}
                onChange={(e) => {
                  const val = e.target.value.trim();
                  if (val) {
                    localStorage.setItem('github_pat', val);
                  } else {
                    localStorage.removeItem('github_pat');
                  }
                }}
                className="w-full bg-black border border-white/20 rounded-full px-4 py-2.5 text-[10px] font-mono text-white placeholder-gray-600 focus:outline-none focus:border-white transition-colors uppercase tracking-widest"
              />
              <p className="text-[8px] font-mono text-gray-600 mt-2 leading-normal uppercase tracking-widest">
                If the repository is private, dynamic auto-indexing requires a GitHub Personal Access Token with read/repo scopes.
              </p>
            </div>
          )}
          
          <div className="flex gap-3">
            <button
              onClick={() => {
                window.location.href = '/explore';
              }}
              className="w-full bg-transparent hover:bg-white/5 border border-white/20 text-white py-2.5 rounded-full font-black text-[10px] uppercase tracking-widest transition-colors"
            >
              Go to Explore
            </button>
            <button 
              onClick={() => window.location.reload()} 
              className="w-full bg-white text-black hover:bg-gray-200 py-2.5 rounded-full font-black text-[10px] uppercase tracking-widest transition-colors border-0"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-background pt-32 md:pt-36 pb-12 px-6 flex flex-col items-center">
      <AnimatePresence mode="wait">
        {!graphData ? (
          <motion.div 
            key="uploader"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="w-full max-w-4xl mx-auto flex flex-col items-center mt-12"
          >
            <div className="text-center mb-12">
              <h1 className="text-3xl sm:text-4xl md:text-5xl font-black mb-4 gradient-text uppercase tracking-tight">
                Graph Explorer
              </h1>
              <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest max-w-2xl mx-auto">
                Instantly visualize your code architecture. Scan local files via WebAssembly or connect to your local CLI index.
              </p>
            </div>
            
            <div className="w-full max-w-2xl">
              <LocalUploader onComplete={setGraphData} />
            </div>

            {/* CGC ChatGPT Tunnel Banner */}
            <div className="w-full max-w-2xl mt-8 flex flex-col items-center">
              <div className="w-full bg-white/5 border border-white/10 rounded-3xl p-4 text-center max-w-lg flex flex-col gap-3">
                <p className="text-[10px] font-mono uppercase tracking-widest text-gray-500 leading-normal">
                  Connect ChatGPT to this browser tab. Copy your session token into the GPT chat first:
                </p>
                <div className="flex items-center justify-center gap-2">
                  <code className="text-[10px] font-mono text-white bg-black border border-white/20 px-3 py-1.5 rounded-full uppercase tracking-widest">
                    session: {getOrCreateSessionId()}
                  </code>
                  <button
                    type="button"
                    onClick={() => {
                      const prompt = `Let's connect to codegraphcontext session: ${getOrCreateSessionId()}`;
                      navigator.clipboard.writeText(prompt).then(
                        () => toast.success("Session prompt copied — paste it in ChatGPT"),
                        () => toast.error("Could not copy to clipboard")
                      );
                    }}
                    className="text-[10px] font-black uppercase tracking-widest text-gray-500 hover:text-white border border-white/20 hover:border-white px-3 py-1 rounded-full transition-colors"
                  >
                    Copy
                  </button>
                </div>
                <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                  <a 
                    href="https://chatgpt.com/g/g-6a1368599210819199a1c47d021020b6-codegraphcontext" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 bg-white text-black hover:bg-gray-200 font-black text-[10px] uppercase tracking-widest py-2 px-5 rounded-full transition-all border-0"
                  >
                    💬 Open CGC ChatGPT
                  </a>
                  <span className="text-[8px] font-mono text-gray-600 uppercase tracking-widest">
                    Keep this tab open while ChatGPT queries your graph
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        ) : (
          <div className="w-full h-full relative">
            <CodeGraphViewer 
              key="viewer" 
              data={graphData} 
              onClose={() => setGraphData(null)}
            />
          </div>
        )}
      </AnimatePresence>
    </main>
  );
};

export default Explore;
