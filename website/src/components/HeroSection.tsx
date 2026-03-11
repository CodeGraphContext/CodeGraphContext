import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Github, ExternalLink, Copy, Check } from "lucide-react";
import heroGraph from "@/assets/hero-graph.jpg";
import { useState, useEffect } from "react";
import ShowDownloads from "@/components/ShowDownloads";
import ShowStarGraph from "@/components/ShowStarGraph";
import { ThemeToggle } from "@/components/ThemeToggle";
import { toast } from "sonner";
import { UploadCloud, Globe, Link, Lock, Box } from "lucide-react";
import { useNavigate } from "react-router-dom";

const OUTLINE_BUTTON_CLASSES = "border-gray-300 hover:border-primary/60 bg-white/80 backdrop-blur-sm shadow-sm transition-smooth text-gray-900 dark:bg-transparent dark:text-foreground dark:border-primary/30 w-full sm:w-auto";

const HeroSection = () => {
  const navigate = useNavigate();
  const [stars, setStars] = useState(null);
  const [forks, setForks] = useState(null);
  const [version, setVersion] = useState("");
  const [copied, setCopied] = useState(false);
  const [isRemoteMode, setIsRemoteMode] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [repoUrl, setRepoUrl] = useState("");
  const [repoToken, setRepoToken] = useState("");

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

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden overflow-y-hidden">
      {/* Header with Theme Toggle */}
      <div className="absolute top-0 left-0 right-0 z-20 p-4" data-aos="fade-down">
        <div className="container mx-auto flex justify-end">
          <div className="rounded-full bg-white/60 backdrop-blur-md border border-gray-200 shadow-sm p-2 dark:bg-transparent dark:border-transparent dark:shadow-none">
            <ThemeToggle />
          </div>
        </div>
      </div>

      {/* Background Image */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat opacity-20 brightness-110 saturate-110 dark:opacity-30 dark:brightness-100 dark:saturate-100"
        style={{ backgroundImage: `url(${heroGraph})` }}
      />

      {/* Gradient Overlay */}
      <div className="absolute inset-0 bg-gradient-to-b from-white/60 via-white/40 to-white/80 dark:from-background/90 dark:via-background/80 dark:to-background/90" />

      {/* Content */}
      <div className="relative z-10 container mx-auto px-4 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 overflow-hidden">
          
          {/* Left Side: Playground Onboarding */}
          <div className="order-2 lg:order-1" data-aos="fade-right">
            <div 
              className={`
                relative group flex flex-col items-center justify-center w-full max-w-xl mx-auto min-h-[450px]
                border-2 border-dashed rounded-[2.5rem] overflow-hidden cursor-pointer
                transition-all duration-500 hover:scale-[1.015] backdrop-blur-md shadow-2xl
                ${isDragging
                  ? 'border-purple-500/60 bg-purple-500/10 shadow-glow-soft scale-[1.015]'
                  : 'border-white/10 bg-black/40 hover:border-purple-500/40 hover:bg-purple-500/5'}
              `}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => { 
                e.preventDefault(); 
                setIsDragging(false);
                toast.info("Moving to Playground to process your code...");
                setTimeout(() => navigate("/playground?action=select-local", { replace: true }), 100); 
              }}
              onClick={() => {
                if (!isRemoteMode) {
                  toast.info("Select a directory and we'll move to the playground!");
                  setTimeout(() => navigate("/playground?action=select-local", { replace: true }), 100);
                }
              }}
            >
              {/* Orb */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 bg-purple-600 blur-[120px] opacity-10 pointer-events-none group-hover:opacity-25 transition-opacity duration-700" />

              <div className="relative z-10 flex flex-col items-center p-8 text-center gap-5 w-full h-full justify-center">
                <div className="flex bg-white/5 p-1 rounded-xl border border-white/10 mb-4 backdrop-blur-xl">
                  <button 
                    onClick={(e) => { e.stopPropagation(); setIsRemoteMode(false); }}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${!isRemoteMode ? 'bg-purple-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
                  >
                    <UploadCloud className="w-3.5 h-3.5" />
                    Local Repo
                  </button>
                  <button 
                    onClick={(e) => { e.stopPropagation(); setIsRemoteMode(true); }}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${isRemoteMode ? 'bg-purple-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
                  >
                    <Globe className="w-3.5 h-3.5" />
                    Remote Repo
                  </button>
                </div>

                {!isRemoteMode ? (
                  <>
                    <div className="w-20 h-20 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center shadow-xl group-hover:scale-110 group-hover:border-purple-500/50 transition-all duration-300">
                      <UploadCloud className="w-10 h-10 text-gray-500 group-hover:text-purple-400 transition-colors duration-300" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-semibold text-white tracking-tight">Visualize your Codebase</h2>
                      <p className="text-gray-400 mt-2 max-w-xs mx-auto text-sm leading-relaxed">
                        Drop a repository to extract AST relationships entirely client-side.
                      </p>
                    </div>
                    <Button variant="outline" className="px-8 py-6 bg-white/5 border-white/10 hover:border-purple-500 rounded-2xl font-medium transition-all duration-300 group-hover:bg-purple-600 group-hover:text-white">
                      Select Local Directory
                    </Button>
                  </>
                ) : (
                  <div className="w-full max-w-xs flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="text-left">
                      <label className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5 block">Repository URL</label>
                      <div className="flex items-center gap-2.5 px-4 py-3 bg-white/5 border border-white/10 rounded-xl focus-within:border-purple-500 transition-all">
                        <Link className="w-4 h-4 text-gray-400" />
                        <input 
                          type="text"
                          placeholder="github.com/owner/repo"
                          value={repoUrl}
                          onChange={(e) => setRepoUrl(e.target.value)}
                          className="bg-transparent border-none outline-none text-sm text-white w-full"
                        />
                      </div>
                    </div>
                    <div className="text-left">
                      <label className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5 block">Access Token (Optional)</label>
                      <div className="flex items-center gap-2.5 px-4 py-3 bg-white/5 border border-white/10 rounded-xl focus-within:border-purple-500 transition-all">
                        <Lock className="w-4 h-4 text-gray-400" />
                        <input 
                          type="password"
                          placeholder="ghp_xxxxxx"
                          value={repoToken}
                          onChange={(e) => setRepoToken(e.target.value)}
                          className="bg-transparent border-none outline-none text-sm text-white w-full"
                        />
                      </div>
                    </div>
                    <Button 
                      className="mt-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl shadow-glow transition-all"
                      onClick={() => {
                        const params = new URLSearchParams();
                        params.set('repo', repoUrl);
                        if (repoToken) params.set('token', repoToken);
                        navigate(`/playground?${params.toString()}`);
                      }}
                    >
                      Fetch & Visualize
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Side: Hero Text */}
          <div className="order-1 lg:order-2 text-left" data-aos="fade-left">
            <Badge variant="secondary" className="mb-6 mt-4 text-sm font-medium border-purple-500/20 bg-purple-500/10 text-purple-400">
              <div className="w-2 h-2 bg-purple-500 rounded-full mr-2 animate-pulse" />
              Version {version} • MIT License
            </Badge>

            <h1
              className="text-3xl xs:text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-white to-purple-400 bg-clip-text text-transparent leading-tight tracking-tight break-words whitespace-normal max-w-full overflow-hidden"
              style={{ wordBreak: 'break-word' }}
            >
              CodeGraphContext
            </h1>

            <p className="text-xl md:text-2xl text-gray-400 mb-4 leading-relaxed max-w-xl">
              A powerful CLI toolkit &amp; MCP server that indexes local code into a 
              <span className="text-purple-400 font-semibold block sm:inline ml-0 sm:ml-2">knowledge graph for AI assistants</span>
            </p>

            <div className="flex flex-col sm:flex-row gap-4 mt-10">
              <Button 
                size="lg" 
                className="bg-purple-600 hover:bg-purple-500 text-white shadow-glow ring-1 ring-purple-400/20"
                onClick={handleCopy}
              >
                {copied ? <Check className="mr-2 h-5 w-5" /> : <Copy className="mr-2 h-5 w-5" />}
                pip install codegraphcontext
              </Button>

              <Button variant="outline" size="lg" asChild className="border-white/10 bg-white/5 hover:bg-white/10">
                <a href="https://github.com/CodeGraphContext/CodeGraphContext" target="_blank" rel="noopener noreferrer">
                  <Github className="mr-2 h-5 w-5" />
                  GitHub
                </a>
              </Button>
            </div>

            {/* Stats */}
            <div className="flex flex-wrap gap-8 mt-12 text-sm text-gray-500 font-medium">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-purple-500 rounded-full" />
                <span>{stars ? `${stars} Stars` : "500+ Stars"}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full" />
                <span>{forks ? `${forks} Forks` : "50+ Forks"}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full" />
                <span><ShowDownloads /></span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Graph Nodes */}
      <div className="absolute top-20 left-10 w-8 h-8 graph-node animate-graph-pulse" style={{ animationDelay: '0.2s' }} />
      <div className="absolute top-40 right-20 w-6 h-6 graph-node animate-graph-pulse" style={{ animationDelay: '0.8s' }} />
      <div className="absolute bottom-32 left-20 w-10 h-10 graph-node animate-graph-pulse" style={{ animationDelay: '1.2s' }} />
      <div className="absolute bottom-20 right-10 w-7 h-7 graph-node animate-graph-pulse" style={{ animationDelay: '0.6s' }} />
    </section>
  );
};

export default HeroSection;