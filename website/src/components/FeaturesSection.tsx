import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { GitBranch, Eye, Zap, Terminal } from "lucide-react";

const features = [
  {
    icon: GitBranch,
    title: "Code Indexing",
    description: "Analyzes code and builds a comprehensive knowledge graph of its components, relationships, and dependencies.",
    color: "graph-node-1"
  },
  {
    icon: Eye,
    title: "Relationship Analysis",
    description: "Query for callers, callees, class hierarchies, and complex code relationships through natural language.",
    color: "graph-node-2"
  },
  {
    icon: Zap,
    title: "Live Updates",
    description: "Watches local files for changes and automatically updates the graph in real-time as you code.",
    color: "graph-node-3"
  },
  {
    icon: Terminal,
    title: "Interactive Setup",
    description: "User-friendly command-line wizard for easy setup. FalkorDB Lite is default (Unix and WSL), with Neo4j available via Docker or native installation.",
    color: "graph-node-1"
  }
];

const FeaturesSection = () => {
  return (
    <section className="py-24 px-4">
      <div className="container mx-auto max-w-6xl">
        <div className="text-center mb-16" data-aos="fade-down">
          <h2 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
            Powerful Features
          </h2>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Transform your codebase into an intelligent knowledge graph that AI assistants can understand and navigate
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {features.map((feature, index) => (
            <div key={index} data-aos="fade-up" data-aos-delay={index * 100}>
              <Card
                className="border-border/50 hover:border-primary/30 transition-smooth group hover:shadow-glow animate-float-up dark:bg-gradient-card dark:bg-card/50 dark:border-border/30 dark:hover:border-primary/40 bg-white/95 border-gray-200/50 hover:border-primary/50 shadow-sm h-full"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <CardHeader>
                  <div className="flex items-center gap-4 mb-4">
                    <div className={`p-3 rounded-xl bg-${feature.color}/10 border border-${feature.color}/20 group-hover:bg-${feature.color}/20 transition-smooth dark:bg-${feature.color}/20 dark:border-${feature.color}/30 bg-${feature.color}/5 border-${feature.color}/15`}>
                      <feature.icon className={`h-6 w-6 text-${feature.color}`} />
                    </div>
                    <CardTitle className="text-xl font-semibold dark:text-foreground text-gray-900">{feature.title}</CardTitle>
                  </div>
                  <CardDescription className="text-base text-muted-foreground leading-relaxed dark:text-muted-foreground text-gray-600">
                    {feature.description}
                  </CardDescription>
                </CardHeader>
              </Card>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default FeaturesSection;

