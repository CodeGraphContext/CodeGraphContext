import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { ChevronDown, Copy, Terminal, Search, Code, Database, BookOpen } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

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
  }) => (
    <div data-aos="fade-up" data-aos-delay="100">
      <Collapsible open={isOpen} onOpenChange={onToggle}>
        <CollapsibleTrigger asChild>
          <Card className="cursor-pointer hover:bg-muted/30 transition-all duration-200 border border-border/50">
            <CardHeader>
              <div className="flex flex-col-reverse gap-5 md:gap-0 md:flex-row items-center md:items-start justify-between">
                <div className="text-center md:text-left">
                  <CardTitle className="text-base font-medium text-foreground">
                    {example.title}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    {example.description}
                  </p>
                </div>
                <div className="flex items-center gap-2 self-start sm:self-auto">
                  <div className="flex items-center gap-1 bg-secondary text-secondary-foreground px-2 py-1 rounded-md text-xs">
                    <span>{example.tool}</span>
                    <ChevronDown
                      className={`h-3.5 w-3.5 transition-transform ${
                        isOpen ? "rotate-180" : ""
                      }`}
                    />
                  </div>
                </div>
              </div>
            </CardHeader>
          </Card>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <Card className="mt-2 border border-border/30 bg-muted/20">
            <CardContent className="p-4">
              <div className="space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <span className="text-sm font-medium text-muted-foreground">
                    JSON Arguments:
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(example.args)}
                    className="h-7"
                  >
                    <Copy className="h-3 w-3" />
                  </Button>
                </div>
                <pre className="bg-muted/50 rounded-md p-3 text-sm overflow-x-auto border border-border/30">
                  <code className="text-foreground break-words">
                    {example.args}
                  </code>
                </pre>
              </div>
            </CardContent>
          </Card>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );

  return (
    <section className="py-20 px-4 bg-gradient-subtle relative overflow-hidden" data-aos="fade-in">
      <div className="absolute inset-0 bg-grid-pattern opacity-20" />
      <div className="container mx-auto max-w-6xl relative z-10">
        <div className="text-center mb-16" data-aos="fade-down">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-primary/10 border border-primary/20">
              <BookOpen className="h-6 w-6 text-primary" />
            </div>
            <h2 className="text-4xl font-bold bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
              MCP Tool Cookbook
            </h2>
          </div>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            Practical examples and patterns for using CodeGraphContext with AI assistants.
            Copy the JSON arguments and use them directly with your MCP-enabled AI tools.
          </p>
        </div>

        <Tabs defaultValue="basic" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-8" data-aos="fade-up" data-aos-delay="200">
            <TabsTrigger value="basic" className="flex items-center gap-1 sm:gap-2 text-xs sm:text-sm">
              <Search className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Basic Navigation</span>
              <span className="sm:hidden">Basic</span>
            </TabsTrigger>
            <TabsTrigger value="analysis" className="flex items-center gap-1 sm:gap-2 text-xs sm:text-sm">
              <Terminal className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Code Analysis</span>
              <span className="sm:hidden">Analysis</span>
            </TabsTrigger>
            <TabsTrigger value="cypher" className="flex items-center gap-1 sm:gap-2 text-xs sm:text-sm">
              <Database className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Advanced Queries</span>
              <span className="sm:hidden">Advanced</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="basic" className="space-y-4">
            <div className="text-center mb-8">
              <h3 className="text-2xl font-semibold mb-3">Basic Navigation & Discovery</h3>
              <p className="text-muted-foreground">
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
              <h3 className="text-2xl font-semibold mb-3">Code Analysis & Quality</h3>
              <p className="text-muted-foreground">
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
              <h3 className="text-2xl font-semibold mb-3">Advanced Cypher Queries</h3>
              <p className="text-muted-foreground">
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

        <div className="mt-16 text-center" data-aos="fade-up" data-aos-delay="300">
          <Card className="inline-block p-6 bg-gradient-to-r from-primary/5 to-accent/5 border border-primary/20">
            <div className="flex items-center gap-3 mb-3">
              <Code className="h-5 w-5 text-primary" />
              <h4 className="text-lg font-semibold">Want to contribute more examples?</h4>
            </div>
            <p className="text-muted-foreground mb-4">
              Help expand this cookbook with your own patterns and use cases.
            </p>
            <Button variant="outline" asChild>
              <a 
                  href="https://github.com/CodeGraphContext/CodeGraphContext/blob/main/docs/docs/cookbook.md"
                  target="_blank"
                  rel="noopener noreferrer"
              >
                View Full Cookbook on GitHub
              </a>
            </Button>
          </Card>
        </div>
      </div>
    </section>
  );
};

export default CookbookSection;

