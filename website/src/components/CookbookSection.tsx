import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { ChevronDown, Copy, Terminal, Search, Code, Database, BookOpen, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import GlassCard from "./GlassCard";
import SectionDivider from "./SectionDivider";

const CookbookSection = () => {
  const { toast } = useToast();
  const [openItems, setOpenItems] = useState<Set<string>>(new Set());

  const toggleItem = (id: string) => {
    const newOpenItems = new Set(openItems);
    if (newOpenItems.has(id)) {
      newOpenItems.delete(id);
    } else {
      newOpenItems.add(id);
    }
    setOpenItems(newOpenItems);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copied to clipboard!",
      description: "The code snippet has been copied to your clipboard.",
    });
  };

  const basicExamples = [
    {
      id: "find-function",
      title: "Find all definitions of a function",
      description: "Find all definitions of the 'helper' function.",
      tool: "analyze_code_relationships",
      args: `{
    "query_type": "find_definitions",
    "target": "helper"
}`
    },
    {
      id: "find-callers",
      title: "Find all calls to a specific function",
      description: "Find all calls to the 'helper' function.",
      tool: "analyze_code_relationships",
      args: `{
    "query_type": "find_callers",
    "target": "helper"
}`
    },
    {
      id: "find-callees",
      title: "Find what a function calls",
      description: "What functions are called inside the 'foo' function?",
      tool: "analyze_code_relationships",
      args: `{
    "query_type": "find_callees",
    "target": "foo",
    "context": "/path/to/your/project/module_a.py"
}`
    },
    {
      id: "find-imports",
      title: "Find all imports of a module",
      description: "Where is the 'math' module imported?",
      tool: "analyze_code_relationships",
      args: `{
    "query_type": "find_importers",
    "target": "math"
}`
    }
  ];

  const analysisExamples = [
    {
      id: "complex-functions",
      title: "Find the most complex functions",
      description: "Find the 5 most complex functions in your codebase.",
      tool: "find_most_complex_functions",
      args: `{
    "limit": 5
}`
    },
    {
      id: "cyclomatic-complexity",
      title: "Calculate cyclomatic complexity",
      description: "What is the cyclomatic complexity of 'try_except_finally'?",
      tool: "calculate_cyclomatic_complexity",
      args: `{
    "function_name": "try_except_finally"
}`
    },
    {
      id: "dead-code",
      title: "Find unused code",
      description: "Find unused code, but ignore API endpoints.",
      tool: "find_dead_code",
      args: `{
    "exclude_decorated_with": ["@app.route"]
}`
    },
    {
      id: "call-chain",
      title: "Find call chain between functions",
      description: "What is the call chain from 'wrapper' to 'helper'?",
      tool: "analyze_code_relationships",
      args: `{
    "query_type": "call_chain",
    "target": "wrapper->helper"
}`
    }
  ];

  const cypherExamples = [
    {
      id: "all-functions",
      title: "Find all function definitions",
      description: "Find all function definitions in the codebase.",
      tool: "execute_cypher_query",
      args: `{
    "cypher_query": "MATCH (n:Function) RETURN n.name, n.path, n.line_number LIMIT 50"
}`
    },
    {
      id: "all-classes",
      title: "Find all classes",
      description: "Show me all the classes in the codebase.",
      tool: "execute_cypher_query",
      args: `{
    "cypher_query": "MATCH (n:Class) RETURN n.name, n.path, n.line_number LIMIT 50"
}`
    },
    {
      id: "dataclasses",
      title: "Find all dataclasses",
      description: "Find all dataclasses in the codebase.",
      tool: "execute_cypher_query",
      args: `{
    "cypher_query": "MATCH (c:Class) WHERE 'dataclass' IN c.decorators RETURN c.name, c.path"
}`
    },
    {
      id: "circular-imports",
      title: "Find circular file imports",
      description: "Are there any circular dependencies between files?",
      tool: "execute_cypher_query",
      args: `{
    "cypher_query": "MATCH path = (f1:File)-[:IMPORTS*2..]->(f1) RETURN path LIMIT 10"
}`
    }
  ];

  const ExampleCard = ({
    example,
    isOpen,
    onToggle,
  }: {
    example: any;
    isOpen: boolean;
    onToggle: () => void;
  }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = (e: React.MouseEvent, text: string) => {
      e.stopPropagation(); // prevent collapsing when copying
      navigator.clipboard.writeText(text);
      setCopied(true);
      toast({
        title: "Copied to clipboard!",
        description: "The code snippet has been copied to your clipboard.",
      });
      setTimeout(() => setCopied(false), 2000);
    };

    return (
      <div>
        <Collapsible open={isOpen} onOpenChange={onToggle}>
          <CollapsibleTrigger asChild>
            <div className="cursor-pointer">
              <GlassCard hoverable={true} className={`transition-all duration-300 ${isOpen ? 'rounded-b-none border-b-0' : ''}`}>
                <div className="p-6">
                  <div className="flex flex-col-reverse gap-5 md:gap-0 md:flex-row items-center md:items-start justify-between">
                    <div className="text-center md:text-left">
                      <h4 className="text-[11px] font-black uppercase tracking-widest text-white">
                        {example.title}
                      </h4>
                      <p className="text-[10px] font-mono uppercase tracking-widest text-gray-500 mt-1">
                        {example.description}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 self-start sm:self-auto">
                      <div className="flex items-center gap-1 bg-white/10 text-white border border-white/10 px-3 py-1.5 rounded-lg text-xs font-mono shadow-sm">
                        <span>{example.tool}</span>
                        <ChevronDown
                          className={`h-3.5 w-3.5 transition-transform ${isOpen ? "rotate-180" : ""
                            }`}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </GlassCard>
            </div>
          </CollapsibleTrigger>

          <CollapsibleContent>
            <GlassCard hoverable={false} className="rounded-t-none border-t-0 bg-black/20">
              <div className="p-6 pt-2">
                <div className="space-y-3">
                  <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      JSON Arguments
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => handleCopy(e, example.args)}
                      className="h-8 hover:bg-purple-500/20"
                    >
                      {copied ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                  <div className="bg-[#1e1e1e] rounded-xl overflow-hidden border border-white/10 shadow-inner">
                    <div className="bg-[#2d2d2d] px-4 py-1.5 flex items-center border-b border-white/5">
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f56]"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-[#ffbd2e]"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-[#27c93f]"></div>
                      </div>
                    </div>
                    <pre className="p-4 text-sm overflow-x-auto text-gray-300">
                      <code className="font-mono">
                        {example.args}
                      </code>
                    </pre>
                  </div>
                </div>
              </div>
            </GlassCard>
          </CollapsibleContent>
        </Collapsible>
      </div>
    );
  };

  return (
    <section className="py-24 px-4 bg-black relative overflow-hidden">
      <SectionDivider variant="mesh" className="absolute top-0 left-0 right-0 z-0 opacity-40" />
      <div className="container mx-auto max-w-5xl relative z-10">
        <div className="text-center mb-16">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="p-2 rounded-full bg-purple-600 text-white">
              <BookOpen className="h-6 w-6" />
            </div>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-black text-white uppercase tracking-tight py-2">
              MCP Tool Cookbook
            </h2>
          </div>
          <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest max-w-3xl mx-auto leading-relaxed">
            Practical examples and patterns for using CodeGraphContext with AI assistants.
            Copy the JSON arguments and use them directly with your MCP-enabled AI tools.
          </p>
        </div>

        <Tabs defaultValue="basic" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-10 bg-white/5 p-1.5 rounded-full h-auto border border-white/10 shadow-inner">
            <TabsTrigger value="basic" className="flex items-center justify-center gap-2 py-3 rounded-full data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-all text-[10px] font-black uppercase tracking-widest text-gray-500 hover:text-white data-[state=active]:hover:text-white">
              <Search className="h-4 w-4" />
              <span className="hidden sm:inline">Basic Navigation</span>
              <span className="sm:hidden">Basic</span>
            </TabsTrigger>
            <TabsTrigger value="analysis" className="flex items-center justify-center gap-2 py-3 rounded-full data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-all text-[10px] font-black uppercase tracking-widest text-gray-500 hover:text-white data-[state=active]:hover:text-white">
              <Terminal className="h-4 w-4" />
              <span className="hidden sm:inline">Code Analysis</span>
              <span className="sm:hidden">Analysis</span>
            </TabsTrigger>
            <TabsTrigger value="cypher" className="flex items-center justify-center gap-2 py-3 rounded-full data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-all text-[10px] font-black uppercase tracking-widest text-gray-500 hover:text-white data-[state=active]:hover:text-white">
              <Database className="h-4 w-4" />
              <span className="hidden sm:inline">Advanced Queries</span>
              <span className="sm:hidden">Advanced</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="basic" className="space-y-4">
            <div className="text-center mb-8">
              <h3 className="text-sm font-black uppercase tracking-widest text-white mb-3">Basic Navigation & Discovery</h3>
              <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                Essential queries for exploring and understanding your codebase structure.
              </p>
            </div>
            {basicExamples.map((example) => (
              <ExampleCard
                key={example.id}
                example={example}
                isOpen={openItems.has(example.id)}
                onToggle={() => toggleItem(example.id)}
              />
            ))}
          </TabsContent>

          <TabsContent value="analysis" className="space-y-4">
            <div className="text-center mb-8">
              <h3 className="text-sm font-black uppercase tracking-widest text-white mb-3">Code Analysis & Quality</h3>
              <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                Advanced analysis tools for code quality, complexity, and dependency tracking.
              </p>
            </div>
            {analysisExamples.map((example) => (
              <ExampleCard
                key={example.id}
                example={example}
                isOpen={openItems.has(example.id)}
                onToggle={() => toggleItem(example.id)}
              />
            ))}
          </TabsContent>

          <TabsContent value="cypher" className="space-y-4">
            <div className="text-center mb-8">
              <h3 className="text-sm font-black uppercase tracking-widest text-white mb-3">Advanced Cypher Queries</h3>
              <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                Direct Neo4j Cypher queries for complex analysis and custom investigations.
              </p>
            </div>
            {cypherExamples.map((example) => (
              <ExampleCard
                key={example.id}
                example={example}
                isOpen={openItems.has(example.id)}
                onToggle={() => toggleItem(example.id)}
              />
            ))}
          </TabsContent>
        </Tabs>

        <div className="mt-16 text-center">
          <GlassCard hoverable={false} glowColor="none" className="inline-block p-8 border border-white/20">
            <div className="flex items-center justify-center gap-3 mb-4">
              <div className="p-2 rounded-full bg-purple-600 text-white">
                <Code className="h-6 w-6" />
              </div>
              <h4 className="text-[11px] font-black uppercase tracking-widest text-white">Want to contribute more examples?</h4>
            </div>
            <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest mb-6">
              Help expand this cookbook with your own patterns and use cases.
            </p>
            <Button className="bg-transparent hover:bg-purple-600 hover:text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] text-white rounded-full px-8 py-3 border border-white/20 font-black text-[10px] uppercase tracking-widest transition-colors" asChild>
              <a
                href="https://github.com/CodeGraphContext/CodeGraphContext/blob/main/docs/docs/cookbook.md"
                target="_blank"
                rel="noopener noreferrer"
              >
                View Full Cookbook on GitHub
              </a>
            </Button>
          </GlassCard>
        </div>
      </div>
    </section>
  );
};

export default CookbookSection;

