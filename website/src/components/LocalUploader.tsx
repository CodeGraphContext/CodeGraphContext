import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { FolderUp, FileArchive, Github, Loader2, Settings, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { parseFilesIntoGraph } from "@/lib/parser";

import JSZip from "jszip";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";

const IGNORED_DIRS = new Set([
  'node_modules', '.git', '.github', 'dist', 'build', 'out', 'coverage',
  '.next', '.nuxt', '__pycache__', 'venv', '.venv', 'env', '.env', '.tox',
  'eggs', 'target', '.gradle', '.idea', 'cmake-build-debug', 'bin', 'obj',
  'packages', 'vendor', 'Pods', '.build', 'DerivedData', '.dart_tool',
  '.vscode'
]);

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

  // Keep original path if not matched
  return p;
};

const isPathIgnored = (path: string, skipTests = true) => {
  const parts = path.split(/[\/\\]/);
  return parts.some(part => {
    if (IGNORED_DIRS.has(part)) return true;
    if (skipTests && ['test', 'tests', '__tests__', 'spec', 'specs'].includes(part.toLowerCase())) return true;
    return false;
  });
};

const fetchWithFallbackProxies = async (url: string): Promise<Response> => {
  if (!url) throw new Error("URL is empty");

  try {
    const res = await fetch(url);
    if (res.ok) return res;
  } catch (e) {
    console.warn("Direct fetch failed, falling back to CORS proxies...", e);
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

        return new Response(bytes.buffer, {
          status: 200,
          headers: { 'Content-Type': 'application/octet-stream' }
        });
      } else {
        const res = await fetch(proxiedUrl);
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

export default function LocalUploader({ onComplete, plain }: { onComplete: (data: unknown) => void, plain?: boolean }) {
  const navigate = useNavigate();
  const [isParsing, setIsParsing] = useState(false);
  const [progress, setProgress] = useState({ text: "", value: 0 });
  const [activeTab, setActiveTab] = useState<'folder' | 'zip' | 'cgc' | 'github'>('github');
  const [githubUrl, setGithubUrl] = useState("");
  const [githubPat, setGithubPat] = useState(() => localStorage.getItem('github_pat') || "");

  const [config, setConfig] = useState(() => {
    try {
      const saved = localStorage.getItem('cgc_indexer_config');
      if (saved) {
        return {
          indexVariables: false,
          skipTests: true,
          maxNodes: 100000,
          maxEdges: 50000,
          ...JSON.parse(saved)
        };
      }
    } catch (e) { }
    return {
      indexVariables: false,
      skipTests: true,
      maxNodes: 100000,
      maxEdges: 50000,
    };
  });

  const [isConfigOpen, setIsConfigOpen] = useState(false);

  useEffect(() => {
    if (!isConfigOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsConfigOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isConfigOpen]);

  const updateConfig = (newConfig: Partial<typeof config>) => {
    const updated = { ...config, ...newConfig };
    setConfig(updated);
    localStorage.setItem('cgc_indexer_config', JSON.stringify(updated));
  };

  const isDirIgnored = (name: string) => {
    if (IGNORED_DIRS.has(name)) return true;
    if (config.skipTests && ['test', 'tests', '__tests__', 'spec', 'specs'].includes(name.toLowerCase())) return true;
    return false;
  };

  const processFiles = async (files: { path: string, content: string }[], repoName: string = "local-project") => {
    // Build fileContents map before the worker clears content for memory
    const fileContents: Record<string, string> = {};
    for (const f of files) {
      fileContents[f.path] = f.content;
    }

    setProgress({ text: `Parsing AST for ${files.length} files...`, value: 50 });
    await new Promise(r => setTimeout(r, 800));

    setProgress({ text: "Initializing WebAssembly tree-sitter...", value: 80 });
    const graphData = await parseFilesIntoGraph(
      files,
      (msg, val) => setProgress({ text: msg, value: val }),
      {
        indexVariables: config.indexVariables,
        maxNodes: config.maxNodes,
        maxEdges: config.maxEdges
      }
    );

    setProgress({ text: "Complete!", value: 100 });
    await new Promise(r => setTimeout(r, 400));

    onComplete({
      ...graphData,
      fileContents,
      metadata: {
        repo: repoName,
        version: "1.0.0",
        timestamp: new Date().toISOString()
      }
    });
  };

  const handleFolderSelect = async () => {
    try {
      if (!("showDirectoryPicker" in window)) {
        alert("Your browser does not support the File System Access API.");
        return;
      }
      const dirHandle = await (window as unknown as { showDirectoryPicker: () => Promise<any> }).showDirectoryPicker();
      setIsParsing(true);
      setProgress({ text: "Reading local directory...", value: 10 });

      const files: any[] = [];
      async function readDir(handle: any, prefix = "") {
        for await (const entry of handle.values()) {
          if (entry.kind === 'file' && entry.name.match(/\.(js|ts|jsx|tsx|py|c|h|cpp|hpp|cc|cs|go|rs|rb|php|swift|kt|kts|dart)$/)) {
            const file = await entry.getFile();
            files.push({ path: `${prefix}/${entry.name}`, content: await file.text() });
          } else if (entry.kind === 'directory' && !isDirIgnored(entry.name)) {
            await readDir(entry, `${prefix}/${entry.name}`);
          }
        }
      }

      await readDir(dirHandle);
      await processFiles(files, dirHandle.name);
    } catch (err) {
      console.error(err);
      setIsParsing(false);
    }
  };

  const handleZipUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsParsing(true);
    try {
      setProgress({ text: "Unzipping locally...", value: 10 });
      const buffer = await file.arrayBuffer();
      const jszip = await JSZip.loadAsync(buffer);

      const files: any[] = [];
      const promises: Promise<void>[] = [];

      jszip.forEach((path, entry) => {
        if (!entry.dir && path.match(/\.(js|ts|jsx|tsx|py|c|h|cpp|hpp|cc|cs|go|rs|rb|php|swift|kt|kts|dart)$/) && !isPathIgnored(path, config.skipTests)) {
          promises.push(entry.async("text").then(content => { files.push({ path, content }); }));
        }
      });

      setProgress({ text: `Extracting ${promises.length} files...`, value: 30 });
      await Promise.all(promises);

      await processFiles(files, file.name.replace(/\.zip$/i, ""));
    } catch (err) {
      console.error(err);
      setIsParsing(false);
    }
  };

  const handleCgcUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsParsing(true);
    try {
      setProgress({ text: "Unzipping CGC bundle...", value: 10 });
      const buffer = await file.arrayBuffer();
      const jszip = await JSZip.loadAsync(buffer);

      const nodesFile = jszip.file("nodes.jsonl");
      const edgesFile = jszip.file("edges.jsonl");

      if (!nodesFile || !edgesFile) {
        alert("Invalid CGC bundle: nodes.jsonl and edges.jsonl are required.");
        setIsParsing(false);
        return;
      }

      setProgress({ text: "Parsing CGC bundle...", value: 30 });

      let metadata: any = {};
      if (jszip.file("metadata.json")) {
        const metaText = await jszip.file("metadata.json")!.async("text");
        try {
          metadata = JSON.parse(metaText);
        } catch (e) {
          console.warn("Could not parse metadata.json", e);
        }
      }

      const repoName = metadata.repo || "Unknown Repository";
      setProgress({ text: `Extracting nodes for ${repoName}...`, value: 50 });

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
          
          let displayName = String(properties.name || properties.label || properties.uid || properties.node_type || properties.path || 'Unknown');
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

      setProgress({ text: "Extracting edges...", value: 70 });

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

      setProgress({ text: "Building tree index...", value: 90 });

      const filePaths: string[] = [];
      for (const n of nodes as any[]) {
        if (n.file && n.type.toLowerCase() === 'file') {
          filePaths.push(n.file);
        }
      }
      const sortedFiles = Array.from(new Set(filePaths)).sort();

      setProgress({ text: "Complete!", value: 100 });
      await new Promise(r => setTimeout(r, 400));

      onComplete({
        nodes,
        links,
        files: sortedFiles,
        fileContents: {},
        metadata
      });
    } catch (err) {
      console.error(err);
      setIsParsing(false);
    }
  };

  const handleGithubFetch = async () => {
    const input = githubUrl.trim();
    if (!input) {
      alert("Please enter a GitHub URL or owner/repo.");
      return;
    }

    let owner = "";
    let repo = "";

    if (input.includes("github.com")) {
      const match = input.match(/github\.com\/([^/]+)\/([^/]+)/);
      if (match) {
        owner = match[1];
        repo = match[2].replace(/\.git$/, "").split("/")[0];
      }
    } else {
      const match = input.match(/^([^/]+)\/([^/]+)$/);
      if (match) {
        owner = match[1];
        repo = match[2];
      }
    }

    if (!owner || !repo) {
      alert("Please enter a valid GitHub repository (e.g. sktime/sktime-mcp or https://github.com/sktime/sktime-mcp).");
      return;
    }

    // Redirect user to the optimized Direct Repo route
    navigate(`/${owner}/${repo}`);
  };

  return (
    <div className={plain ? "flex flex-col w-full h-full relative z-10" : "flex flex-col p-6 w-full h-full min-h-[400px] border border-white/10 dark:border-white/20 rounded-[2rem] bg-black/40 backdrop-blur-xl shadow-2xl relative overflow-hidden"}>

      {/* Tab Selectors */}
      <div className="grid grid-cols-2 sm:flex bg-black/5 dark:bg-white/5 p-1.5 rounded-2xl mb-6 relative z-10 w-full shadow-inner border border-gray-200 dark:border-white/5 gap-1.5 sm:gap-2">
        <button onClick={() => setActiveTab('folder')} className={`w-full sm:flex-1 py-2.5 px-3 text-xs sm:text-sm font-semibold rounded-xl transition-all duration-300 ${activeTab === 'folder' ? 'bg-purple-600 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)]' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-purple-500/10 dark:hover:bg-purple-500/20'}`}>Folder</button>
        <button onClick={() => setActiveTab('zip')} className={`w-full sm:flex-1 py-2.5 px-3 text-xs sm:text-sm font-semibold rounded-xl transition-all duration-300 ${activeTab === 'zip' ? 'bg-purple-600 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)]' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-purple-500/10 dark:hover:bg-purple-500/20'}`}>ZIP</button>
        <button onClick={() => setActiveTab('cgc')} className={`w-full sm:flex-1 py-2.5 px-3 text-xs sm:text-sm font-semibold rounded-xl transition-all duration-300 ${activeTab === 'cgc' ? 'bg-purple-600 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)]' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-purple-500/10 dark:hover:bg-purple-500/20'}`}>CGC Bundle</button>
        <button onClick={() => setActiveTab('github')} className={`w-full sm:flex-1 py-2.5 px-3 text-xs sm:text-sm font-semibold rounded-xl transition-all duration-300 ${activeTab === 'github' ? 'bg-purple-600 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)]' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-purple-500/10 dark:hover:bg-purple-500/20'}`}>GitHub</button>
      </div>



      {!isParsing ? (
        <div className="flex flex-col items-center justify-center flex-1 text-center w-full relative z-10">

          {activeTab === 'folder' && (
            <motion.div key="folder" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center w-full">

              <h3 className="text-2xl font-bold mb-2 text-gray-900 dark:text-white">Select Directory</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm mb-8 max-w-[250px]">Select a local folder. Visualized locally in the browser.</p>
              <Button onClick={handleFolderSelect} className="bg-purple-600 text-white hover:bg-purple-500 shadow-[0_0_15px_rgba(168,85,247,0.4)] rounded-full px-10 py-6 text-lg w-full max-w-[280px] shadow-[0_0_20px_rgba(255,255,255,0.1)]">
                Browse Files
              </Button>
            </motion.div>
          )}

          {activeTab === 'zip' && (
            <motion.div key="zip" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center w-full">

              <h3 className="text-2xl font-bold mb-2 text-gray-900 dark:text-white">Upload ZIP</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm mb-8 max-w-[250px]">Drop a compressed repository. Unzipped and parsed securely in memory.</p>
              <div className="relative w-full max-w-[280px]">
                <Button className="bg-purple-600 text-white relative cursor-pointer hover:bg-gray-200 rounded-full px-10 py-6 text-lg w-full shadow-[0_0_20px_rgba(255,255,255,0.1)]">
                  Select ZIP Archive
                  <input type="file" accept=".zip" onChange={handleZipUpload} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
                </Button>
              </div>
            </motion.div>
          )}

          {activeTab === 'cgc' && (
            <motion.div key="cgc" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center w-full">

              <h3 className="text-2xl font-bold mb-2 text-gray-900 dark:text-white">Upload CGC Bundle</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm mb-8 max-w-[250px]">Drop a .cgc pre-indexed bundle file. Loaded instantly in-memory.</p>
              <div className="relative w-full max-w-[280px]">
                <Button className="bg-purple-600 text-white relative cursor-pointer hover:bg-gray-200 rounded-full px-10 py-6 text-lg w-full shadow-[0_0_20px_rgba(255,255,255,0.1)]">
                  Select CGC Bundle
                  <input type="file" accept=".cgc" onChange={handleCgcUpload} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
                </Button>
              </div>
            </motion.div>
          )}

          {activeTab === 'github' && (
            <motion.div key="github" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center w-full">

              <h3 className="text-2xl font-bold mb-2 text-gray-900 dark:text-white">Fetch Repository</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm mb-6 max-w-[250px]">Pull raw files from a GitHub repository.</p>

              <div className="w-full space-y-3 mb-4">
                <input
                  type="text"
                  placeholder="https://github.com/facebook/react"
                  value={githubUrl}
                  onChange={e => setGithubUrl(e.target.value)}
                  className="w-full bg-white/40 dark:bg-black/40 border border-gray-300 dark:border-white/20 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 px-5 py-3.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all text-sm"
                />

                <input
                  type="password"
                  placeholder="Personal Access Token (PAT) - Required for Private Repos"
                  value={githubPat}
                  onChange={e => {
                    const val = e.target.value;
                    setGithubPat(val);
                    if (val.trim()) {
                      localStorage.setItem('github_pat', val.trim());
                    } else {
                      localStorage.removeItem('github_pat');
                    }
                  }}
                  className="w-full bg-white/40 dark:bg-black/40 border border-gray-300 dark:border-white/20 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 px-5 py-3.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all text-sm"
                />
              </div>

              <Button onClick={handleGithubFetch} className="bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] w-full rounded-xl py-6 text-lg font-semibold shadow-[0_0_20px_rgba(255,255,255,0.1)]">
                Scan & Visualize
              </Button>
            </motion.div>
          )}

          {/* Configure Indexer Link */}
          <button
            type="button"
            onClick={() => setIsConfigOpen(true)}
            className="mt-8 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-gray-400 hover:text-white transition-all cursor-pointer group"
          >
            <Settings className="w-3.5 h-3.5 group-hover:rotate-45 transition-transform duration-300 text-purple-400" />
            <span>Configure Indexer Settings ⚙️</span>
          </button>

        </div>
      ) : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center flex-1 w-full px-4 relative z-10">
          <Loader2 className="w-14 h-14 text-white animate-spin mb-6 drop-shadow-[0_0_15px_rgba(255,255,255,0.5)]" />
          <h3 className="text-lg font-medium text-white mb-4 text-center">{progress.text}</h3>

          <div className="w-full bg-gray-800 rounded-full h-2 mt-2 overflow-hidden shadow-inner border border-white/5">
            <div
              className="bg-white h-2 rounded-full transition-all duration-300 ease-out relative"
              style={{ width: `${progress.value}%` }}
            >
              <div className="absolute inset-0 bg-white/30 truncate" style={{ animation: "shimmer 2s infinite linear" }}></div>
            </div>
          </div>
          <p className="text-xs text-gray-400 font-mono mt-3">{progress.value}%</p>
        </motion.div>
      )}

      {/* Decorative Blob */}
      {!plain && <div className="absolute -bottom-32 -right-32 w-80 h-80 bg-purple-600/15 blur-3xl rounded-full z-0 pointer-events-none"></div>}

      {/* Configuration Modal */}
      {createPortal(
        <AnimatePresence>
          {isConfigOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4"
              onClick={() => setIsConfigOpen(false)}
            >
              <motion.div
                initial={{ scale: 0.95, y: 15 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.95, y: 15 }}
                transition={{ type: "spring", duration: 0.4 }}
                className="bg-zinc-950/95 border border-white/10 dark:border-white/20 p-6 rounded-[2rem] max-w-md w-full shadow-[0_0_50px_rgba(0,0,0,0.8)] relative overflow-hidden text-left"
                onClick={e => e.stopPropagation()}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/10">
                  <div className="flex items-center gap-2">
                    <Settings className="w-5 h-5 text-purple-400 animate-pulse" />
                    <h3 className="text-lg font-bold text-white tracking-wide">Indexer Configuration</h3>
                  </div>
                  <button
                    onClick={() => setIsConfigOpen(false)}
                    className="p-1.5 rounded-full bg-white/5 text-gray-400 hover:text-white hover:bg-purple-500/20 transition-all cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Body */}
                <div className="space-y-6">

                  {/* 1. Index High-Fidelity Variables */}
                  <div className="flex items-start gap-3 justify-between">
                    <div className="flex-1">
                      <label className="text-sm font-semibold text-white block mb-0.5">
                        Index High-Fidelity Variables
                      </label>
                      <span className="text-[11px] text-gray-400 leading-normal block">
                        Enables extraction of local variable assignments. Increases graph density but requires higher compute.
                      </span>
                    </div>
                    <div
                      onClick={() => updateConfig({ indexVariables: !config.indexVariables })}
                      className={`w-11 h-6 rounded-full p-1 cursor-pointer transition-all flex items-center shrink-0 ${config.indexVariables ? 'bg-white justify-end' : 'bg-zinc-800 justify-start'}`}
                    >
                      <motion.div layout className={`w-4 h-4 rounded-full shadow-md ${config.indexVariables ? 'bg-black' : 'bg-white'}`} />
                    </div>
                  </div>

                  {/* 2. Skip Tests & Configuration folders */}
                  <div className="flex items-start gap-3 justify-between">
                    <div className="flex-1">
                      <label className="text-sm font-semibold text-white block mb-0.5">
                        Exclude Spec & Test Suites
                      </label>
                      <span className="text-[11px] text-gray-400 leading-normal block">
                        Completely skip parsing test suites, mocks, configurations, specs, and complex directories (e.g. <code>tests/</code>, <code>.github/</code>).
                      </span>
                    </div>
                    <div
                      onClick={() => updateConfig({ skipTests: !config.skipTests })}
                      className={`w-11 h-6 rounded-full p-1 cursor-pointer transition-all flex items-center shrink-0 ${config.skipTests ? 'bg-white justify-end' : 'bg-zinc-800 justify-start'}`}
                    >
                      <motion.div layout className={`w-4 h-4 rounded-full shadow-md ${config.skipTests ? 'bg-black' : 'bg-white'}`} />
                    </div>
                  </div>

                  {/* 3. Max Graph Nodes */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-sm font-semibold text-white">
                        Maximum Graph Nodes
                      </label>
                      <span className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-md">
                        {config.maxNodes.toLocaleString()}
                      </span>
                    </div>
                    <span className="text-[11px] text-gray-400 leading-normal block mb-2">
                      The maximum number of AST elements (files, classes, functions, variables) to create in the graph.
                    </span>
                    <input
                      type="range"
                      min={10000}
                      max={500000}
                      step={10000}
                      value={config.maxNodes}
                      onChange={e => updateConfig({ maxNodes: parseInt(e.target.value) })}
                      className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
                    />
                  </div>

                  {/* 4. Max Graph Edges */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-sm font-semibold text-white">
                        Maximum Call / Import Edges
                      </label>
                      <span className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-md">
                        {config.maxEdges.toLocaleString()}
                      </span>
                    </div>
                    <span className="text-[11px] text-gray-400 leading-normal block mb-2">
                      Limits relationship lines to safeguard browser rendering performance. High edge density can slow down rendering.
                    </span>
                    <input
                      type="range"
                      min={5000}
                      max={200000}
                      step={5000}
                      value={config.maxEdges}
                      onChange={e => updateConfig({ maxEdges: parseInt(e.target.value) })}
                      className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
                    />
                  </div>

                </div>

                {/* Footer */}
                <div className="mt-8 flex gap-3">
                  <Button
                    onClick={() => {
                      updateConfig({
                        indexVariables: false,
                        skipTests: true,
                        maxNodes: 100000,
                        maxEdges: 50000
                      });
                    }}
                    variant="outline"
                    className="flex-1 bg-transparent hover:bg-purple-500/10 text-gray-300 hover:text-white border-white/10 rounded-xl py-5 cursor-pointer"
                  >
                    Reset Defaults
                  </Button>
                  <Button
                    onClick={() => setIsConfigOpen(false)}
                    className="flex-1 bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] rounded-xl py-5 shadow-lg cursor-pointer"
                  >
                    Apply Settings
                  </Button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}
