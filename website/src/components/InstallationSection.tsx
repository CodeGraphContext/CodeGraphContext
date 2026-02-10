import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, Check, Terminal, Play, Settings, Bot } from "lucide-react";
import { toast } from "sonner";
import ShowStarGraph from "@/components/ShowStarGraph";

const CommandBlock = ({ children }: { children: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      // Check if text starts with '$ ' and strip it for clipboard only
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
      className="relative group cursor-pointer" 
      onClick={handleCopy}
      title="Click to copy"
    >
      <pre className="bg-muted/80 px-4 py-2 pr-10 rounded font-mono text-accent shadow-inner max-w-full overflow-x-auto hover:bg-muted/90 transition-colors">
        <code className="whitespace-pre-wrap break-words">
          {children}
        </code>
      </pre>
      <div className="absolute top-2.5 right-2">
        {copied ? (
          <Check className="h-4 w-4 text-green-500" />
        ) : (
          <Copy className="h-4 w-4 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors" />
        )}
      </div>
    </div>
  );
};

const installSteps = [
  {
    step: "1",
    title: "Install",
    command: "pip install codegraphcontext",
    description: "Install CodeGraphContext using pip."
  },
  {
    step: "2",
    title: "Setup",
    command: "cgc mcp setup",
    description: "Interactive wizard to configure your IDE client."
  },
  {
    step: "3",
    title: "Start",
    command: "cgc mcp start",
    description: "Launch the MCP server and begin indexing."
  }
];

const setupOptions = [
  { icon: Terminal, title: "Docker (Recommended)", description: "Automated Neo4j setup using Docker containers.", color: "graph-node-1" },
  { icon: Play, title: "Linux Binary", description: "Direct installation on Debian-based systems.", color: "graph-node-2" },
  { icon: Settings, title: "Hosted Database", description: "Connect to Neo4j AuraDB or an existing instance.", color: "graph-node-3" }
];

const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text);
  toast.success("Copied to clipboard!");
};

