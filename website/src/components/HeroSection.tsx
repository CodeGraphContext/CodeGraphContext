import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Github, ExternalLink, Copy, Check, Sparkles, FolderUp, Mail, Loader2, Package, Download, CheckCircle2, XCircle, Clock } from "lucide-react";
import { useState, useEffect } from "react";
import ShowDownloads from "@/components/ShowDownloads";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import LocalUploader from "@/components/LocalUploader";
import CodeGraphViewer from "@/components/CodeGraphViewer";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import MagneticButton from "@/components/MagneticButton";

const OUTLINE_BUTTON_CLASSES = "border-cyan-400/50 hover:border-cyan-400 bg-transparent transition-colors text-cyan-50 shadow-[0_0_10px_rgba(34,211,238,0.1)] w-full sm:w-auto h-12 rounded-full font-semibold uppercase tracking-widest text-xs";

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
        const match = text.match(/\*\*Version:\*\*\s*([0-9]+\.[0-9]+\.[0-9]+)/i);
        setVersion(match ? match[1] : "N/A");
      } catch (err) {
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
                className="bg-white dark:bg-black border-gray-200 dark:border-white/20 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 rounded-2xl py-6 border-2 focus-visible:border-purple-500 dark:focus-visible:border-white focus-visible:ring-0"
                onKeyDown={(e) => e.key === "Enter" && handleGenerateBundle()}
              />
              <div className="bg-black/5 dark:bg-white/5 border border-gray-200 dark:border-white/20 rounded-2xl p-4 flex items-start gap-3">
                <Sparkles className="w-5 h-5 text-purple-600 dark:text-white shrink-0 mt-0.5" />
                <div className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed font-mono">
                  <span className="font-bold text-gray-900 dark:text-white block mb-1">LIVE COMPLETION ALERT</span>
                  Keep this tab open. We will notify you the moment your CodeGraph is generated successfully.
                </div>
              </div>

              <MagneticButton
                onClick={handleGenerateBundle}
                className="w-full bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] rounded-2xl py-6 font-bold uppercase tracking-widest text-xs transition-colors"
              >
                <Package className="mr-2 h-4 w-4" />
                Generate Bundle
              </MagneticButton>
            </div>
            <p className="text-[10px] text-gray-500 text-center font-mono uppercase tracking-widest mt-4">
              Generation typically takes 5-10 minutes.
            </p>
          </div>
        );

      case "validating":
        return (
          <div className="flex items-center gap-3 p-6 border border-white/20 rounded-2xl relative z-10 bg-black">
            <Loader2 className="h-4 w-4 animate-spin text-white" />
            <span className="text-xs font-mono uppercase tracking-widest text-white">Validating repository...</span>
          </div>
        );

      case "triggered":
      case "processing":
        return (
          <div className="p-6 border border-white/20 rounded-2xl space-y-4 relative z-10 bg-black">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest font-bold text-white">
                <Clock className="h-4 w-4 text-white animate-pulse" />
                Generating Bundle
              </div>
              <span className="text-[10px] px-2 py-1 uppercase font-mono bg-purple-600 text-white font-bold">
                {generationStatus.status === "triggered" ? "Queued" : "Indexing"}
              </span>
            </div>
            <p className="text-xs font-mono text-gray-400 truncate border-l-2 border-white/20 pl-3">{generationStatus.repository}</p>
            
            <div className="space-y-2 mt-4">
              <Progress value={progress} className="h-2 bg-white/20 rounded-full" />
              <div className="flex justify-between text-[10px] uppercase font-mono text-gray-500">
                <span>EST: {generationStatus.estimated_time || "5-10m"}</span>
                <span>{progress}%</span>
              </div>
            </div>

            {generationStatus.run_url && (
              <Button variant="link" asChild className="p-0 h-auto text-xs font-mono text-white hover:text-gray-300 mt-4 uppercase">
                <a href={generationStatus.run_url} target="_blank" rel="noopener noreferrer">
                  View Progress <ExternalLink className="ml-1 h-3 w-3" />
                </a>
              </Button>
            )}
          </div>
        );

      case "exists":
      case "ready":
        return (
          <div className="p-6 border border-white/20 rounded-2xl space-y-6 relative z-10 bg-black">
            <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest text-white">
              <CheckCircle2 className="h-5 w-5" />
              Bundle Ready
            </div>
            <p className="text-xs font-mono text-gray-400 truncate border-l-2 border-white/20 pl-3">{generationStatus.repository}</p>

            {generationStatus.bundle && (
              <div className="grid grid-cols-2 gap-4 border-t border-b border-white/10 py-4 text-[10px] text-gray-500 font-mono uppercase">
                <div>Size: <span className="text-white">{generationStatus.bundle.size}</span></div>
                <div>Commit: <span className="text-white">{generationStatus.bundle.commit?.slice(0, 7)}</span></div>
              </div>
            )}

            <div className="flex gap-3">
              <Button asChild className="flex-1 bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] rounded-xl uppercase font-bold text-xs tracking-widest h-12">
                <a href={`/explore?bundle_url=${encodeURIComponent(generationStatus.download_url)}`}>
                  Visualize
                </a>
              </Button>
              <Button variant="outline" asChild className="flex-1 rounded-xl border-white/20 hover:bg-purple-500/10 uppercase font-bold text-xs tracking-widest h-12">
                <a href={generationStatus.download_url} download>
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </a>
              </Button>
            </div>
            
            <Button
              variant="link"
              className="w-full text-center text-[10px] uppercase font-mono text-gray-500 hover:text-white h-auto p-0 mt-2"
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
          <div className="p-6 border border-red-500/30 rounded-2xl space-y-4 relative z-10 bg-black">
            <div className="flex items-center gap-2 text-xs font-mono uppercase font-bold text-red-500">
              <XCircle className="h-4 w-4" />
              Generation Failed
            </div>
            <p className="text-xs font-mono text-gray-400 leading-relaxed border-l-2 border-red-500/30 pl-3">{generationStatus.error}</p>
            <Button
              variant="outline"
              className="w-full text-xs font-bold uppercase tracking-widest text-white border-white/20 hover:bg-purple-500/10 rounded-xl mt-4 h-12"
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
    <section className="relative w-full pt-32 pb-20 md:pt-48 md:pb-32 bg-black flex flex-col items-center">
      {/* Abstract Background grid pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none" />

      <div className="relative z-10 w-full max-w-5xl mx-auto px-6 flex flex-col items-center text-center">
        
        <Badge variant="outline" className="mb-8 text-xs font-mono px-4 py-1.5 bg-transparent border-white/20 text-white uppercase tracking-widest rounded-full">
          Version {version} • MIT License
        </Badge>

        <h1 className="text-5xl md:text-7xl lg:text-8xl font-black text-white tracking-tighter leading-[1.1] mb-6 font-sans">
          THE CODEBASE <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-500 to-cyan-400">KNOWLEDGE GRAPH</span>
        </h1>

        <p className="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto mb-12 font-light">
          A powerful CLI toolkit and MCP server that instantly indexes your local code into a fully navigable graph for AI assistants.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 w-full sm:w-auto items-center justify-center mb-24">
          <MagneticButton 
            className="bg-purple-600 hover:bg-purple-500 shadow-[0_0_20px_rgba(168,85,247,0.4)] text-white hover:opacity-90 transition-all duration-300 cursor-pointer w-full sm:w-[320px] h-14 flex items-center justify-center font-bold text-sm tracking-wide rounded-full uppercase border-0"
            onClick={handleCopy}
          >
            {copied ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
            pip install codegraphcontext
          </MagneticButton>

          <Button asChild className="bg-cyan-400 hover:bg-cyan-300 text-black shadow-[0_0_20px_rgba(34,211,238,0.4)] border-0 transition-colors w-full sm:w-auto h-14 rounded-full font-bold uppercase tracking-widest text-xs px-8">
            <a href="https://github.com/CodeGraphContext/CodeGraphContext" target="_blank" rel="noopener noreferrer">
              <Github className="mr-2 h-4 w-4" />
              GitHub
            </a>
          </Button>
          <Button variant="outline" asChild className="border-cyan-400/50 hover:border-cyan-400 bg-transparent transition-colors text-cyan-50 shadow-[0_0_10px_rgba(34,211,238,0.1)] w-full sm:w-auto h-14 rounded-full font-bold uppercase tracking-widest text-xs px-8">
            <a href="https://codegraphcontext.github.io/" target="_blank" rel="noopener noreferrer">
              Docs
            </a>
          </Button>
        </div>

        {/* Indexer Widget */}
        <div className="w-full max-w-4xl border border-gray-200 dark:border-white/20 rounded-3xl bg-white dark:bg-black relative shadow-2xl shadow-black/5 dark:shadow-white/5 overflow-hidden">
          <div className="flex w-full border-b border-gray-200 dark:border-white/20 relative">
            <div className="absolute inset-0 bg-black/5 dark:bg-white/5 pointer-events-none"></div>
            <button 
              onClick={() => setActiveTab('client')} 
              className={`flex-1 py-5 text-xs font-bold uppercase tracking-widest transition-colors relative z-10 ${activeTab === 'client' ? 'bg-purple-600 text-white' : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}`}
            >
              Client Indexer
            </button>
            <button 
              onClick={() => setActiveTab('server')} 
              className={`flex-1 py-5 text-xs font-bold uppercase tracking-widest transition-colors relative z-10 ${activeTab === 'server' ? 'bg-purple-600 text-white' : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}`}
            >
              Server Indexer
            </button>
          </div>
          <div className="p-8 md:p-12 text-left bg-white dark:bg-black relative">
            {activeTab === 'client' ? (
              <LocalUploader onComplete={setGraphData} plain={true} />
            ) : (
              renderServerStatusContent()
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center justify-center gap-6 text-[10px] font-mono text-gray-500 mt-16 uppercase tracking-widest border border-white/10 rounded-full px-8 py-3 bg-black">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(168,85,247,0.8)]" />
            {stars !== null ? `${stars} Stars` : "Loading Stars"}
          </div>
          <div>•</div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse shadow-[0_0_8px_rgba(34,211,238,0.8)]" style={{ animationDelay: '0.5s' }} />
            {forks !== null ? `${forks} Forks` : "Loading Forks"}
          </div>
          <div>•</div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-cyan-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(6,182,212,0.8)]" style={{ animationDelay: '1s' }} />
            <ShowDownloads />
          </div>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;