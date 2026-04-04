import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MessageCircle, Search, Eye, BarChart3 } from "lucide-react";
import { motion } from "framer-motion";

const examplesData = [
  {
    icon: MessageCircle,
    category: "Indexing",
    title: "Add Projects to Graph",
    examples: [
      "Please index the code in the `/path/to/my-project` directory.",
      "Add the project at `~/dev/my-app` to the code graph."
    ]
  },
  {
    icon: Search,
    category: "Analysis",
    title: "Code Relationships", 
    examples: [
      "Show me all functions that call `process_data()`",
      "Find the class hierarchy for `BaseProcessor`"
    ]
  },
  {
    icon: Eye,
    category: "Monitoring",
    title: "Live Updates",
    examples: [
      "Watch the `/project` directory for changes.",
      "Keep the graph updated for my active development."
    ]
  },
  {
    icon: BarChart3,
    category: "Insights",
    title: "Code Quality",
    examples: [
      "Find dead code in my project",
      "Show the most complex functions by cyclomatic complexity"
    ]
  }
];

const ExamplesSection = () => {
  return (
    <section className="py-24 px-4" data-aos="fade-in">
      <div className="container mx-auto max-w-6xl">
        <div className="text-center mb-16" data-aos="fade-down">
          <h2 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent py-2">
            Natural Language Interface
          </h2>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Interact with your code graph using plain English. No complex queries or syntax to learn.
          </p>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {examplesData.map((example, index) => (
            <div key={index} data-aos="fade-up" data-aos-delay={index * 100}>
              <Card className="h-full border-border/50 group animate-float-up bg-white/95 dark:bg-card/50 shadow-sm hover:shadow-lg transition-shadow duration-300">
                <CardHeader>
                  <div className="flex items-center gap-4 mb-4">
                    <div className="p-3 rounded-xl bg-primary/5 border border-primary/15 group-hover:bg-primary/10 transition-colors dark:bg-primary/20 dark:border-primary/30">
                      <example.icon className="h-6 w-6 text-primary" />
                    </div>
                    <div>
                      <Badge variant="secondary" className="mb-2">{example.category}</Badge>
                      <CardTitle className="text-xl font-semibold">{example.title}</CardTitle>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {example.examples.map((text, idx) => (
                      <div key={idx} className="p-3 rounded-md border-l-4 border-accent/30 bg-muted/30 hover:border-accent/60 transition-colors">
                        <p className="text-sm text-muted-foreground italic">"{text}"</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          ))}
        </div>
        
        <div className="text-center mt-16" data-aos="fade-up" data-aos-delay="200">
          <Card className="max-w-2xl mx-auto bg-white/95 dark:bg-card/50 shadow-sm p-2">
            <CardContent className="pt-8">
              <h3 className="text-2xl font-bold mb-4">Ready to enhance your AI assistant?</h3>
              <p className="text-muted-foreground mb-6">
                Start building intelligent code understanding today with CodeGraphContext.
              </p>
              <div className="p-3 rounded-md bg-muted/40 max-w-md mx-auto border shadow-inner">
                <code className="text-accent font-mono">$ pip install codegraphcontext</code>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
};

export default ExamplesSection;
