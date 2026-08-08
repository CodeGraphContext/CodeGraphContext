import { MessageCircle, Search, Eye, BarChart3 } from "lucide-react";
import GlassCard from "./GlassCard";
import SectionDivider from "./SectionDivider";

const examplesData = [
  {
    icon: MessageCircle,
    category: "Indexing",
    title: "Add Projects to Graph",
    color: "primary",
    examples: [
      "Please index the code in the `/path/to/my-project` directory.",
      "Add the project at `~/dev/my-app` to the code graph."
    ]
  },
  {
    icon: Search,
    category: "Analysis",
    title: "Code Relationships", 
    color: "accent",
    examples: [
      "Show me all functions that call `process_data()`",
      "Find the class hierarchy for `BaseProcessor`"
    ]
  },
  {
    icon: Eye,
    category: "Monitoring",
    title: "Live Updates",
    color: "graph-node-3",
    examples: [
      "Watch the `/project` directory for changes.",
      "Keep the graph updated for my active development."
    ]
  },
  {
    icon: BarChart3,
    category: "Insights",
    title: "Code Quality",
    color: "graph-node-1",
    examples: [
      "Find dead code in my project",
      "Show the most complex functions by cyclomatic complexity"
    ]
  }
];

const ExamplesSection = () => {
  return (
    <section className="py-24 px-4 relative bg-black">
      <SectionDivider variant="wave" className="absolute top-0 left-0 right-0 z-0 opacity-40" />
      
      <div className="container mx-auto max-w-6xl relative z-10">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-black mb-6 gradient-text uppercase tracking-tight py-2">
            Natural Language Interface
          </h2>
          <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest max-w-3xl mx-auto">
            Interact with your code graph using plain English. No complex queries or syntax to learn.
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {examplesData.map((example, index) => (
            <div key={index}>
              <GlassCard glowColor="none" className="h-full group p-6 sm:p-8">
                <div className="flex items-center gap-4 mb-6">
                  <div className={`p-3 rounded-full bg-${example.color}/10 text-${example.color} group-hover:bg-${example.color}/20 transition-colors`}>
                    <example.icon className="h-5 w-5" />
                  </div>
                  <div>
                    <span className={`text-[8px] font-black px-3 py-1 rounded-full bg-${example.color}/10 text-${example.color} uppercase tracking-widest mb-2 inline-block`}>
                      {example.category}
                    </span>
                    <h3 className="text-sm font-black uppercase tracking-widest text-white">{example.title}</h3>
                  </div>
                </div>
                
                <div className="space-y-4 pl-2 border-l border-white/10 ml-5">
                  {example.examples.map((text, idx) => (
                    <div key={idx} className="relative group/bubble">
                      <div className={`absolute -left-[23px] top-3 w-2.5 h-2.5 rounded-full bg-${example.color}/20 border border-${example.color}/40 group-hover/bubble:bg-${example.color} transition-colors`}></div>
                      <div className="p-4 rounded-3xl rounded-tl-sm bg-white/5 border border-white/5 group-hover/bubble:border-white/10 transition-colors">
                        <p className="text-[10px] text-gray-400 font-mono uppercase tracking-widest">"{text}"</p>
                      </div>
                    </div>
                  ))}
                </div>
              </GlassCard>
            </div>
          ))}
        </div>
        
      </div>
    </section>
  );
};

export default ExamplesSection;
