import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Github, ExternalLink, Copy, Check, Sparkles, FolderUp, Mail, Loader2, Package, Download, CheckCircle2, XCircle, Clock } from "lucide-react";
import heroGraph from "@/assets/hero-graph.jpg";
import { useState, useEffect } from "react";
import ShowDownloads from "@/components/ShowDownloads";
import { ThemeToggle } from "@/components/ThemeToggle";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import LocalUploader from "@/components/LocalUploader";
import CodeGraphViewer from "@/components/CodeGraphViewer";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";

const OUTLINE_BUTTON_CLASSES = "border-gray-300 hover:border-primary/60 bg-white/80 backdrop-blur-sm shadow-sm transition-smooth text-gray-900 dark:bg-transparent dark:text-foreground dark:border-primary/30 w-full sm:w-auto";

const HeroSection = () => {
  const [stars, setStars] = useState<number | null>(null);
  const [forks, setForks] = useState<number | null>(null);
  const [version, setVersion] = useState("");
  const [copied, setCopied] = useState(false);

  // Indexing states
  const [activeTab, setActiveTab] = useState<'client' | 'server'>('client');
  const [repoUrl, setRepoUrl] = useState("");
  const [email, setEmail] = useState("");
  const [generationStatus, setGenerationStatus] = useState<any>({ status: "idle" });
  const [progress, setProgress] = useState(0);
  const [graphData, setGraphData] = useState<any>(null);

  useEffect(() => {
    async function fetchVersion() {
      try {
        const res = await fetch(
          "https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/README.md"
        );
        if (!res.ok) throw new Error("Failed to fetch README");

        const text = await res.text();
        const match = text.match(
          /\*\*Version:\*\*\s*([0-9]+\.[0-9]+\.[0-9]+)/i
        );
        setVersion(match ? match[1] : "N/A");
      } catch (err) {
        console.error(err);
        setVersion("N/A");
      }
    }
    fetchVersion();
  }, []);

  useEffect(() => {
    fetch("https://api.github.com/repos/CodeGraphContext/CodeGraphContext")
      .then((response) => response.json())
      .then((data) => {
        setStars(data.stargazers_count);
        setForks(data.forks_count);
      })
      .catch((error) => console.error("Error fetching GitHub stats:", error));
  }, []);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText("pip install codegraphcontext");
      setCopied(true);
      toast.success("Copied to clipboard!");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      toast.error("Failed to copy");
    }
  };

  const handleGenerateBundle = async () => {
    if (!repoUrl.trim()) {
      toast.error("Please enter a GitHub repository URL");
      return;
    }

    setGenerationStatus({ status: "validating" });
    setProgress(5);

    const isDevelopment = import.meta.env.DEV;

    if (isDevelopment) {
      toast.info("🚧 Development Mode: Showing mock response for UI testing.");

      setTimeout(() => {
        setGenerationStatus({
          status: "ready",
          message: "Mock bundle ready (development mode)",
          repository: repoUrl.replace("https://github.com/", ""),
          download_url: "#",
          bundle: {
            repo: repoUrl.replace("https://github.com/", ""),
            bundle_name: "example-repo-v1.0.0-abc123.cgc",
            size: "25MB",
            generated_at: new Date().toISOString(),
            commit: "abc123",
          },
        });
        setProgress(100);
      }, 2000);
      return;
    }

    try {
      const response = await fetch("/api/trigger-bundle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repoUrl, email: "" }),
      });

      const data = await response.json();

      if (!response.ok) {
        setGenerationStatus({
          status: "error",
          error: data.error || "Failed to generate bundle",
        });
        setProgress(0);
        return;
      }

      if (data.status === "exists") {
        setGenerationStatus({
          status: "ready",
          message: "Bundle already exists!",
          repository: data.bundle.repo,
          download_url: data.download_url,
          bundle: data.bundle,
        });
        setProgress(100);
        toast.success("Bundle Found! This repository has already been indexed.");
      } else if (data.status === "triggered") {
        setGenerationStatus({
          status: "triggered",
          message: data.message || "Bundle generation started",
          repository: data.repository,
          run_id: data.run_id,
          run_url: data.run_url,
          estimated_time: data.estimated_time,
          repo_size_mb: data.repo_size_mb,
        });
        setProgress(15);
        toast.success(`Generation Started! Indexing ${data.repository}.`);

        if (data.run_id) {
          pollBundleStatus(data.run_id, data.repository);
        }
      }
    } catch (err: any) {
      setGenerationStatus({
        status: "error",
        error: err.message || "Network error",
      });
      setProgress(0);
    }
  };

  const pollBundleStatus = async (runId: string, repo: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/bundle-status?run_id=${runId}`);
        const data = await response.json();

        if (data.status === "completed") {
          clearInterval(pollInterval);

          if (data.conclusion === "success") {
            const manifestResponse = await fetch(`/api/bundle-status?repo=${repo}`);
            const manifestData = await manifestResponse.json();

            if (manifestData.status === "ready") {
              setGenerationStatus({
                status: "ready",
                message: "Bundle ready for download!",
                repository: repo,
                download_url: manifestData.download_url,
                bundle: manifestData.bundle,
              });
              setProgress(100);
              toast.success("Bundle Ready! Your bundle has been generated successfully.");
              
              // Live browser alert notification
              alert(`🎉 CGC Live Alert:\n\nYour repository bundle [${repo}] has been successfully generated and is ready to explore!`);
            }
          } else {
            setGenerationStatus({
              status: "error",
              error: "Bundle generation failed. Please try again.",
            });
            setProgress(0);
          }
        } else if (data.status === "in_progress") {
          setGenerationStatus((prev: any) => ({ ...prev, status: "processing" }));
          setProgress(data.progress || 50);
        }
      } catch (err) {
        console.error("Error polling status:", err);
      }
    }, 10000);

    setTimeout(() => clearInterval(pollInterval), 30 * 60 * 1000);
  };

  const renderServerStatusContent = () => {
    switch (generationStatus.status) {
      case "idle":
        return (
          <div className="space-y-4 w-full relative z-10">
            <div className="flex flex-col gap-3">
              <Input
                type="url"
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="bg-black/40 border-white/10 text-white placeholder-gray-500 rounded-xl py-5"
                onKeyDown={(e) => e.key === "Enter" && handleGenerateBundle()}
              />
              {/* Live Completion Notification Notice */}
              <div className="bg-purple-500/10 border border-purple-500/20 rounded-xl p-3.5 flex items-start gap-2.5">
                <Sparkles className="w-5 h-5 text-purple-400 shrink-0 mt-0.5 animate-pulse" />
                <div className="text-[11px] text-gray-300 leading-relaxed">
                  <span className="font-bold text-white block mb-0.5">Live Completion Alert</span>
                  If you wish to get a live browser alert for completion, keep this tab open. CodeGraphContext will notify you the moment your CodeGraph is generated successfully.
                </div>
              </div>

              <Button
                onClick={handleGenerateBundle}
                className="w-full bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-600 hover:to-indigo-700 text-white rounded-xl py-6 font-semibold"
              >
                <Package className="mr-2 h-4 w-4" />
                Generate Bundle
              </Button>
            </div>
            <p className="text-[10px] text-gray-400 text-center">
              ⏱️ Generation typically takes 5-10 minutes. Bundles are cached for 30 days.
            </p>
          </div>
        );

      case "validating":
        return (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-white/5 border border-white/10 relative z-10">
            <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
            <span className="text-sm text-gray-300">Validating repository...</span>
          </div>
        );

      case "triggered":
      case "processing":
        return (
          <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-4 relative z-10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Clock className="h-4 w-4 text-blue-400 animate-pulse" />
                Generating Bundle
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-blue-500/20 text-blue-300 border border-blue-500/30">
                {generationStatus.status === "triggered" ? "Queued" : "Indexing"}
              </span>
            </div>
            <p className="text-xs text-gray-400 truncate">{generationStatus.repository}</p>
            
            <div className="space-y-1">
              <Progress value={progress} className="h-1.5" />
              <div className="flex justify-between text-[10px] text-gray-400">
                <span>Estimated: {generationStatus.estimated_time || "5-10m"}</span>
                <span>{progress}%</span>
              </div>
            </div>

            {generationStatus.run_url && (
              <Button variant="link" asChild className="p-0 h-auto text-xs text-purple-400 hover:text-purple-300">
                <a href={generationStatus.run_url} target="_blank" rel="noopener noreferrer">
                  View Progress on GitHub <ExternalLink className="ml-1 h-3 w-3" />
                </a>
              </Button>
            )}
          </div>
        );

      case "exists":
      case "ready":
        return (
          <div className="p-4 rounded-xl bg-green-500/10 border border-green-500/30 space-y-4 relative z-10">
            <div className="flex items-center gap-2 text-sm font-semibold text-green-400">
              <CheckCircle2 className="h-4 w-4" />
              Bundle Ready!
            </div>
            <p className="text-xs text-gray-400 truncate">{generationStatus.repository}</p>

            {generationStatus.bundle && (
              <div className="grid grid-cols-2 gap-2 text-[10px] text-gray-400 font-mono">
                <div>Size: {generationStatus.bundle.size}</div>
                <div>Commit: {generationStatus.bundle.commit?.slice(0, 7)}</div>
              </div>
            )}

            <div className="flex gap-2">
              <Button asChild size="sm" className="flex-1 bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-lg">
                <a href={`/explore?bundle_url=${encodeURIComponent(generationStatus.download_url)}`}>
                  <img src="/cgcIcon.png" alt="CGC" className="w-4 h-4 mr-2" />
                  Visualize
                </a>
              </Button>
              <Button variant="outline" size="sm" asChild className="flex-1 text-xs">
                <a href={generationStatus.download_url} download>
                  <Download className="mr-2 h-3 w-3" />
                  Download
                </a>
              </Button>
            </div>
            
            <Button
              variant="link"
              size="sm"
              className="w-full text-center text-xs text-gray-500 hover:text-gray-400 h-auto p-0"
              onClick={() => {
                setGenerationStatus({ status: "idle" });
                setRepoUrl("");
                setProgress(0);
              }}
            >
              Generate Another
            </Button>
          </div>
        );

      case "error":
        return (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 space-y-3 relative z-10">
            <div className="flex items-center gap-2 text-sm font-semibold text-red-400">
              <XCircle className="h-4 w-4" />
              Generation Failed
            </div>
            <p className="text-xs text-red-300 leading-relaxed">{generationStatus.error}</p>
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs text-red-400 hover:text-red-300 border-red-500/30"
              onClick={() => {
                setGenerationStatus({ status: "idle" });
                setProgress(0);
              }}
            >
              Try Again
            </Button>
          </div>
        );

      default:
        return null;
    }
  };

  if (graphData) {
    return (
      <div className="fixed inset-0 z-50 bg-background w-full h-full">
        <CodeGraphViewer data={graphData} onClose={() => setGraphData(null)} />
      </div>
    );
  }

  return (
    <section className="relative min-h-screen flex flex-col md:flex-row md:items-center md:justify-center overflow-x-hidden pt-36 pb-12 md:py-0">
      <motion.div
        key="hero"
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.4 }}
        className="absolute inset-0 w-full h-full"
      >
        {/* Background Image */}
        <div
          className="absolute inset-0 bg-cover bg-center bg-no-repeat opacity-20 brightness-110 saturate-110 dark:opacity-30 dark:brightness-100 dark:saturate-100"
          style={{ backgroundImage: `url(${heroGraph})` }}
        />

        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-white/60 via-white/40 to-white/80 dark:from-background/90 dark:via-background/80 dark:to-background/90" />

        {/* Content (2-Column Grid) */}
        <div className="relative z-10 w-full max-w-7xl mx-auto px-6 pt-32 lg:pt-32 pb-16 lg:pb-20 flex flex-col lg:justify-center lg:h-full">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
            
            {/* LEFT COLUMN: Interactive Indexer Widget */}
            <div className="lg:col-span-6 w-full flex justify-center lg:justify-end animate-float-up" data-aos="fade-right">
              <div className="w-full max-w-lg p-6 sm:p-8 border border-white/10 dark:border-white/20 rounded-[2rem] bg-black/40 backdrop-blur-xl shadow-2xl relative overflow-hidden flex flex-col min-h-[500px]">
                
                {/* Segmented controls */}
                <div className="grid grid-cols-2 bg-white/5 p-1.5 rounded-2xl mb-6 relative z-10 w-full shadow-inner border border-white/5 gap-1.5">
                  <button 
                    onClick={() => setActiveTab('client')} 
                    className={`py-2.5 px-3 text-xs sm:text-sm font-semibold rounded-xl transition-all duration-300 ${activeTab === 'client' ? 'bg-gradient-to-br from-purple-500 to-indigo-600 text-white shadow-lg' : 'text-gray-400 hover:text-white hover:bg-white/10'}`}
                  >
                    Client-Based Indexer
                  </button>
                  <button 
                    onClick={() => setActiveTab('server')} 
                    className={`py-2.5 px-3 text-xs sm:text-sm font-semibold rounded-xl transition-all duration-300 ${activeTab === 'server' ? 'bg-gradient-to-br from-purple-500 to-indigo-600 text-white shadow-lg' : 'text-gray-400 hover:text-white hover:bg-white/10'}`}
                  >
                    Server-Based Indexer
                  </button>
                </div>

                {/* Conditional Rendering of Forms */}
                {activeTab === 'client' ? (
                  <div className="w-full text-left flex-1 flex flex-col relative z-10">
                    <div className="mb-4">
                      <h4 className="text-sm font-bold text-white mb-1">⚡ Fast & Local Indexing</h4>
                      <p className="text-[11px] text-gray-400">Instantly parse repository files directly in-browser. 100% private.</p>
                    </div>
                    <LocalUploader onComplete={setGraphData} plain={true} />
                  </div>
                ) : (
                  <div className="w-full text-left flex-1 flex flex-col justify-start relative z-10">
                    <div className="mb-4">
                      <h4 className="text-sm font-bold text-white mb-1">🔮 Deep Cloud Indexing</h4>
                      <p className="text-[11px] text-gray-400">Run a remote build via GitHub Actions for larger repositories.</p>
                    </div>
                    {renderServerStatusContent()}
                  </div>
                )}

                {/* Decorative Blob */}
                <div className="absolute -bottom-32 -right-32 w-80 h-80 bg-purple-600/15 blur-3xl rounded-full z-0 pointer-events-none"></div>
              </div>
            </div>

            {/* RIGHT COLUMN: Value Proposition & Commands */}
            <div className="lg:col-span-6 flex flex-col justify-center text-left" data-aos="fade-left">
              <div className="flex mb-6">
                <Badge variant="secondary" className="text-sm font-medium px-4 py-1.5 shadow-sm bg-white/50 backdrop-blur dark:bg-white/10">
                  <div className="w-2.5 h-2.5 bg-accent rounded-full mr-2.5 animate-graph-pulse" />
                  Version {version} &bull; MIT License
                </Badge>
              </div>



              <h1 className="inline-block w-max whitespace-nowrap text-3xl sm:text-4xl md:text-5xl lg:text-5xl xl:text-6xl 2xl:text-7xl font-bold pr-2 mb-6 bg-gradient-to-r from-purple-700 via-indigo-700 to-purple-900 dark:bg-gradient-primary bg-clip-text py-2 text-transparent leading-tight tracking-tight drop-shadow-[0_2px_8px_rgba(0,0,0,0.15)]">
                CodeGraphContext
              </h1>

              <p className="text-xl md:text-2xl text-muted-foreground mb-3 leading-relaxed max-w-2xl">
                A powerful CLI toolkit &amp; MCP server that indexes local code into a
              </p>
              <p className="text-xl md:text-2xl text-accent font-semibold mb-6 sm:mb-10">
                knowledge graph for AI assistants
              </p>

              <div className="flex flex-col sm:flex-row gap-4 items-start mb-6 sm:mb-12">
                <Button 
                  size="lg" 
                  className="bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-800 text-primary-foreground hover:opacity-90 transition-all duration-300 shadow-glow ring-1 ring-primary/20 dark:bg-gradient-primary cursor-pointer w-full sm:w-auto min-w-[280px] h-14 text-lg rounded-xl"
                  onClick={handleCopy}
                  title="Click to copy install command"
                >
                  {copied ? (
                    <Check className="mr-3 h-5 w-5 animate-in zoom-in duration-300" />
                  ) : (
                    <Copy className="mr-3 h-5 w-5" />
                  )}
                  pip install codegraphcontext
                </Button>

                <div className="flex gap-4 w-full sm:w-auto">
                  <Button variant="outline" size="lg" asChild className={`${OUTLINE_BUTTON_CLASSES} h-14 rounded-xl`}>
                    <a href="https://github.com/CodeGraphContext/CodeGraphContext" target="_blank" rel="noopener noreferrer">
                      <Github className="mr-2 h-5 w-5" />
                      GitHub
                      <ExternalLink className="ml-2 h-4 w-4 text-muted-foreground" />
                    </a>
                  </Button>
                  <Button variant="outline" size="lg" asChild className={`${OUTLINE_BUTTON_CLASSES} h-14 rounded-xl`}>
                    <a href="https://codegraphcontext.github.io/" target="_blank" rel="noopener noreferrer">
                      Docs
                      <ExternalLink className="ml-2 h-4 w-4 text-muted-foreground" />
                    </a>
                  </Button>
                </div>
              </div>

              {/* Stats */}
              <div className="flex flex-wrap items-center gap-8 text-sm text-muted-foreground font-medium">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-graph-node-1 rounded-full animate-graph-pulse" />
                  {stars !== null ? <span>{stars} GitHub Stars</span> : <span>Loading...</span>}
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-graph-node-2 rounded-full animate-graph-pulse" style={{ animationDelay: '0.5s' }} />
                  {forks !== null ? <span>{forks} Forks</span> : <span>Loading...</span>}
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-graph-node-3 rounded-full animate-graph-pulse" style={{ animationDelay: '1s' }} />
                  <span><ShowDownloads /></span>
                </div>
              </div>
            </div>

          </div>
        </div>

        {/* Floating Graph Nodes Background Decoration */}
        <div className="absolute top-20 left-10 w-8 h-8 graph-node animate-graph-pulse" style={{ animationDelay: '0.2s' }} />
        <div className="absolute top-40 right-20 w-6 h-6 graph-node animate-graph-pulse" style={{ animationDelay: '0.8s' }} />
        <div className="absolute bottom-32 left-20 w-10 h-10 graph-node animate-graph-pulse" style={{ animationDelay: '1.2s' }} />
        <div className="absolute bottom-20 right-10 w-7 h-7 graph-node animate-graph-pulse" style={{ animationDelay: '0.6s' }} />
      </motion.div>
    </section>
  );
};

export default HeroSection;