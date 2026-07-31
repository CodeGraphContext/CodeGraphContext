import { track } from "@vercel/analytics/react";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { motion } from "framer-motion";
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

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.2,
      },
    },
  };

  const itemVariants = {
    hidden: { y: 40, opacity: 0 },
    visible: {
      y: 0,
      opacity: 1,
      transition: {
        type: "spring",
        stiffness: 100,
        damping: 15,
      },
    },
  };

  return (
    <section className="py-20 px-4 bg-black">
      <div className="container mx-auto max-w-7xl relative z-10">
        <SectionDivider variant="wave" className="absolute -top-20 left-0 right-0 z-0" />
        
        {/* Heading Section */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-50px" }}
          transition={{ type: "spring", stiffness: 100, damping: 20 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-black mb-6 gradient-text uppercase tracking-tight py-2">
            See CodeGraphContext in Action
          </h2>
          <p className="text-sm font-mono text-gray-500 uppercase tracking-widest max-w-3xl mx-auto mb-12">
            Watch how CodeGraphContext transforms complex codebases into
            interactive knowledge graphs.
          </p>
        </motion.div>

        {/* Embedded Demo Video */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, margin: "-50px" }}
          transition={{ type: "spring", stiffness: 80, damping: 20, delay: 0.2 }}
          className="max-w-4xl mx-auto mb-16"
        >
          <div className="relative aspect-video rounded-3xl overflow-hidden shadow-[0_0_40px_rgba(168,85,247,0.15)] border border-white/20">
            <iframe
              src="https://www.youtube.com/embed/KYYSdxhg1xU?autoplay=1&mute=1&loop=1&playlist=KYYSdxhg1xU"
              title="CodeGraphContext Demo"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="w-full h-full"
            />
          </div>
        </motion.div>

        {/* Interactive Visualizations Section */}
        <div className="mb-12">
          <motion.h3 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.5 }}
            className="text-xl md:text-2xl font-black uppercase tracking-widest text-center text-white mb-8"
          >
            Interactive Visualizations
          </motion.h3>

          <motion.div 
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-50px" }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8"
          >
            {visualizations.map((viz, index) => (
              <motion.div key={index} variants={itemVariants}>
                <motion.div
                  whileHover={{ y: -8, scale: 1.02 }}
                  transition={{ type: "spring", stiffness: 300, damping: 20 }}
                  className="h-full relative group"
                >
                  {/* Subtle glow effect on hover */}
                  <div className="absolute inset-0 bg-purple-500/20 opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-500 rounded-3xl pointer-events-none" />
                  
                  <GlassCard className="h-full w-full relative z-10 transition-colors duration-300 group-hover:border-purple-500/50 group-hover:shadow-[0_0_30px_rgba(168,85,247,0.15)] overflow-hidden flex flex-col cursor-pointer">
                    <Dialog>
                      <DialogTrigger asChild>
                        <div 
                          className="flex flex-col h-full outline-none"
                          onClick={() => {
                            track('feature_clicked', {
                                feature: 'DemoSection',
                                demo: viz.title
                              });
                          }}
                        >
                          <div className="relative overflow-hidden">
                            <motion.img
                              whileHover={{ scale: 1.05 }}
                              transition={{ duration: 0.4 }}
                              src={viz.image}
                              alt={viz.title}
                              className="w-full h-48 object-cover opacity-90 group-hover:opacity-100"
                              loading="lazy"
                            />
                            <Badge className="absolute top-4 left-4 text-[10px] font-mono uppercase tracking-widest bg-purple-500/20 text-purple-300 border border-purple-500/50 rounded-full py-1 backdrop-blur-md">
                              {viz.badge}
                            </Badge>
                          </div>
                          <div className="p-6 flex-grow flex flex-col bg-black">
                            <h4 className="text-sm font-black uppercase tracking-widest text-white mb-3 group-hover:text-purple-300 transition-colors duration-300">
                              {viz.title}
                            </h4>
                            <p className="text-xs font-mono text-gray-500 flex-grow group-hover:text-gray-400 transition-colors duration-300">
                              {viz.description}
                            </p>
                          </div>
                        </div>
                      </DialogTrigger>

                      {/* Dialog Content */}
                      <DialogContent className="max-w-[95vw] w-full h-[95vh] bg-black/95 backdrop-blur-xl border-white/20 rounded-3xl p-2 md:p-6 shadow-[0_0_50px_rgba(168,85,247,0.2)] flex items-center justify-center overflow-hidden">
                        <img
                           src={viz.image}
                           alt={`${viz.title} Visualization`}
                           className="w-full h-full object-contain rounded-2xl"
                        />
                      </DialogContent>
                    </Dialog>
                  </GlassCard>
                </motion.div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
};

export default DemoSection;
