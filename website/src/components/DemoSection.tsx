import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { motion } from "framer-motion";
import graphTotalImage from "../assets/graph-total.png";
import functionCallsImage from "../assets/function-calls.png";
import hierarchyImage from "../assets/hierarchy.png";
import type { Variants } from "framer-motion";

const DemoSection = () => {
  const visualizations = [
    {
      title: "Complete Code Graph",
      description: "All components and relationships between code elements.",
      image: graphTotalImage,
      badge: "Full Overview",
      aos: "fade-up",
    },
    {
      title: "Function Call Analysis",
      description: "Direct and indirect function calls across directories.",
      image: functionCallsImage,
      badge: "Call Chains",
      aos: "zoom-in",
    },
    {
      title: "Project Hierarchy",
      description: "Hierarchical structure of files and dependencies.",
      image: hierarchyImage,
      badge: "File Structure",
      aos: "flip-up",
    },
  ];

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.2, delayChildren: 0.1 },
  },
};

const itemVariants: Variants = {
  hidden: { y: 20, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.6, ease: "easeOut" },
  },
};


  return (
    <section
      className="py-20 px-4 bg-gradient-to-b from-background to-secondary/10"
      data-aos="fade-in"
      data-aos-duration="800"
    >
      <div className="container mx-auto max-w-7xl">
        {/* Heading Section */}
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: -20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.7 }}
        >
          <h2
            className="text-3xl sm:text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent py-2"
            data-aos="fade-down"
            data-aos-duration="1000"
          >
            See CodeGraphContext in Action
          </h2>
          <p
            className="text-xl text-muted-foreground max-w-3xl mx-auto mb-12"
            data-aos="fade-up"
            data-aos-delay="200"
          >
            Watch how CodeGraphContext transforms complex codebases into
            interactive knowledge graphs.
          </p>
        </motion.div>

        {/* Embedded Demo Video */}
        <motion.div
          className="max-w-4xl mx-auto mb-16"
          initial={{ opacity: 0, scale: 0.9 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.8, ease: "easeInOut" }}
          data-aos="zoom-in"
        >
          <div className="relative aspect-video rounded-lg overflow-hidden shadow-2xl border border-border/50">
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
          <h3
            className="text-3xl font-bold text-center mb-8"
            data-aos="fade-up"
            data-aos-delay="100"
          >
            Interactive Visualizations
          </h3>

          <motion.div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8"
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.2 }}
          >
            {visualizations.map((viz, index) => (
              <motion.div
                key={index}
                variants={itemVariants}
                data-aos={viz.aos}
                data-aos-delay={index * 150}
              >
                <Card className="group hover:shadow-xl transition-all duration-300 border-border/50 overflow-hidden w-full h-full bg-background/70 backdrop-blur-sm">
                  <Dialog>
                    <DialogTrigger asChild>
                      <div className="relative cursor-pointer flex flex-col h-full">
                        <div className="relative">
                          <img
                            src={viz.image}
                            alt={viz.title}
                            className="w-full h-48 object-cover group-hover:scale-105 transition-transform duration-300"
                            loading="lazy"
                          />
                          <Badge className="absolute top-2 left-2 text-xs">
                            {viz.badge}
                          </Badge>
                        </div>
                        <CardContent className="p-6 flex-grow flex flex-col">
                          <h4 className="text-xl font-semibold mb-3 group-hover:text-primary transition-colors">
                            {viz.title}
                          </h4>
                          <p className="text-base text-muted-foreground flex-grow">
                            {viz.description}
                          </p>
                        </CardContent>
                      </div>
                    </DialogTrigger>

                    {/* Dialog Content */}
                    <DialogContent className="max-w-5xl w-full">
                      <img
                        src={viz.image}
                        alt={`${viz.title} Visualization`}
                        className="w-full h-auto max-h-[80vh] object-contain rounded-lg"
                      />
                    </DialogContent>
                  </Dialog>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
};

export default DemoSection;
