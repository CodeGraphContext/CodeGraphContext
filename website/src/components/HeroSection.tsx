import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Github, ExternalLink, Copy, Check, Sparkles, TerminalSquare, Network } from "lucide-react";
import heroGraph from "@/assets/hero-graph.jpg";
import { useState, useEffect } from "react";
import ShowDownloads from "@/components/ShowDownloads";

import { toast } from "sonner";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

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
    <>
      
      
      <section className="relative flex items-center justify-center min-h-[95vh] pt-20 overflow-hidden">
        
        

        <motion.div
          key="hero"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="w-full h-full relative z-10"
        >
          <div className="max-w-[1400px] mx-auto px-6 lg:px-12 flex flex-col justify-center h-full">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-16 lg:gap-8 items-center">
              
              {/* LEFT COLUMN: Text Content */}
              <div className="lg:col-span-7 flex flex-col justify-center text-left mt-10 lg:mt-0" data-aos="fade-right">
                
                <div className="flex mb-8">
                  <Badge variant="outline" className="text-xs font-semibold px-3 py-1.5 border-border bg-background/50 dark:border-white/10 dark:bg-white/5 backdrop-blur-md text-foreground rounded-full shadow-sm">
                    <span className="flex h-2 w-2 rounded-full bg-primary mr-2 animate-pulse" />
                    v{version || "Loading..."} &bull; Open Source
                  </Badge>
                </div>

                <h1 className="text-5xl sm:text-6xl lg:text-[5rem] font-extrabold mb-6 leading-[1.1] tracking-tight text-foreground drop-shadow-sm">
                  Turn code into
                  <span className="block mt-2 bg-gradient-to-r from-primary via-[#A78BFA] to-accent bg-clip-text text-transparent pb-2">
                    knowledge graphs.
                  </span>
                </h1>

                <p className="text-lg md:text-xl text-muted-foreground mb-10 leading-relaxed max-w-[600px] font-medium">
                  The ultimate CLI toolkit & MCP server that parses your codebase into a structural semantic graph, supercharging your AI assistants with flawless local context.
                </p>

                {/* Primary Actions */}
                <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center mb-12">
                  <Button 
                    size="lg" 
                    className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_30px_-5px_hsl(var(--primary))] border border-primary/50 h-14 px-8 text-base rounded-full font-semibold transition-all hover:scale-[1.02]"
                    onClick={handleCopy}
                  >
                    {copied ? (
                      <Check className="mr-2 h-5 w-5" />
                    ) : (
                      <TerminalSquare className="mr-2 h-5 w-5" />
                    )}
                    pip install codegraphcontext
                  </Button>

                  <div className="flex gap-4">
                    <Button variant="outline" size="lg" asChild className="h-14 px-6 rounded-full border-border bg-background/50 hover:bg-accent/10 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10 text-foreground backdrop-blur-md transition-all font-medium">
                      <a href="https://github.com/CodeGraphContext/CodeGraphContext" target="_blank" rel="noopener noreferrer">
                        <Github className="mr-2 h-5 w-5" />
                        GitHub
                      </a>
                    </Button>
                    <Button variant="outline" size="lg" asChild className="h-14 px-6 rounded-full border-border bg-background/50 hover:bg-accent/10 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10 text-foreground backdrop-blur-md transition-all font-medium">
                      <a href="https://codegraphcontext.github.io/CodeGraphContext/" target="_blank" rel="noopener noreferrer">
                        Documentation
                      </a>
                    </Button>
                  </div>
                </div>

                {/* Stats */}
                <div className="flex flex-wrap items-center gap-6 sm:gap-10 text-sm text-muted-foreground font-semibold">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 bg-yellow-400 rounded-full shadow-[0_0_10px_rgba(250,204,21,0.5)]" />
                    <span>{typeof stars === 'number' ? stars.toLocaleString() : "..."} Stars</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 bg-blue-400 rounded-full shadow-[0_0_10px_rgba(96,165,250,0.5)]" />
                    <span>{typeof forks === 'number' ? forks.toLocaleString() : "..."} Forks</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 bg-green-400 rounded-full shadow-[0_0_10px_rgba(74,222,128,0.5)]" />
                    <span><ShowDownloads /></span>
                  </div>
                </div>
              </div>

              {/* RIGHT COLUMN: Interactive Graphic / Mockup */}
              <div className="lg:col-span-5 w-full relative perspective-[2000px]" data-aos="fade-left" data-aos-delay="200">
                {/* Floating graphic elements */}
                <div className="relative w-full aspect-square max-w-[500px] mx-auto lg:ml-auto rounded-3xl border border-border/50 dark:border-white/10 bg-card/70 dark:bg-gradient-to-b dark:from-white/5 dark:to-transparent backdrop-blur-xl shadow-2xl overflow-hidden group transform-gpu rotate-y-[-5deg] rotate-x-[5deg] hover:rotate-y-0 hover:rotate-x-0 transition-transform duration-700 ease-out">
                  
                  {/* Top bar */}
                  <div className="absolute top-0 inset-x-0 h-12 border-b border-border/50 dark:border-white/10 bg-foreground/5 dark:bg-white/5 flex items-center px-4 gap-2">
                    <div className="w-3 h-3 rounded-full bg-red-500/80" />
                    <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                    <div className="w-3 h-3 rounded-full bg-green-500/80" />
                    <div className="ml-4 text-xs font-mono text-muted-foreground flex items-center gap-2">
                      <Network className="w-3 h-3" />
                      graph_explorer.exe
                    </div>
                  </div>

                  {/* Body visualization mock */}
                  <div className="absolute top-12 inset-0 p-6 flex flex-col items-center justify-center bg-[url('https://grainy-gradients.vercel.app/noise.svg')] bg-repeat opacity-90 mix-blend-overlay pointer-events-none" />
                  
                  <div className="pt-20 pb-10 px-8 h-full flex flex-col items-center justify-center relative z-10">
                     <div className="w-24 h-24 rounded-2xl bg-gradient-to-tr from-primary/30 to-accent/30 border border-border/50 dark:border-white/20 flex items-center justify-center mb-6 shadow-[0_0_40px_rgba(139,92,246,0.3)] group-hover:scale-110 transition-transform duration-500">
                        <Network className="w-12 h-12 text-primary dark:text-white drop-shadow-md" />
                     </div>
                     <h3 className="text-2xl font-bold text-foreground mb-2 text-center">Browser Graph Explorer</h3>
                     <p className="text-center text-sm text-muted-foreground mb-8">
                       Instantly visualize the architecture of any local or GitHub repository seamlessly in a 2D physics graph. Complete privacy via WebAssembly.
                     </p>
                     
                     <Link to="/explore" className="w-full">
                       <Button className="w-full bg-foreground/5 hover:bg-foreground/10 dark:bg-white/10 dark:hover:bg-white/20 text-foreground dark:text-white rounded-xl py-6 border border-border/50 dark:border-white/10 backdrop-blur-md shadow-lg transition-all hover:shadow-[0_0_20px_rgba(255,255,255,0.1)] group-hover:-translate-y-1">
                          Launch Explorer <Sparkles className="w-4 h-4 ml-2 text-accent" />
                       </Button>
                     </Link>
                  </div>

                  {/* Decorative glowing dots representing nodes */}
                  <div className="absolute top-[30%] left-[20%] w-2 h-2 rounded-full bg-accent animate-pulse shadow-[0_0_10px_rgba(34,211,238,0.8)]" />
                  <div className="absolute top-[40%] right-[25%] w-3 h-3 rounded-full bg-primary animate-pulse shadow-[0_0_15px_rgba(139,92,246,0.8)]" style={{animationDelay: '0.5s'}} />
                  <div className="absolute bottom-[35%] left-[30%] w-2.5 h-2.5 rounded-full bg-purple-400 animate-pulse shadow-[0_0_12px_rgba(192,132,252,0.8)]" style={{animationDelay: '1s'}} />
                  
                  {/* Edges mock */}
                  <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-20" data-aos="fade-in" data-aos-delay="500">
                     <path d="M 120 180 Q 200 200 280 220" stroke="currentColor" strokeWidth="1" fill="none" className="text-accent stroke-dasharray-[5_5] animate-[dash_20s_linear_infinite]" />
                     <path d="M 280 220 Q 250 300 180 320" stroke="currentColor" strokeWidth="1" fill="none" className="text-primary stroke-dasharray-[5_5]" />
                  </svg>
                </div>
                
                {/* Backglow for the mockup box */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80%] h-[80%] bg-primary/30 blur-[100px] rounded-full z-[-1]" />
              </div>

            </div>
          </div>
        </motion.div>
      </section>
    </>
  );
};

export default HeroSection;