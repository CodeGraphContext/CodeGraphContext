import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { motion } from "framer-motion";
import { GitBranch, Eye, Zap, Terminal } from "lucide-react";
import GlassCard from "./GlassCard";
import SectionDivider from "./SectionDivider";

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
        <div className="text-center mb-16 relative z-10">
          <h2 className="text-4xl md:text-5xl font-black mb-6 uppercase tracking-tight text-white py-2">
            Powerful Features
          </h2>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-sm font-mono text-gray-500 uppercase tracking-widest max-w-3xl mx-auto"
          >
            Transform your codebase into an intelligent knowledge graph that AI assistants can understand and navigate
          </motion.p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 relative z-10">
          {features.map((feature, index) => (
            <motion.div 
              key={index} 
              className="relative"
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
            >
              {/* Optional connection line visually linking items */}
              {index % 2 === 0 && index < features.length - 1 && (
                <div className="hidden md:block absolute top-1/2 -right-4 w-8 border-t-2 border-dashed border-border/50 z-0"></div>
              )}
              {index < features.length - 2 && (
                <div className="hidden md:block absolute -bottom-4 left-1/2 h-8 border-l-2 border-dashed border-border/50 z-0"></div>
              )}
              
              <GlassCard
                glowColor="none"
                className="h-full group rounded-3xl"
              >
                <div className="absolute top-4 right-6 text-6xl font-black opacity-5 pointer-events-none transition-opacity group-hover:opacity-10 text-white">
                  0{index + 1}
                </div>
                <div className="p-6 sm:p-8">
                  <div className="flex items-center gap-4 mb-6">
                    <div className={`p-4 rounded-2xl bg-black border border-white/10 group-hover:border-purple-500/50 group-hover:bg-purple-500/10 transition-smooth relative overflow-hidden`}>
                      <div className={`absolute inset-0 bg-gradient-to-br from-purple-500/20 to-cyan-400/20 opacity-0 group-hover:opacity-100 transition-opacity`} />
                      <feature.icon className={`h-8 w-8 text-gray-400 group-hover:text-cyan-400 transition-colors relative z-10`} />
                    </div>
                    <h3 className="text-xl font-bold uppercase tracking-widest text-white">{feature.title}</h3>
                  </div>
                  <p className="text-sm font-mono text-gray-400 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default FeaturesSection;

