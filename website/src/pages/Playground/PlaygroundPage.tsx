import React, { useState, useRef, useMemo, useEffect, useCallback } from 'react';
import { useSearchParams, Link as RouterLink } from 'react-router-dom';
import JSZip from 'jszip';
import './playground.css';
import { processFiles } from './core/astWorker';
import type { FileData, GraphData } from './core/astWorker';
import { fetchRemoteRepo } from './core/remoteRepo';
import { GraphCanvas, EDGE_STYLES } from './components/GraphCanvas';
import { UploadCloud, Box, Search, Settings, HelpCircle, Heart, X, FileCode2, FileText, Link, Lock, Globe, Filter, ChevronRight, ChevronDown, Lightbulb, Share2, Menu, Pipette, Download, Twitter, MessageSquare, ExternalLink } from 'lucide-react';

// Node colour map for search results (mirrors GitNexus Header.tsx)
const NODE_TYPE_COLORS: Record<string, string> = {
  file:       '#3b82f6',
  folder:     '#6366f1',
  class:      '#f59e0b',
  interface:  '#ec4899',
  function:   '#10b981',
  method:     '#14b8a6',
  struct:     '#f97316',
  enum:       '#a78bfa',
  module:     '#22d3ee',
  namespace:  '#7c3aed',
  default:    '#6b7280',
};

