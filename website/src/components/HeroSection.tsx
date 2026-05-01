import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Github, ExternalLink, Copy, Check, Sparkles, FolderUp } from "lucide-react";
import heroGraph from "@/assets/hero-graph.jpg";
import { useState, useEffect } from "react";
import ShowDownloads from "@/components/ShowDownloads";
import { ThemeToggle } from "@/components/ThemeToggle";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

const OUTLINE_BUTTON_CLASSES = "border-gray-300 hover:border-primary/60 bg-white/80 backdrop-blur-sm shadow-sm transition-smooth text-gray-900 dark:bg-transparent dark:text-foreground dark:border-primary/30 w-full sm:w-auto";

const HeroSection = () => {
  const [stars, setStars] = useState<number | null>(null);
  const [forks, setForks] = useState<number | null>(null);
  const [version, setVersion] = useState("");
  const [copied, setCopied] = useState(false);

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
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <motion.div
        key="hero"
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.4 }}
        className="absolute inset-0 w-full h-full"
      >
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

        {/* Content (2-Column Grid) */}
        <div className="relative z-10 w-full h-full max-w-7xl mx-auto px-6 pt-32 pb-20 flex flex-col justify-center">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
            
            {/* LEFT COLUMN: Explore CTA instead of LocalUploader */}
            <div className="lg:col-span-5 w-full flex justify-center lg:justify-end animate-float-up" data-aos="fade-right">
              <div className="w-full max-w-md p-8 border border-white/10 dark:border-white/20 rounded-[2rem] bg-black/40 backdrop-blur-xl shadow-2xl relative overflow-hidden flex flex-col items-center text-center">
                <div className="bg-gradient-to-br from-purple-500/20 to-indigo-500/20 p-5 rounded-full mb-6 border border-purple-500/30">
                  <FolderUp className="w-10 h-10 text-purple-400" />
                </div>
                <h3 className="text-2xl font-bold mb-3 text-white">Browser Graph Explorer</h3>
                <p className="text-gray-400 text-sm mb-6 max-w-[280px]">
                  Instantly visualize the architecture of any local or GitHub repository seamlessly in a 2D physics graph. Complete privacy via WebAssembly.
                </p>
                <Link to="/explore">
                  <Button className="bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white rounded-full px-10 py-6 text-lg w-full max-w-[280px] shadow-[0_0_20px_rgba(59,130,246,0.3)] border-none transition-all duration-300 hover:scale-105">
                    Launch Explorer <Sparkles className="w-5 h-5 ml-2" />
                  </Button>
                </Link>
                {/* Decorative Blob */}
                <div className="absolute -bottom-32 -right-32 w-80 h-80 bg-purple-600/15 blur-3xl rounded-full z-0 pointer-events-none"></div>
              </div>
            </div>

            {/* RIGHT COLUMN: Value Proposition & Commands */}
            <div className="lg:col-span-7 flex flex-col justify-center text-left" data-aos="fade-left">
              <div className="flex mb-6">
                <Badge variant="secondary" className="text-sm font-medium px-4 py-1.5 shadow-sm bg-white/50 backdrop-blur dark:bg-white/10">
                  <div className="w-2.5 h-2.5 bg-accent rounded-full mr-2.5 animate-graph-pulse" />
                  Version {version} &bull; MIT License
                </Badge>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold mb-6 bg-gradient-to-r from-purple-700 via-indigo-700 to-purple-900 dark:bg-gradient-primary bg-clip-text py-2 text-transparent leading-tight tracking-tight drop-shadow-[0_2px_8px_rgba(0,0,0,0.15)]">
                CodeGraphContext
              </h1>

              <p className="text-xl md:text-2xl text-muted-foreground mb-3 leading-relaxed max-w-2xl">
                A powerful CLI toolkit &amp; MCP server that indexes local code into a
              </p>
              <p className="text-xl md:text-2xl text-accent font-semibold mb-10">
                knowledge graph for AI assistants
              </p>

              <div className="flex flex-col sm:flex-row gap-4 items-start mb-12">
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
                    <a href="https://codegraphcontext.github.io/CodeGraphContext/" target="_blank" rel="noopener noreferrer">
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