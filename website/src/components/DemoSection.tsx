import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import GlassCard from "./GlassCard";
import SectionDivider from "./SectionDivider";

import graphTotalImage from "@/assets/graph-total.png";
import functionCallsImage from "@/assets/function-calls.png";
import hierarchyImage from "@/assets/hierarchy.png";

const DemoSection = () => {
  const visualizations = [
    {
      title: "Complete Code Graph",
      description: "All components and relationships between code elements.",
      image: graphTotalImage,
      badge: "Full Overview",
    },
    {
      title: "Function Call Analysis",
      description: "Direct and indirect function calls across directories.",
      image: functionCallsImage,
      badge: "Call Chains",
    },
    {
      title: "Project Hierarchy",
      description: "Hierarchical structure of files and dependencies.",
      image: hierarchyImage,
      badge: "File Structure",
    },
  ];


  return (
    <section
      className="py-20 px-4 bg-black"
    >
      <div className="container mx-auto max-w-7xl relative z-10">
        <SectionDivider variant="wave" className="absolute -top-20 left-0 right-0 z-0" />
        
        {/* Heading Section */}
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-black mb-6 gradient-text uppercase tracking-tight py-2">
            See CodeGraphContext in Action
          </h2>
          <p className="text-sm font-mono text-gray-500 uppercase tracking-widest max-w-3xl mx-auto mb-12">
            Watch how CodeGraphContext transforms complex codebases into
            interactive knowledge graphs.
          </p>
        </div>

        {/* Embedded Demo Video */}
        <div className="max-w-4xl mx-auto mb-16">
          <div className="relative aspect-video rounded-3xl overflow-hidden shadow-2xl border border-white/20">
            <iframe
              src="https://www.youtube.com/embed/KYYSdxhg1xU?autoplay=1&mute=1&loop=1&playlist=KYYSdxhg1xU"
              title="CodeGraphContext Demo"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="w-full h-full"
            />
          </div>
        </div>

        {/* Interactive Visualizations Section */}
        <div className="mb-12">
          <h3 className="text-xl md:text-2xl font-black uppercase tracking-widest text-center text-white mb-8">
            Interactive Visualizations
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {visualizations.map((viz, index) => (
              <div key={index}>
                <GlassCard className="group h-full w-full">
                  <Dialog>
                    <DialogTrigger asChild>
                      <div className="relative cursor-pointer flex flex-col h-full rounded-3xl overflow-hidden bg-black border border-white/10">
                        <div className="relative">
                          <img
                            src={viz.image}
                            alt={viz.title}
                            className="w-full h-48 object-cover opacity-90 group-hover:opacity-100 transition-all duration-300"
                            loading="lazy"
                          />
                          <Badge className="absolute top-4 left-4 text-[10px] font-mono uppercase tracking-widest bg-purple-500/20 text-purple-300 border border-purple-500/50 rounded-full py-1">
                            {viz.badge}
                          </Badge>
                        </div>
                        <div className="p-6 flex-grow flex flex-col bg-black">
                          <h4 className="text-sm font-black uppercase tracking-widest text-white mb-3 group-hover:text-gray-300 transition-colors">
                            {viz.title}
                          </h4>
                          <p className="text-xs font-mono text-gray-500 flex-grow">
                            {viz.description}
                          </p>
                        </div>
                      </div>
                    </DialogTrigger>

                    {/* Dialog Content */}
                    <DialogContent className="max-w-5xl w-full bg-black border-white/20 rounded-3xl p-4">
                      <img
                         src={viz.image}
                         alt={`${viz.title} Visualization`}
                         className="w-full h-auto max-h-[80vh] object-contain rounded-2xl"
                      />
                    </DialogContent>
                  </Dialog>
                </GlassCard>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default DemoSection;
