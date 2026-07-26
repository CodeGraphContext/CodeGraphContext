import { useState } from "react";
import { Copy, Check, Terminal, Play, Settings, Bot, ChevronDown, ChevronUp } from "lucide-react";
import { toast } from "sonner";
import GlassCard from "./GlassCard";
import SectionDivider from "./SectionDivider";
import MagneticButton from "./MagneticButton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

const CommandBlock = ({ children }: { children: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      const textToCopy = children.startsWith("$ ") ? children.slice(2) : children;
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      toast.success("Copied to clipboard!");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      toast.error("Failed to copy");
    }
  };

  return (
    <div 
      className="relative group cursor-pointer w-full" 
      onClick={handleCopy}
      title="Click to copy"
    >
      <div className="bg-[#1e1e1e] rounded-xl overflow-hidden border border-white/10 shadow-lg">
        {/* Terminal Header */}
        <div className="bg-[#2d2d2d] px-4 py-2 flex items-center border-b border-white/5">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-[#ff5f56]"></div>
            <div className="w-3 h-3 rounded-full bg-[#ffbd2e]"></div>
            <div className="w-3 h-3 rounded-full bg-[#27c93f]"></div>
          </div>
          <div className="mx-auto text-[10px] text-gray-400 font-mono">bash</div>
        </div>
        {/* Terminal Body */}
        <pre className="px-5 py-4 font-mono text-sm sm:text-base text-gray-200 overflow-x-auto relative">
          <code className="whitespace-pre-wrap break-words">
            <span className="text-primary mr-2">$</span>
            {children.startsWith("$ ") ? children.slice(2) : children}
          </code>
          <div className="absolute top-4 right-4 bg-[#1e1e1e] pl-2">
            {copied ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <Copy className="h-4 w-4 text-gray-500 group-hover:text-gray-300 transition-colors" />
            )}
          </div>
        </pre>
      </div>
    </div>
  );
};

const setupOptions = [
  { icon: Terminal, title: "Docker (Recommended)", description: "Automated Neo4j setup using Docker containers." },
  { icon: Play, title: "Linux Binary", description: "Direct installation on Debian-based systems." },
  { icon: Settings, title: "Hosted Database", description: "Connect to Neo4j AuraDB or an existing instance." }
];

