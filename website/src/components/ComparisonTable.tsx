"use client";

import { motion } from "framer-motion";

import { Badge } from "@/components/ui/badge";
import GlassCard from "./GlassCard";
import SectionDivider from "./SectionDivider";

const tableData = [
  {
    feature: "Code Completion",
    copilot: { text: "Strong", status: "good" },
    cursor: { text: "Strong", status: "good" },
    cgc: { text: "Strong", status: "good" },
  },
  {
    feature: "Refactoring Suggestions",
    copilot: { text: "Limited to context length", status: "warning" },
    cursor: { text: "Limited to context length", status: "warning" },
    cgc: { text: "Via dependency tracing", status: "good" },
  },
  {
    feature: "Codebase Understanding",
    copilot: { text: "Limited", status: "bad" },
    cursor: { text: "Partial (local context)", status: "warning" },
    cgc: { text: "Deep graph-based", status: "good" },
  },
  {
    feature: "Call Graph & Imports",
    copilot: { text: "No", status: "bad" },
    cursor: { text: "No", status: "bad" },
    cgc: { text: "Direct + Multi-hops", status: "good" },
  },
  {
    feature: "Cross-File Tracing",
    copilot: { text: "Very low", status: "bad" },
    cursor: { text: "Some", status: "warning" },
    cgc: { text: "Complete code", status: "good" },
  },
  {
    feature: "LLM Explainability",
    copilot: { text: "Low", status: "bad" },
    cursor: { text: "Hallucinate", status: "warning" },
    cgc: { text: "Extremely good", status: "good" },
  },
  {
    feature: "Performance on Large Codebases",
    copilot: { text: "Slows with size", status: "bad" },
    cursor: { text: "Slows with size", status: "bad" },
    cgc: { text: "Scales with graph DB", status: "good" },
  },
  {
    feature: "Extensible to Multiple Languages",
    copilot: { text: "Strong", status: "good" },
    cursor: { text: "Strong", status: "good" },
    cgc: { text: "Work-in-progress", status: "warning" },
  },
  {
    feature: "Set-up Time for new code",
    copilot: { text: "Low", status: "good" },
    cursor: { text: "Slows with size", status: "bad" },
    cgc: { text: "Slows with size", status: "bad" },
  },
];

const StatusBadge = ({ status, text }: { status: string; text: string }) => {
  const getStatusStyles = () => {
    switch (status) {
      case "good":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/20";
      case "warning":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "bad":
        return "bg-white/5 text-gray-500 border-white/5";
      default:
        return "bg-black text-gray-500 border-white/10";
    }
  };

  const getIcon = () => {
    switch (status) {
      case "good":
        return "✓";
      case "warning":
        return "⚠";
      case "bad":
        return "✕";
      default:
        return "";
    }
  };

  return (
    <Badge
      className={`
        ${getStatusStyles()}
        border font-bold uppercase tracking-widest text-[0.55rem] sm:text-[0.65rem] px-2 sm:px-3 py-1.5 
        rounded-full transition-all duration-300
      `}
    >
      <span className="mr-1 sm:mr-2 font-black">{getIcon()}</span>
      <span className="relative z-10">{text}</span>
    </Badge>
  );
};

export default function ComparisonTable() {
  return (
    <section
      className="relative min-h-screen flex items-center justify-center bg-black overflow-hidden py-24 px-4"
    >
      <div className="container mx-auto max-w-7xl relative z-10">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-black mb-6 uppercase tracking-tight text-white py-2">
            Why CodeGraphContext?
          </h2>
          <p className="text-sm font-mono text-gray-500 uppercase tracking-widest max-w-3xl mx-auto mb-12">
            Experience the next generation of AI-powered code understanding
            with graph-based intelligence
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          <GlassCard hoverable={false} className="p-1 sm:p-2 bg-black border-white/20">
          <div className="overflow-x-auto rounded-3xl">
            <table className="w-full min-w-[600px] md:min-w-full table-auto border-collapse">
              <thead>
                <tr className="border-b border-white/20 bg-white/5">
                  <th className="sticky top-0 z-20 bg-black p-4 text-left font-black uppercase tracking-widest text-white text-[0.65rem] sm:text-xs">
                    Feature
                  </th>
                  <th className="sticky top-0 z-20 bg-black p-4 text-center font-black uppercase tracking-widest text-white text-[0.65rem] sm:text-xs min-w-[120px]">
                    GitHub Copilot
                  </th>
                  <th className="sticky top-0 z-20 bg-black p-4 text-center font-black uppercase tracking-widest text-white text-[0.65rem] sm:text-xs min-w-[120px]">
                    Cursor
                  </th>
                  <th className="sticky top-0 z-20 bg-black p-4 text-center font-black uppercase tracking-widest text-white text-[0.65rem] sm:text-xs min-w-[120px] relative">
                    CodeGraphContext
                    <span className="absolute -top-1 right-2 text-[8px] bg-purple-600 text-white px-2 py-0.5 rounded-full font-black">RECOMMENDED</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tableData.map((row, index) => (
                  <tr
                    key={row.feature}
                    className={`
                      border-b border-white/10 transition-colors duration-300 
                      hover:bg-purple-500/10
                      ${index % 2 === 0 ? "bg-black" : "bg-white/[0.02]"}
                    `}
                  >
                    <td className="p-4 sm:p-6 text-white font-bold text-xs uppercase tracking-widest text-left">
                      {row.feature}
                    </td>
                    <td className="p-4 sm:p-6 text-center">
                      <div className="flex justify-center">
                        <StatusBadge status={row.copilot.status} text={row.copilot.text} />
                      </div>
                    </td>
                    <td className="p-4 sm:p-6 text-center">
                      <div className="flex justify-center">
                        <StatusBadge status={row.cursor.status} text={row.cursor.text} />
                      </div>
                    </td>
                    <td className="p-4 sm:p-6 text-center bg-white/5">
                      <div className="flex justify-center">
                        <StatusBadge status={row.cgc.status} text={row.cgc.text} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
        </motion.div>

        <div className="text-center mt-12 mb-16">
          <p className="text-sm font-mono text-gray-500 uppercase tracking-widest">
            Experience the power of graph-based code understanding
          </p>
        </div>
      </div>
    </section>
  );
}
