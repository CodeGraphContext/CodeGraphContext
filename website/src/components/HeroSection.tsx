import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Github, ExternalLink, Copy, Check } from "lucide-react";
import heroGraph from "@/assets/hero-graph.jpg";
import { useState, useEffect } from "react";
import ShowDownloads from "@/components/ShowDownloads";
import ShowStarGraph from "@/components/ShowStarGraph";
import { ThemeToggle } from "@/components/ThemeToggle";
import { toast } from "sonner";

const HeroSection = () => {
  const [stars, setStars] = useState(null);
  const [forks, setForks] = useState(null);
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
      <div className="relative z-10 container mx-auto px-4 text-center max-w-5xl">
        <div className="animate-float-up" data-aos="fade-up">
          <Badge variant="secondary" className="mb-6 text-sm font-medium">
            <div className="w-2 h-2 bg-accent rounded-full mr-2 animate-graph-pulse" />
            Version {version} • MIT License
          </Badge>

          <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl xl:text-7xl font-bold mb-6 bg-gradient-to-r from-purple-700 via-indigo-700 to-purple-900 dark:bg-gradient-primary bg-clip-text py-2 text-transparent leading-tight tracking-tight drop-shadow-[0_2px_8px_rgba(0,0,0,0.15)]">
            CodeGraphContext
          </h1>

          <p className="text-xl md:text-2xl text-muted-foreground mb-4 leading-relaxed">
            A powerful CLI toolkit &amp; MCP server that indexes local code into a
          </p>
          <p className="text-xl md:text-2xl text-accent font-semibold mb-8">
            knowledge graph for AI assistants
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-12" data-aos="fade-up" data-aos-delay="200">
            <Button 
              size="lg" 
              className="bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-800 text-primary-foreground hover:opacity-90 transition-all duration-300 shadow-glow ring-1 ring-primary/20 dark:bg-gradient-primary cursor-pointer w-full sm:w-auto min-w-[280px]"
              onClick={handleCopy}
              title="Click to copy install command"
            >
              {copied ? (
                <Check className="mr-2 h-5 w-5 animate-in zoom-in duration-300" />
              ) : (
                <Copy className="mr-2 h-5 w-5" />
              )}
              pip install codegraphcontext
            </Button>

            <Button variant="outline" size="lg" asChild className="border-gray-300 hover:border-primary/60 bg-white/80 backdrop-blur-sm shadow-sm transition-smooth text-gray-900 dark:bg-transparent dark:text-foreground dark:border-primary/30 w-full sm:w-auto">
              <a href="https://github.com/CodeGraphContext/CodeGraphContext" target="_blank" rel="noopener noreferrer">
                <Github className="mr-2 h-5 w-5" />
                View on GitHub
                <ExternalLink className="ml-2 h-4 w-4" />
              </a>
            </Button>
            <Button variant="ghost" size="lg" asChild className="w-full sm:w-auto">
              <a href="https://codegraphcontext.github.io/CodeGraphContext/" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 justify-center">
                <ExternalLink className="h-5 w-5" />
                Documentation
              </a>
            </Button>
          </div>

          {/* Stats */}
          <div className="flex flex-wrap justify-center gap-8 text-sm text-muted-foreground" data-aos="fade-up" data-aos-delay="400">
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

      {/* Floating Graph Nodes */}
      <div className="absolute top-20 left-10 w-8 h-8 graph-node animate-graph-pulse" style={{ animationDelay: '0.2s' }} />
      <div className="absolute top-40 right-20 w-6 h-6 graph-node animate-graph-pulse" style={{ animationDelay: '0.8s' }} />
      <div className="absolute bottom-32 left-20 w-10 h-10 graph-node animate-graph-pulse" style={{ animationDelay: '1.2s' }} />
      <div className="absolute bottom-20 right-10 w-7 h-7 graph-node animate-graph-pulse" style={{ animationDelay: '0.6s' }} />
    </section>
  );
};

export default HeroSection;