const InstallationSection = () => {
  const [dbOpen, setDbOpen] = useState(false);

  return (
    <section className="py-24 px-4 relative z-10">
      <SectionDivider variant="wave" className="absolute top-0 left-0 right-0 z-0 opacity-40" />
      
      <div className="container mx-auto max-w-5xl relative z-10">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-black mb-6 uppercase tracking-tight text-white py-2">
            Get Started in Minutes
          </h2>
          <p className="text-sm font-mono text-gray-500 uppercase tracking-widest max-w-2xl mx-auto">
            Install CodeGraphContext globally and configure it for your workflow.
          </p>
        </div>
        
        {/* Universal Installation Step */}
        <div className="mb-16">
          <GlassCard glowColor="none" className="p-8 md:p-10 text-center relative overflow-visible">
            <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-white p-[1px] rounded-full">
              <div className="bg-background rounded-full w-12 h-12 flex items-center justify-center text-xl font-bold text-white">1</div>
            </div>
            
            <h3 className="text-lg font-black uppercase tracking-widest text-white mb-4 mt-4">Global Installation</h3>
            <p className="text-xs font-mono text-gray-400 mb-8 max-w-xl mx-auto uppercase tracking-wide">
              Install the package globally via pip to access the <code className="bg-purple-600 text-white px-1.5 py-0.5 rounded text-xs font-bold">cgc</code> command everywhere.
            </p>
            
            <div className="max-w-2xl mx-auto">
              <CommandBlock>$ pip install codegraphcontext</CommandBlock>
            </div>
          </GlassCard>
        </div>

        {/* Database Setup (Collapsible) */}
        <div className="mb-16 max-w-4xl mx-auto">
          <Collapsible open={dbOpen} onOpenChange={setDbOpen}>
            <GlassCard hoverable={false} className="p-6 transition-all duration-300">
              <CollapsibleTrigger className="w-full flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-2.5 rounded-full bg-purple-600 text-white">
                    <Settings className="w-5 h-5" />
                  </div>
                  <div className="text-left">
                    <h4 className="text-sm font-black uppercase tracking-widest text-white">Database Setup Options</h4>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-gray-500 hidden sm:block">FalkorDB Lite is default (Unix). Click to view Neo4j options.</p>
                  </div>
                </div>
                {dbOpen ? <ChevronUp className="w-5 h-5 text-muted-foreground" /> : <ChevronDown className="w-5 h-5 text-muted-foreground" />}
              </CollapsibleTrigger>
              
              <CollapsibleContent className="pt-6 animate-in slide-in-from-top-2">
                <div className="grid md:grid-cols-3 gap-4">
                  {setupOptions.map((option, idx) => (
                    <div key={option.title} className="text-center p-5 rounded-3xl bg-white/5 border border-white/10 hover:bg-purple-500/20 transition-colors">
                      <div className={`w-12 h-12 bg-purple-600 text-white rounded-full flex items-center justify-center mx-auto mb-4`}>
                        <option.icon className={`h-5 w-5`} />
                      </div>
                      <h4 className="font-black text-xs uppercase tracking-widest text-white mb-2">{option.title}</h4>
                      <p className="text-[10px] font-mono uppercase tracking-widest text-gray-500">{option.description}</p>
                    </div>
                  ))}
                </div>
              </CollapsibleContent>
            </GlassCard>
          </Collapsible>
        </div>

        {/* Mode Selection Tabs */}
        <div className="mb-12">
          <GlassCard glowColor="none" className="p-6 md:p-8">
            <h3 className="text-lg font-black uppercase tracking-widest text-white mb-6 text-center">Choose Your Mode</h3>
            
            <Tabs defaultValue="mcp" className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-8 bg-white/5 border border-white/10 p-1.5 rounded-full h-auto">
                <TabsTrigger value="cli" className="rounded-full py-3 data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-all">
                  <div className="flex flex-col sm:flex-row items-center gap-2">
                    <Terminal className="w-4 h-4" />
                    <span className="font-black text-xs uppercase tracking-widest">CLI Toolkit</span>
                  </div>
                </TabsTrigger>
                <TabsTrigger value="mcp" className="rounded-full py-3 data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-all">
                  <div className="flex flex-col sm:flex-row items-center gap-2">
                    <Bot className="w-4 h-4" />
                    <span className="font-black text-xs uppercase tracking-widest">MCP Server</span>
                  </div>
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="cli" className="animate-in fade-in zoom-in-95 duration-300">
                <div className="text-center mb-8">
                  <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest max-w-2xl mx-auto">
                    Index and analyze codebases directly from your terminal. Perfect for developers who want direct control via CLI commands.
                  </p>
                </div>
                
                <div className="grid sm:grid-cols-2 gap-6 max-w-3xl mx-auto mb-8">
                  <div className="space-y-3">
                    <div className="text-[10px] font-black text-white uppercase tracking-widest">Index current directory</div>
                    <CommandBlock>$ cgc index .</CommandBlock>
                  </div>
                  <div className="space-y-3">
                    <div className="text-[10px] font-black text-white uppercase tracking-widest">List indexed repos</div>
                    <CommandBlock>$ cgc list</CommandBlock>
                  </div>
                  <div className="space-y-3 sm:col-span-2">
                    <div className="text-[10px] font-black text-white uppercase tracking-widest">Analyze dependencies</div>
                    <CommandBlock>$ cgc analyze callers my_function</CommandBlock>
                  </div>
                </div>
                
                <div className="text-center">
                  <a href="https://codegraphcontext.github.io/cli/" target="_blank" rel="noopener noreferrer">
                    <MagneticButton className="bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] rounded-full px-8 py-3 border border-white/10 font-black text-xs uppercase tracking-widest transition-colors">
                      View Full CLI Guide
                    </MagneticButton>
                  </a>
                </div>
              </TabsContent>
              
              <TabsContent value="mcp" className="animate-in fade-in zoom-in-95 duration-300">
                <div className="text-center mb-8">
                  <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest max-w-2xl mx-auto">
                    Connect to AI IDEs (VS Code, Cursor, Windsurf, Claude). Let AI agents query your codebase using natural language.
                  </p>
                </div>
                
                <div className="relative max-w-3xl mx-auto">
                  {/* Stepper vertical line */}
                  <div className="absolute left-6 top-8 bottom-8 w-0.5 bg-white/20 hidden sm:block"></div>
                  
                  <div className="space-y-8">
                    <div className="flex gap-6 relative">
                      <div className="hidden sm:flex w-12 h-12 rounded-full bg-background border-2 border-white items-center justify-center z-10 shrink-0 font-bold text-white">
                        2
                      </div>
                      <div className="flex-1 space-y-3">
                        <h4 className="text-xs font-black uppercase tracking-widest text-white flex items-center gap-3">
                          <span className="sm:hidden w-6 h-6 rounded-full bg-purple-600 text-white flex items-center justify-center text-[10px]">2</span>
                          Run Setup Wizard
                        </h4>
                        <CommandBlock>$ cgc mcp setup</CommandBlock>
                        <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">Configures your preferred IDE (Cursor, VS Code, etc.) with the correct paths.</p>
                      </div>
                    </div>
                    
                    <div className="flex gap-6 relative">
                      <div className="hidden sm:flex w-12 h-12 rounded-full bg-background border-2 border-white items-center justify-center z-10 shrink-0 font-bold text-white">
                        3
                      </div>
                      <div className="flex-1 space-y-3">
                        <h4 className="text-xs font-black uppercase tracking-widest text-white flex items-center gap-3">
                          <span className="sm:hidden w-6 h-6 rounded-full bg-purple-600 text-white flex items-center justify-center text-[10px]">3</span>
                          Start Server
                        </h4>
                        <CommandBlock>$ cgc mcp start</CommandBlock>
                        <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">Launches the background server. Your AI assistant is now ready to query the graph!</p>
                      </div>
                    </div>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </GlassCard>
        </div>

      </div>
    </section>
  );
};

export default InstallationSection;