const InstallationSection = () => {
  return (
    <section className="py-24 px-4 bg-muted/20">
      <div className="container mx-auto max-w-5xl text-center">
        <div className="text-center mb-6">
          <h2 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
            Get Started in Minutes
          </h2>
        </div>
        <div className="mb-12">
          <div className="text-center mb-10">
            <h3 className="text-xl text-muted-foreground max-w-3xl mx-auto">Understanding CodeGraphContext Modes</h3>
          </div>
          <div className="flex flex-col md:flex-row gap-8 mb-12">
            {[
              {
                icon: Terminal,
                title: "CLI Toolkit (Standalone)",
                description: "Index and analyze codebases directly from your terminal. Perfect for developers who want direct control via CLI commands.",
                color: "graph-node-1"
              },
              {
                icon: Bot,
                title: "MCP Server (AI-Powered)",
                description: "Connect to AI IDEs (VS Code, Cursor, Windsurf, Claude, etc.). Let AI agents query your codebase using natural language. Perfect for AI-assisted development workflows.",
                color: "graph-node-2"
              }
            ].map((mode, idx) => (
              <Card
                key={mode.title}
                className={`flex-1 flex flex-col border-border/50 hover:border-primary/30 transition-smooth group hover:shadow-glow animate-float-up dark:bg-gradient-card dark:bg-card/50 dark:border-border/30 dark:hover:border-primary/40 bg-white/95 border-gray-200/50 hover:border-primary/50 shadow-sm h-full text-left min-h-[240px]`}
                style={{ animationDelay: `${idx * 0.1}s` }}
              >
                <CardHeader className="flex-1 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-4 mb-4">
                      <div className={`p-3 rounded-xl bg-${mode.color}/10 border border-${mode.color}/20 group-hover:bg-${mode.color}/20 transition-smooth dark:bg-${mode.color}/20 dark:border-${mode.color}/30 bg-${mode.color}/5 border-${mode.color}/15`}>
                        <mode.icon className={`h-6 w-6 text-${mode.color}`} />
                      </div>
                      <CardTitle className="text-xl font-semibold dark:text-foreground text-gray-900">{mode.title}</CardTitle>
                    </div>
                    <CardDescription className="text-base text-muted-foreground leading-relaxed dark:text-muted-foreground text-gray-600">
                      {mode.description}
                    </CardDescription>
                  </div>
                </CardHeader>
              </Card>
            ))}
          </div>


          <Card className="mb-10">
            <CardHeader>
              <CardTitle className="text-xl font-semibold">Installation (Both Modes)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex justify-center mb-2">
                <CommandBlock>$ pip install codegraphcontext</CommandBlock>


              </div>
            </CardContent>
          </Card>

          <Card className="mb-4">
            <CardHeader>
              <div className="flex items-center gap-3 mb-1">
                <Settings className="h-6 w-6 text-primary" />
                <CardTitle className="text-2xl font-bold">Database Setup Options</CardTitle>
              </div>
              <CardDescription className="text-base text-muted-foreground">
                FalkorDB Lite is default (Unix). For Neo4j, the wizard supports multiple configurations:
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-3 gap-6">
                {[
                  {
                    icon: Terminal,
                    title: "Docker (Recommended)",
                    description: "Automated Neo4j setup using Docker containers.",
                    color: "graph-node-1"
                  },
                  {
                    icon: Play,
                    title: "Linux Binary",
                    description: "Direct installation on Debian-based systems.",
                    color: "graph-node-2"
                  },
                  {
                    icon: Settings,
                    title: "Hosted Database",
                    description: "Connect to Neo4j AuraDB or an existing instance.",
                    color: "graph-node-3"
                  }
                ].map((option, idx) => (
                  <div key={option.title} className="text-center p-4 rounded-lg bg-muted/30">
                    <div className={`w-12 h-12 bg-${option.color}/10 rounded-lg flex items-center justify-center mx-auto mb-3`}>
                      <option.icon className={`h-6 w-6 text-${option.color}`} />
                    </div>
                    <h4 className="font-semibold mb-2 text-lg">{option.title}</h4>
                    <p className="text-sm text-muted-foreground">{option.description}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="w-full my-10">
            <div className="h-1 w-full rounded-full bg-gradient-to-r from-primary via-blue-500 to-green-400 opacity-80" />
          </div>


        </div>
        <div className="mb-12">
          <div className="text-center mb-10">
            <h3 className="text-xl text-muted-foreground max-w-3xl mx-auto">For CLI Toolkit Mode</h3>
          </div>
          <Card className="mb-4">
            <CardHeader>
              <div className="flex items-center gap-3 mb-1">
                <Terminal className="h-6 w-6 text-primary" />
                <CardTitle className="text-2xl font-bold">Start using immediately with CLI commands:</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-4">
                {/* Card 1 */}
                <Card className="bg-muted/40">
                  <CardHeader>
                    <CardTitle className="text-base font-semibold text-left">Index your current directory</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CommandBlock>cgc index .</CommandBlock>

                  </CardContent>
                </Card>
                {/* Card 2 */}
                <Card className="bg-muted/40">
                  <CardHeader>
                    <CardTitle className="text-base font-semibold text-left">List all indexed repositories</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CommandBlock>cgc list</CommandBlock>

                  </CardContent>
                </Card>
                {/* Card 3 */}
                <Card className="bg-muted/40">
                  <CardHeader>
                    <CardTitle className="text-base font-semibold text-left">See all commands</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CommandBlock>cgc help</CommandBlock>

                  </CardContent>
                </Card>
              </div>
            </CardContent>
            <div className="mt-4 text-left max-w-lg ml-8 mb-8">
              <span className="font-semibold text-muted-foreground">Ex:</span>
              <CommandBlock>cgc analyze callers my_function</CommandBlock>

            </div>

            <div className="mt-3 mb-6">


              <a href="https://codegraphcontext.github.io/CodeGraphContext/cli/" target="_blank" rel="noopener noreferrer" className="underline text-primary font-medium">
                See the full CLI Commands Guide for all available commands and usage scenarios.
              </a>
            </div>
          </Card>


        </div>

        <div className="w-full my-10">
          <div className="h-1 w-full rounded-full bg-gradient-to-r from-primary via-blue-500 to-green-400 opacity-80" />
        </div>

        <div>
          <div className="mb-12">
            <div className="text-center mb-10">
              <h3 className="text-xl text-muted-foreground max-w-3xl mx-auto">For MCP Server Mode</h3>
            </div>
            <Card className="mb-4">
              <CardHeader>
                <div className="flex items-center gap-3 mb-1">
                  <Bot className="h-6 w-6 text-primary" />
                  <CardTitle className="text-2xl font-bold">Configure your AI assistant to use CodeGraphContext:</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col gap-4">
                  {/* Card 1 */}
                  <Card className="bg-muted/40">
                    <CardHeader>
                      <CardTitle className="text-base font-semibold text-left"> Run the MCP setup wizard to configure:</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <CommandBlock>cgc mcp setup</CommandBlock>


                    </CardContent>
                  </Card>

                  {/* Card 2 */}
                  <Card className="bg-muted/40">
                    <CardHeader>
                      <CardTitle className="text-base font-semibold text-left">Launch the MCP server:</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <CommandBlock>cgc mcp start</CommandBlock>

                    </CardContent>
                  </Card>
                </div>
              </CardContent>
              <div className="mt-3 mb-6">
                <a href="https://codegraphcontext.github.io/CodeGraphContext/cookbook/" target="_blank" rel="noopener noreferrer" className="underline text-primary font-medium">
                  Now interact with your codebase through your AI assistant using natural language! See full cookbook.
                </a>
              </div>
            </Card>

          </div>
        </div>

      </div>
    </section>
  );
};

export default InstallationSection;