function App() {
  const [loading, setLoading] = useState(false);
  const [progressMsg, setProgressMsg] = useState('');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [illustratedPath, setIllustratedPath] = useState<string | null>(null);
  const [selectedNodeLabel, setSelectedNodeLabel] = useState<string | null>(null);
  const [isRemoteMode, setIsRemoteMode] = useState(true);
  const [repoUrl, setRepoUrl] = useState('');
  const [repoToken, setRepoToken] = useState('');
  const [explorerWidth, setExplorerWidth] = useState(260);
  const [isExplorerCollapsed, setIsExplorerCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [collapsedPaths, setCollapsedPaths] = useState<Set<string>>(new Set());
  const [customNodeColors, setCustomNodeColors] = useState<Record<string, string>>({});
  const [customEdgeColors, setCustomEdgeColors] = useState<Record<string, string>>({});
  const [isHintModalOpen, setIsHintModalOpen] = useState(false);


  const fileInputRef = useRef<HTMLInputElement>(null);
  const searchRef    = useRef<HTMLDivElement>(null);
  const inputRef     = useRef<HTMLInputElement>(null);
  const codePanelRef = useRef<HTMLDivElement>(null);
  const graphCanvasRef = useRef<any>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const actionProcessedRef = useRef(false);
  const [isExportDropdownOpen, setIsExportDropdownOpen] = useState(false);
 
  const performRemoteFetch = useCallback(async (url: string, token?: string) => {
    if (!url.trim()) return;
    
    setLoading(true);
    setProgressMsg('Connecting to repository...');
    
    try {
      const fileEntries = await fetchRemoteRepo({ url, token }, msg => setProgressMsg(msg));
      if (fileEntries.length === 0) {
        alert('No source files found in the repository.');
        setLoading(false);
        return;
      }
      const result = await processFiles(fileEntries, msg => setProgressMsg(msg));
      setGraphData(result);
      setSelectedFile(null);
      setSelectedNodeLabel(null);
    } catch (err: any) {
      console.error('Remote fetch failed:', err);
      alert(err.message || 'Failed to fetch repository.');
    } finally {
      setLoading(false);
    }
  }, [repoUrl, repoToken]);

  // Handle URL params on mount
  useEffect(() => {
    if (actionProcessedRef.current) return;

    const repo = searchParams.get('repo');
    const token = searchParams.get('token');
    const action = searchParams.get('action');

    if (repo) {
       actionProcessedRef.current = true;
       setRepoUrl(repo);
       if (token) setRepoToken(token);
       setIsRemoteMode(true);
       performRemoteFetch(repo, token || undefined);
       // Clear URL
       setSearchParams({}, { replace: true });
    } else if (action === 'select-local') {
       actionProcessedRef.current = true;
       // Clear URL first
       setSearchParams({}, { replace: true });
       // Pull open the picker
       setTimeout(() => {
          fileInputRef.current?.click();
       }, 300);
    }
  }, [searchParams, performRemoteFetch, setSearchParams]);

  // Resize handler
  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const stopResizing = useCallback(() => {
    setIsResizing(false);
  }, []);

  const resize = useCallback((e: MouseEvent) => {
    if (isResizing) {
       const newWidth = e.clientX;
       if (newWidth > 150 && newWidth < 600) {
         setExplorerWidth(newWidth);
       }
    }
  }, [isResizing]);

  useEffect(() => {
    window.addEventListener('mousemove', resize);
    window.addEventListener('mouseup', stopResizing);
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [resize, stopResizing]);

  // Visibility filters
  const [visibleNodeTypes, setVisibleNodeTypes] = useState<Set<string>>(new Set(['file', 'folder', 'class', 'function', 'interface', 'method', 'struct', 'enum', 'namespace', 'module']));
  const [visibleEdgeTypes, setVisibleEdgeTypes] = useState<Set<string>>(new Set(['contains', 'defines', 'imports', 'calls', 'inherits', 'implements']));
  const [isFiltersCollapsed, setIsFiltersCollapsed] = useState(false);

  // Scroll to selected node in code panel
  useEffect(() => {
    if (selectedFile && selectedNodeLabel && codePanelRef.current) {
      // Find the text in the code and scroll to it
      // Simple implementation: search for the label in the code string, calculate line number
      const content = graphData?.files[selectedFile];
      if (content) {
         const lines = content.split('\n');
         const lineIdx = lines.findIndex(l => l.includes(selectedNodeLabel));
         if (lineIdx !== -1) {
            const lineEl = codePanelRef.current.querySelector(`[data-line="${lineIdx}"]`);
            if (lineEl) {
               lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
               // Add a brief highlight effect
               lineEl.classList.add('bg-accent/20');
               setTimeout(() => lineEl.classList.remove('bg-accent/20'), 2000);
            }
         }
      }
    }
  }, [selectedFile, selectedNodeLabel, graphData]);

  /* ── search results across graph nodes ─────────────────────────────── */
  const searchResults = useMemo(() => {
    if (!graphData || !searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    return graphData.nodes
      .filter(n => n.label.toLowerCase().includes(q))
      .slice(0, 10);
  }, [graphData, searchQuery]);

  /* ── file ingestion ─────────────────────────────────────────────────── */
  const processFilesList = async (files: FileList | File[] | DataTransferItemList, onProgress?: (msg: string) => void) => {
    if (!files || files.length === 0) return;
    setLoading(true);
    setProgressMsg('Reading files...');
    const fileEntries: FileData[] = [];
    const textExts = new Set(['.js', '.jsx', '.ts', '.tsx', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.go', '.rs', '.rb', '.php', '.cs', '.swift', '.kt', '.sh', '.bash', '.sql', '.html', '.css', '.scss', '.json', '.xml', '.yaml', '.yml', '.md', '.txt', '.env', '.toml', '.proto', '.graphql', '.svelte', '.vue', '.astro', '.properties', '.gradle', '.lock']);

    for (let i = 0; i < files.length; i++) {
      const item = files[i];
      let file: File | null = null;
      if ('getAsFile' in item) file = (item as DataTransferItem).getAsFile();
      else file = item as File;
      if (!file) continue;

      // Handle ZIP files
      if (file.name.endsWith('.zip')) {
        onProgress?.('Extracting ZIP...');
        const zip = await JSZip.loadAsync(file);
        for (const [relPath, zipFile] of Object.entries(zip.files)) {
          if (zipFile.dir) continue;
          
          const segments = relPath.split('/');
          const isIgnored = segments.some(s => 
            ['node_modules', '.git', 'dist', 'target', 'build', 'out', '.next', '.cache', 'vendor'].includes(s)
          );
          if (isIgnored) continue;
          
          const ext = relPath.substring(relPath.lastIndexOf('.')).toLowerCase();
          const isText = textExts.has(ext) || !relPath.includes('.'); 
          if (!isText) continue; 
          
          fileEntries.push({ path: relPath, content: await zipFile.async('string') });
        }
        continue;
      }

      const path = file.webkitRelativePath || file.name;
      const segments = path.split('/');
      const isIgnored = segments.some(s => 
        ['node_modules', '.git', 'dist', 'target', 'build', 'out', '.next', '.cache', 'vendor'].includes(s)
      );
      if (isIgnored) continue;
      
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      const isText = textExts.has(ext) || !file.name.includes('.');
      if (!isText) continue;

      try { fileEntries.push({ path, content: await file.text() }); }
      catch (err) { console.error(`Failed to read ${file.name}`, err); }
    }

    if (fileEntries.length === 0) {
      setLoading(false);
      alert('No source files found. Make sure you select a directory.');
      return;
    }
    try {
      const result = await processFiles(fileEntries, msg => setProgressMsg(msg));
      setGraphData(result);
    } catch (err) {
      console.error('Parsing failed:', err);
      alert('Failed during AST parsing. See console.');
    } finally { setLoading(false); }
  };

  const handleRemoteFetch = async (e: React.FormEvent) => {
    e.preventDefault();
    await performRemoteFetch(repoUrl, repoToken);
  };

  const handleDirectorySelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      await processFilesList(e.target.files, (msg) => setProgressMsg(msg));
      setSelectedFile(null);
      setSelectedNodeLabel(null);
      // 🔥 Reset value so the SAME folder can be picked again if needed
      e.target.value = '';
    }
  };
  const handleDragOver  = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop      = async (e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    if (e.dataTransfer.items) {
      await processFilesList(e.dataTransfer.items as any, (msg) => setProgressMsg(msg));
    } else {
      await processFilesList(e.dataTransfer.files as any);
    }
    setSelectedFile(null);
    setSelectedNodeLabel(null);
  };


  return (
    <div className="flex flex-col h-screen overflow-hidden bg-void text-text-primary font-sans">

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-5 py-3 bg-deep border-b border-dashed border-border-subtle shrink-0 z-50">

        {/* Left: logo + project badge */}
        <div className="flex items-center gap-4">
          <button className="md:hidden p-1.5 -ml-1 text-text-muted hover:text-white transition-colors">
            <Menu className="w-5 h-5" />
          </button>
          <RouterLink to="/" className="flex items-center gap-2.5 hover:opacity-80 transition-opacity">
            <div className="w-7 h-7 flex items-center justify-center bg-gradient-to-br from-accent to-accent-dim rounded-md shadow-glow text-white">
              <Box className="w-4 h-4" />
            </div>
            <span className="font-semibold text-[15px] tracking-tight hidden sm:inline-block">CodeGraphContext</span>
          </RouterLink>
          {graphData && (
            <button
              onClick={() => { setGraphData(null); setSelectedFile(null); setSelectedNodeLabel(null); }}
              className="flex items-center gap-2 px-3 py-1.5 bg-surface border border-border-subtle rounded-lg text-sm text-text-secondary hover:bg-hover transition-colors"
            >
              <span className="w-1.5 h-1.5 bg-node-function rounded-full animate-pulse" />
              <span>Playground</span>
            </button>
          )}
        </div>

        {/* Center: search (only when graph loaded) */}
        {graphData ? (
          <div className="flex-1 max-w-md mx-6 relative" ref={searchRef}>
            <div className="flex items-center gap-2.5 px-3.5 py-2 bg-surface border border-border-subtle rounded-lg transition-all focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20">
              <Search className="w-4 h-4 text-text-muted flex-shrink-0" />
              <input
                ref={inputRef}
                type="text"
                placeholder="Search nodes..."
                value={searchQuery}
                onChange={e => { setSearchQuery(e.target.value); setIsSearchOpen(true); }}
                onFocus={() => setIsSearchOpen(true)}
                onBlur={() => setTimeout(() => setIsSearchOpen(false), 150)}
                className="flex-1 bg-transparent border-none outline-none text-sm text-text-primary placeholder:text-text-muted"
              />
              <kbd className="px-1.5 py-0.5 bg-elevated border border-border-subtle rounded text-[10px] text-text-muted font-mono">⌘K</kbd>
            </div>

            {/* Search dropdown */}
            {isSearchOpen && searchQuery.trim() && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-surface border border-border-subtle rounded-lg shadow-xl overflow-hidden z-50">
                {searchResults.length === 0 ? (
                  <div className="px-4 py-3 text-sm text-text-muted">No nodes found for "{searchQuery}"</div>
                ) : (
                  <div className="max-h-80 overflow-y-auto scrollbar-thin">
                    {searchResults.map(node => (
                      <button
                        key={node.id}
                        className="w-full px-4 py-2.5 flex items-center gap-3 text-left hover:bg-hover text-text-secondary transition-colors"
                        onClick={() => {
                          if (node.file) {
                             setSelectedFile(node.file);
                             setSelectedNodeLabel(node.label);
                          }
                          setIsSearchOpen(false);
                        }}
                      >
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                          style={{ backgroundColor: NODE_TYPE_COLORS[node.type] || '#6b7280' }} />
                        <span className="flex-1 truncate text-sm font-medium text-text-primary">{node.label}</span>
                        <span className="text-xs text-text-muted px-2 py-0.5 bg-elevated rounded">{node.type}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1" />
        )}

        {/* Right: icons */}
        <div className="flex items-center gap-2">
          {graphData && (
            <div className="flex items-center gap-2">
              <div className="relative">
                <button 
                  className="px-3 h-9 flex items-center gap-2 rounded-md bg-purple-600/10 border border-purple-500/20 text-purple-400/60 cursor-not-allowed transition-all text-xs font-semibold"
                  title="Exporting features are coming soon!"
                >
                  <Share2 className="w-4 h-4" />
                  <span>Work in Progress</span>
                </button>
                
                {isExportDropdownOpen && (
                  <div className="absolute top-full right-0 mt-2 w-48 bg-[#12121c] border border-[#2a2a3a] rounded-xl shadow-2xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="px-3 py-2 border-b border-[#2a2a3a] text-[10px] font-bold text-[#8888a0] uppercase tracking-wider">Share Repository</div>
                    
                    <a 
                      href={`https://twitter.com/intent/tweet?text=Exploring%20my%20codebase%20visually%20with%20CodeGraphContext!%20Check%20it%20out:&url=${encodeURIComponent(window.location.href)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-full px-4 py-2.5 flex items-center gap-3 text-left hover:bg-white/5 text-gray-300 transition-colors text-sm"
                    >
                      <Twitter className="w-4 h-4 text-[#1DA1F2]" />
                      <span>Twitter / X</span>
                    </a>
                    
                    <a 
                      href="https://discord.gg/your-invite-link" // Replace with actual discord if you have one or just a generic link
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-full px-4 py-2.5 flex items-center gap-3 text-left hover:bg-white/5 text-gray-300 transition-colors text-sm"
                    >
                      <MessageSquare className="w-4 h-4 text-[#5865F2]" />
                      <span>Discord</span>
                    </a>
                    
                    <button 
                      onClick={() => {
                        navigator.clipboard.writeText(window.location.href);
                        setIsExportDropdownOpen(false);
                      }}
                      className="w-full px-4 py-2.5 flex items-center gap-3 text-left hover:bg-white/5 text-gray-300 transition-colors text-sm border-t border-[#2a2a3a]"
                    >
                      <Link className="w-4 h-4 text-accent" />
                      <span>Copy Link</span>
                    </button>
                  </div>
                )}
              </div>

              <button 
                onClick={() => graphCanvasRef.current?.exportHTML()}
                className="px-3 h-9 flex items-center gap-2 rounded-md bg-accent/10 border border-accent/20 text-accent hover:bg-accent hover:text-white transition-all shadow-glow-soft text-xs font-medium"
                title="Download Standalone Interactive HTML"
              >
                <Download className="w-4 h-4" />
                <span>Download Graph</span>
              </button>
            </div>
          )}
          <div className="w-px h-6 bg-border-subtle mx-2" />
          <button className="w-9 h-9 flex items-center justify-center rounded-md text-text-secondary hover:bg-hover hover:text-text-primary transition-colors">
            <Settings className="w-[18px] h-[18px]" />
          </button>
          <button 
            onClick={() => setIsHintModalOpen(true)}
            className="w-9 h-9 flex items-center justify-center rounded-md text-text-secondary hover:bg-hover hover:text-text-primary transition-colors"
            title="How to Use"
          >
            <HelpCircle className="w-[18px] h-[18px]" />
          </button>
        </div>
      </header>

      {/* ── Main ─────────────────────────────────────────────────────────── */}
      <main className="flex-1 flex min-h-0">
        {graphData ? (
          <>
            {/* Sidebar Explorer */}
            <div 
              className={`border-r border-border-subtle bg-[#0d0d14] flex min-h-0 relative shrink-0 z-10 shadow-[4px_0_24px_rgba(0,0,0,0.2)] transition-all duration-300 ${isExplorerCollapsed ? 'w-10' : ''}`}
              style={!isExplorerCollapsed ? { width: `${explorerWidth}px` } : {}}
            >
              {!isExplorerCollapsed ? (
                <div className="flex flex-col w-full h-full overflow-hidden">
                  <div className="px-4 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center justify-between border-b border-border-subtle/50">
                    <div className="flex items-center gap-2">
                      <FileCode2 className="w-4 h-4 text-accent" />
                      Explorer
                    </div>
                    <button 
                      onClick={() => setIsExplorerCollapsed(true)}
                      className="p-1 rounded hover:bg-white/10 text-text-muted transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto scrollbar-thin py-2">
                    {graphData.nodes
                      .filter(n => n.type === 'file' || n.type === 'folder')
                      .filter(node => {
                        // Hide if any parent is collapsed
                        const parts = node.id.split('/');
                        for (let i = 1; i < parts.length; i++) {
                          const parentPath = parts.slice(0, i).join('/');
                          if (collapsedPaths.has(parentPath)) return false;
                        }
                        return true;
                      })
                      .sort((a, b) => a.id.localeCompare(b.id))
                      .map(node => {
                        const path = node.id;
                        const isSelected = selectedFile === path;
                        const isFolder = node.type === 'folder';
                        const isCollapsed = collapsedPaths.has(path);
                        const parts = path.split('/');
                        const name = parts[parts.length - 1];
                        const indent = (parts.length - 1) * 12;
                        
                        return (
                          <div 
                            key={path}
                            className={`
                              group relative w-full flex items-center gap-2 px-4 py-1.5 text-[12px] transition-all
                              ${isSelected ? 'bg-accent/10 text-accent font-medium' : 'text-text-secondary hover:bg-white/5 hover:text-text-primary'}
                            `}
                            style={{ paddingLeft: `${16 + indent}px` }}
                          >
                            {isSelected && <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-accent" />}
                            
                            <button
                              onClick={() => {
                                if (isFolder) {
                                  const next = new Set(collapsedPaths);
                                  if (isCollapsed) next.delete(path); else next.add(path);
                                  setCollapsedPaths(next);
                                }
                                setSelectedFile(path);
                              }}
                              className="flex-1 flex items-center gap-2 text-left truncate"
                              title={path}
                            >
                              {isFolder ? (
                                <div className="flex items-center gap-1 shrink-0">
                                  {isCollapsed ? <ChevronRight className="w-3 h-3 text-text-muted" /> : <ChevronDown className="w-3 h-3 text-text-muted" />}
                                  <Box className="w-3.5 h-3.5 opacity-50 text-indigo-400" />
                                </div>
                              ) : (
                                <FileText className="w-3.5 h-3.5 opacity-70 shrink-0" />
                              )}
                              <span className={`truncate ${isFolder ? 'font-semibold text-text-muted/80' : ''}`}>{name}</span>
                            </button>

                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setIllustratedPath(path === illustratedPath ? null : path);
                              }}
                              className={`
                                p-1 rounded hover:bg-accent/20 transition-all opacity-0 group-hover:opacity-100
                                ${illustratedPath === path ? 'opacity-100 text-yellow-400' : 'text-text-muted'}
                              `}
                              title="Illustrate in graph"
                            >
                              <Lightbulb className={`w-3 h-3 ${illustratedPath === path ? 'fill-yellow-400/20 shadow-glow-yellow' : ''}`} />
                            </button>
                          </div>
                        );
                      })}
                  </div>

                  {/* Resize Handle */}
                  <div 
                    onMouseDown={startResizing}
                    className="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-accent/40 active:bg-accent transition-colors z-20"
                  />
                </div>
              ) : (
                <div className="flex flex-col items-center pt-4 w-full h-full">
                  <button 
                    onClick={() => setIsExplorerCollapsed(false)}
                    className="p-2 rounded-md bg-accent/10 border border-accent/20 text-accent hover:bg-accent hover:text-white transition-all shadow-glow-soft"
                    title="Expand Explorer"
                  >
                    <FileCode2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
            {/* Graph Canvas */}
            <div className="flex-1 relative min-w-0">
              <GraphCanvas 
                ref={graphCanvasRef}
                data={graphData} 
                onReset={() => { setGraphData(null); setSelectedFile(null); setIllustratedPath(null); setSelectedNodeLabel(null); }}
                selectedFile={selectedFile}
                selectedPath={illustratedPath}
                customNodeColors={customNodeColors}
                customEdgeColors={customEdgeColors}
                visibleNodeTypes={visibleNodeTypes}
                visibleEdgeTypes={visibleEdgeTypes}
                onNodeClick={(file, label) => {
                  setSelectedFile(file);
                  setSelectedNodeLabel(label);
                }}
                onStageClick={() => {
                   setIllustratedPath(null);
                   setSelectedFile(null);
                   setSelectedNodeLabel(null);
                }}
              />
              
              {/* Type Toggles Floating Panel */}
              <div className="absolute top-4 left-4 z-20 flex flex-col gap-4">
                <div className={`bg-[#12121c]/90 border border-[#2a2a3a] rounded-xl backdrop-blur-md shadow-2xl transition-all duration-300 overflow-hidden ${isFiltersCollapsed ? 'w-10 h-10' : 'px-4 py-3 max-w-xs'}`}>
                  <div className={`flex items-center justify-between ${isFiltersCollapsed ? 'w-full h-full flex justify-center items-center' : 'mb-3 border-b border-border-subtle/50 pb-2'}`}>
                    {!isFiltersCollapsed && <span className="text-[11px] font-bold text-text-muted uppercase tracking-wider font-mono">Filters</span>}
                    <button 
                      onClick={() => setIsFiltersCollapsed(!isFiltersCollapsed)}
                      className="p-1.5 rounded-md hover:bg-white/10 transition-colors"
                      title={isFiltersCollapsed ? 'Expand Filters' : 'Collapse Filters'}
                    >
                      <Filter className={`w-3.5 h-3.5 text-text-muted transition-transform duration-300 ${isFiltersCollapsed ? 'rotate-0' : 'scale-110 opacity-80'}`} />
                    </button>
                  </div>
                  
                  {!isFiltersCollapsed && (
                    <div className="space-y-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-widest text-[#8888a0] mb-2 font-semibold">Nodes</p>
                      <div className="grid grid-cols-2 gap-2">
                        {['folder', 'file', 'class', 'function', 'interface', 'method', 'struct', 'enum', 'namespace', 'module'].map(type => {
                          const isActive = visibleNodeTypes.has(type);
                          const color = customNodeColors[type] || NODE_TYPE_COLORS[type] || '#6b7280';
                          return (
                            <div key={type} className="group relative flex items-center gap-1">
                              <button
                                onClick={() => {
                                  const next = new Set(visibleNodeTypes);
                                  if (isActive) next.delete(type); else next.add(type);
                                  setVisibleNodeTypes(next);
                                }}
                                className={`flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg text-[11px] font-medium transition-all border
                                  ${isActive 
                                    ? 'bg-accent/20 border-accent/40 text-text-primary' 
                                    : 'bg-void border-transparent text-text-muted hover:border-[#2a2a3a] hover:text-text-secondary'}`}
                              >
                                <div className="w-1.5 h-1.5 rounded-full shrink-0" 
                                  style={{ backgroundColor: color }} />
                                <span className="capitalize">{type}</span>
                              </button>
                              <div className="relative flex items-center">
                                <label className="cursor-pointer p-1 rounded hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <Pipette className="w-3 h-3 text-text-muted hover:text-accent" />
                                  <input 
                                    type="color" 
                                    className="absolute inset-0 w-0 h-0 opacity-0 pointer-events-none"
                                    value={color}
                                    onChange={(e) => setCustomNodeColors(prev => ({ ...prev, [type]: e.target.value }))}
                                  />
                                </label>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                      <div>
                        <p className="text-[10px] uppercase tracking-widest text-[#8888a0] mb-2 font-semibold">Edges</p>
                        <div className="grid grid-cols-2 gap-2">
                          {['contains', 'defines', 'imports', 'calls', 'inherits', 'implements', 'extends'].map(type => {
                            const isActive = visibleEdgeTypes.has(type);
                            const edgeColor = customEdgeColors[type] || EDGE_STYLES[type]?.color || '#7c3aed';
                            return (
                              <div key={type} className="group relative flex items-center gap-1">
                                <button
                                  onClick={() => {
                                    const next = new Set(visibleEdgeTypes);
                                    if (isActive) next.delete(type); else next.add(type);
                                    setVisibleEdgeTypes(next);
                                  }}
                                  className={`flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg text-[11px] font-medium transition-all border
                                    ${isActive 
                                      ? 'bg-accent/20 border-accent/40 text-text-primary' 
                                      : 'bg-void border-transparent text-text-muted hover:border-[#2a2a3a] hover:text-text-secondary'}`}
                                >
                                  <div className="w-3 h-0.5 rounded-full shrink-0" 
                                    style={{ backgroundColor: edgeColor }} />
                                  <span className="capitalize">{type}</span>
                                </button>
                                <div className="relative flex items-center">
                                  <label className="cursor-pointer p-1 rounded hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <Pipette className="w-3 h-3 text-text-muted hover:text-accent" />
                                    <input 
                                      type="color" 
                                      className="absolute inset-0 w-0 h-0 opacity-0 pointer-events-none"
                                      value={edgeColor}
                                      onChange={(e) => setCustomEdgeColors(prev => ({ ...prev, [type]: e.target.value }))}
                                    />
                                  </label>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                  </div>
                )}
              </div>
            </div>
          </div>

            {/* Code Panel */}
            {selectedFile && graphData.files[selectedFile] && (
              <div className="w-[450px] border-l border-border-subtle bg-[#0a0a0f] flex flex-col shrink-0 z-10 shadow-[-4px_0_24px_rgba(0,0,0,0.2)]">
                <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle/50 bg-[#0d0d14]">
                  <div className="flex items-center gap-2 min-w-0">
                     <FileCode2 className="w-4 h-4 text-accent shrink-0" />
                     <span className="text-sm font-medium text-text-primary truncate" title={selectedFile}>
                       {selectedFile.split('/').pop()}
                     </span>
                     <span className="text-xs text-text-muted truncate ml-2 hidden sm:inline-block">
                       {selectedFile}
                     </span>
                  </div>
                  <button 
                    onClick={() => { setSelectedFile(null); setSelectedNodeLabel(null); }}
                    className="p-1 rounded-md text-text-muted hover:text-white hover:bg-white/10 transition-colors shrink-0"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div 
                  ref={codePanelRef}
                  className="flex-1 overflow-y-auto scrollbar-thin p-4 text-[13px] font-mono leading-relaxed bg-[#0a0a0f] text-gray-300"
                >
                  {graphData.files[selectedFile].split('\n').map((line, i) => (
                    <div 
                      key={i} 
                      data-line={i}
                      className="flex hover:bg-white/5 px-2 -mx-2 rounded transition-colors"
                    >
                      <span className="w-8 shrink-0 text-right pr-4 text-gray-600 select-none">
                        {i + 1}
                      </span>
                      <span className="whitespace-pre-wrap word-break-all flex-1">
                        {line || ' '}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          /* ── Onboarding / Dropzone ─────────────────────────────────── */
          <div className="flex-1 flex flex-col items-center justify-center p-6 relative overflow-hidden">
            {/* Ambient blobs */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
              <div className="absolute -top-[20%] -right-[10%] w-[50%] h-[70%] rounded-[100%] bg-gradient-to-br from-accent/6 to-transparent blur-[140px] rotate-[-15deg]" />
              <div className="absolute -bottom-[20%] -left-[10%] w-[60%] h-[60%] rounded-[100%] bg-gradient-to-tr from-node-file/5 to-transparent blur-[120px]" />
            </div>

            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => !loading && fileInputRef.current?.click()}
              className={`
                relative group flex flex-col items-center justify-center w-full max-w-2xl h-96
                border-2 border-dashed rounded-[2rem] overflow-hidden cursor-pointer z-10
                transition-all duration-500 hover:scale-[1.015]
                ${loading || isDragging
                  ? 'border-accent/60 bg-accent/8 shadow-glow-soft scale-[1.015]'
                  : 'border-border-default bg-surface/40 hover:border-accent/50 hover:bg-accent/5 hover:shadow-glow-soft'}
              `}
            >
              {/* Orb */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 bg-accent blur-[120px] opacity-10 pointer-events-none group-hover:opacity-25 transition-opacity duration-700" />

              {loading ? (
                <div className="relative z-10 flex flex-col items-center gap-5">
                  <div className="relative w-20 h-20">
                    <div className="absolute inset-0 border-4 border-accent/20 rounded-full" />
                    <div className="absolute inset-0 border-4 border-accent rounded-full border-t-transparent animate-spin" />
                    <div className="absolute inset-2 border-2 border-accent-dim/40 rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
                    <Box className="absolute inset-0 m-auto w-7 h-7 text-accent animate-pulse" />
                  </div>
                  <div className="text-center">
                    <p className="text-base font-medium text-text-primary">{progressMsg}</p>
                    <p className="text-text-muted font-mono text-xs uppercase tracking-widest mt-1">Client-side WebAssembly · Tree-sitter</p>
                  </div>
                </div>
              ) : (
                <div className="relative z-10 flex flex-col items-center p-8 text-center gap-5 w-full">
                  <div className="flex bg-elevated/50 p-1 rounded-xl border border-border-subtle mb-4">
                    <button 
                      onClick={(e) => { e.stopPropagation(); setIsRemoteMode(false); }}
                      className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${!isRemoteMode ? 'bg-accent text-white shadow-lg' : 'text-text-secondary hover:text-text-primary'}`}
                    >
                      <UploadCloud className="w-3.5 h-3.5" />
                      Local Repo
                    </button>
                    <button 
                      onClick={(e) => { e.stopPropagation(); setIsRemoteMode(true); }}
                      className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${isRemoteMode ? 'bg-accent text-white shadow-lg' : 'text-text-secondary hover:text-text-primary'}`}
                    >
                      <Globe className="w-3.5 h-3.5" />
                      Remote Repo
                    </button>
                  </div>

                  {!isRemoteMode ? (
                    <>
                      <div className="w-20 h-20 rounded-2xl bg-elevated border border-border-subtle flex items-center justify-center shadow-xl group-hover:scale-110 group-hover:shadow-[0_0_25px_rgba(124,58,237,0.35)] group-hover:border-accent/50 transition-all duration-300">
                        <UploadCloud className="w-10 h-10 text-text-muted group-hover:text-accent transition-colors duration-300" />
                      </div>
                      <div>
                        <h1 className="text-3xl font-semibold text-text-primary tracking-tight">Visualize your Codebase</h1>
                        <p className="text-text-secondary mt-2 max-w-sm text-[15px] leading-relaxed">
                          Drop a local repository or select a directory. AST relationships are extracted
                          entirely client-side using WebAssembly.
                        </p>
                      </div>
                      <button className="px-8 py-3 bg-elevated hover:bg-accent text-text-primary border border-border-subtle hover:border-accent rounded-xl font-medium shadow-lg hover:shadow-glow transition-all duration-300 active:scale-95">
                        Select Local Directory
                      </button>
                    </>
                  ) : (
                    <form 
                      onSubmit={handleRemoteFetch} 
                      onClick={(e) => e.stopPropagation()}
                      className="w-full max-w-md flex flex-col gap-4"
                    >
                      <div className="text-left">
                        <label className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1.5 block">Repository URL</label>
                        <div className="flex items-center gap-2.5 px-4 py-3 bg-elevated border border-border-subtle rounded-xl focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 transition-all">
                          <Link className="w-4 h-4 text-text-muted" />
                          <input 
                            type="text"
                            placeholder="https://github.com/owner/repo"
                            value={repoUrl}
                            onChange={(e) => setRepoUrl(e.target.value)}
                            className="bg-transparent border-none outline-none text-sm text-text-primary w-full"
                          />
                        </div>
                      </div>
                      <div className="text-left">
                        <div className="flex items-center justify-between mb-1.5">
                          <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block">Access Token (Optional)</label>
                          <span className="text-[10px] text-text-muted bg-surface px-1.5 py-0.5 rounded border border-border-subtle">For private repos</span>
                        </div>
                        <div className="flex items-center gap-2.5 px-4 py-3 bg-elevated border border-border-subtle rounded-xl focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 transition-all">
                          <Lock className="w-4 h-4 text-text-muted" />
                          <input 
                            type="password"
                            placeholder="ghp_xxxxxxxxxxxx"
                            value={repoToken}
                            onChange={(e) => setRepoToken(e.target.value)}
                            className="bg-transparent border-none outline-none text-sm text-text-primary w-full"
                          />
                        </div>
                      </div>
                      <button 
                        type="submit"
                        disabled={!repoUrl.trim() || loading}
                        className="mt-2 px-8 py-3 bg-accent hover:bg-accent-light text-white rounded-xl font-medium shadow-lg hover:shadow-glow transition-all duration-300 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Fetch & Visualize
                      </button>
                      <p className="text-[11px] text-text-muted mt-2">
                        Currently supports GitHub and GitLab repositories
                      </p>
                    </form>
                  )}
                </div>
              )}
            </div>

            <input
              type="file" ref={fileInputRef} onChange={handleDirectorySelect} className="hidden"
              {...({ webkitdirectory: 'true', directory: 'true' } as any)} multiple
            />
          </div>
        )}
      </main>

      {/* ── Status Bar (mirrors GitNexus StatusBar) ─────────────────────── */}
      <footer className="flex items-center justify-between px-5 py-2 bg-deep border-t border-dashed border-border-subtle text-[11px] text-text-muted shrink-0">
        {/* Left: status */}
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-node-function rounded-full" />
          <span>{loading ? progressMsg : 'Ready'}</span>
        </div>

        {/* Center: sponsor link */}
        <div className="flex flex-col items-center gap-1">
          <a
            href="https://github.com/Shashankss1205/CodeGraphContext"
            target="_blank" rel="noreferrer"
            className="group flex items-center gap-2 px-3 py-1 rounded-full bg-pink-500/10 border border-pink-500/20 hover:bg-pink-500/20 hover:border-pink-500/40 hover:scale-[1.02] transition-all duration-200"
          >
            <Heart className="w-3.5 h-3.5 text-pink-500 fill-pink-500/40 group-hover:fill-pink-500 transition-all duration-200 animate-pulse" />
            <span className="text-[11px] font-medium text-pink-400 group-hover:text-pink-300 transition-colors">Star us on GitHub</span>
          </a>
          <span className="text-[9px] text-text-muted/60 uppercase tracking-widest font-medium">Made with love by Shashank</span>
        </div>

        {/* Right: stats */}
        <div className="flex items-center gap-3" />
      </footer>

      {/* ── Hint Modal ─────────────────────────────────────────────────── */}
      {isHintModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div 
            className="absolute inset-0 bg-void/80 backdrop-blur-sm animate-in fade-in duration-300" 
            onClick={() => setIsHintModalOpen(false)}
          />
          <div className="relative w-full max-w-lg bg-surface border border-border-subtle rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
            <div className="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-accent to-accent-dim" />
            
            <div className="p-8">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 flex items-center justify-center bg-accent/10 rounded-xl">
                    <Lightbulb className="w-5 h-5 text-accent" />
                  </div>
                  <h2 className="text-xl font-bold tracking-tight">CodeGraphContext</h2>
                </div>
                <button 
                  onClick={() => setIsHintModalOpen(false)}
                  className="p-2 rounded-xl hover:bg-hover transition-colors text-text-muted hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-6">
                <section>
                  <h3 className="text-xs font-bold text-accent uppercase tracking-widest mb-2 font-mono">What is this?</h3>
                  <p className="text-text-secondary text-sm leading-relaxed">
                    CodeGraphContext is a next-generation codebase visualizer. It builds a multi-dimensional map of your project's architecture, extracting AST relationships entirely in your browser using WebAssembly.
                  </p>
                </section>

                <section>
                  <h3 className="text-xs font-bold text-accent uppercase tracking-widest mb-3 font-mono">How to use</h3>
                  <ul className="space-y-3">
                    {[
                      { icon: Box, text: "Navigate through the file explorer to filter specific modules." },
                      { icon: Search, text: "Search across variables, functions, and classes." },
                      { icon: Filter, text: "Toggle node and edge types to focus on specific architectural layers." },
                      { icon: Share2, text: "Export a fully interactive, standalone HTML version of your graph." }
                    ].map((item, i) => (
                      <li key={i} className="flex gap-4">
                        <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-elevated/50 border border-border-subtle shrink-0">
                          <item.icon className="w-3.5 h-3.5 text-text-muted" />
                        </div>
                        <p className="text-sm text-text-secondary mt-1">{item.text}</p>
                      </li>
                    ))}
                  </ul>
                </section>

                <div className="pt-4 flex justify-end">
                  <button 
                    onClick={() => setIsHintModalOpen(false)}
                    className="px-6 py-2.5 bg-accent hover:bg-accent-light text-white rounded-xl text-sm font-semibold transition-all shadow-glow hover:scale-[1.02] active:scale-95"
                  >
                    Got it, thanks!
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
