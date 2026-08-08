/* Enhanced ComparisonTable component – UI improvements */
"use client";

import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import GlassCard from "./GlassCard";
import MagneticButton from "./MagneticButton";

// User‑friendly feature labels and updated data
const tableData = [
  {
    feature: "Smart Code Completion",
    copilot: { text: "Strong", status: "good" },
    cursor: { text: "Strong", status: "good" },
    cgc: { text: "Strong", status: "good" },
    highlight: false,
  },
  {
    // Call Graph & Imports → Dependency Tracking
    feature: "Dependency Tracking",
    copilot: { text: "No", status: "bad" },
    cursor: { text: "No", status: "bad" },
    cgc: { text: "Direct + Multi‑hops", status: "good" },
    highlight: true,
  },
  {
    // Context‑Aware Refactoring (keep name)
    feature: "Context‑Aware Refactoring",
    copilot: { text: "Limited", status: "warning" },
    cursor: { text: "Limited", status: "warning" },
    cgc: { text: "Via dependency tracing", status: "good" },
    highlight: false,
  },
  {
    feature: "Deep Codebase Understanding",
    copilot: { text: "Limited", status: "bad" },
    cursor: { text: "Partial", status: "warning" },
    cgc: { text: "Graph‑based analysis", status: "good" },
    highlight: false,
  },
  {
    // Cross‑File Tracing → Cross‑Repository Navigation
    feature: "Cross‑Repository Navigation",
    copilot: { text: "Very low", status: "bad" },
    cursor: { text: "Some", status: "warning" },
    cgc: { text: "Complete code view", status: "good" },
    highlight: false,
  },
  {
    // LLM Explainability → AI Explanation Quality
    feature: "AI Explanation Quality",
    copilot: { text: "Low", status: "bad" },
    cursor: { text: "Hallucinated", status: "warning" },
    cgc: { text: "Extremely accurate", status: "good" },
    highlight: true,
  },
  {
    feature: "Scalable Performance",
    copilot: { text: "Slows with size", status: "bad" },
    cursor: { text: "Slows with size", status: "bad" },
    cgc: { text: "Graph DB scaling", status: "good" },
    highlight: false,
  },
];

const StatusBadge = ({ status, text }: { status: string; text: string }) => {
  const getStyles = () => {
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
      className={`${getStyles()} border font-bold uppercase tracking-widest text-[0.55rem] sm:text-[0.65rem] px-2 sm:px-3 py-1.5 rounded-full min-w-[80px] text-center`}
    >
      <span className="mr-1 font-black">{getIcon()}</span>
      <span>{text}</span>
    </Badge>
  );
};

export default function ComparisonTable() {
  return (
    <section className="relative min-h-screen flex items-center justify-center bg-black py-24 px-4 overflow-hidden">
      <div className="container mx-auto max-w-7xl relative z-10">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-black mb-6 uppercase tracking-tight text-white">
            Why CodeGraphContext?
          </h2>
          <p className="text-sm font-mono text-gray-500 uppercase tracking-widest max-w-3xl mx-auto mb-4">
            Experience the next generation of AI‑powered code understanding with graph‑based intelligence.
          </p>
        </motion.div>

        {/* Desktop table */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="hidden md:block"
        >
          <GlassCard hoverable={false} className="p-2 bg-black border-white/20">
            <div className="overflow-x-auto rounded-2xl">
              <table className="min-w-full table-auto border-separate border-spacing-0">
                <thead className="bg-gray-900/50">
                  <tr>
                    <th className="p-2 text-left text-sm font-medium text-gray-300">Feature</th>
                    <th className="p-2 text-center"><img src="/logo-copilot.svg" alt="Copilot" className="h-5 mx-auto" /></th>
                    <th className="p-2 text-center"><img src="/logo-cursor.svg" alt="Cursor" className="h-5 mx-auto" /></th>
                    <th className="p-2 text-center"><img src="/logo-cgc.svg" alt="CodeGraphContext" className="h-5 mx-auto" /></th>
                  </tr>
                </thead>
                <tbody>
                   {tableData.map((row, idx) => (
                      <motion.tr
                        key={row.feature}
                        initial={{ opacity: 0, y: 10 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.3, delay: idx * 0.05 }}
                        className={`border-b border-white/10 hover:bg-purple-500/10 transition-colors ${idx % 2 === 0 ? "bg-black" : "bg-white/5"} p-1.5`}
                      >
                        <td className="p-2 text-sm font-medium text-gray-200">{row.feature}</td>
                        <td className="p-2 text-center"><StatusBadge status={row.copilot.status} text={row.copilot.text} /></td>
                        <td className="p-2 text-center"><StatusBadge status={row.cursor.status} text={row.cursor.text} /></td>
                        <td className="p-2 text-center">
                          <div className={`bg-gradient-to-r from-purple-600/30 to-indigo-600/30 p-1 rounded ${row.highlight ? "ring-2 ring-purple-400" : ""}`}> <StatusBadge status={row.cgc.status} text={row.cgc.text} /> </div>
                        </td>
                      </motion.tr>
                    ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </motion.div>

        {/* Mobile stacked cards */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="md:hidden space-y-4"
        >
          {tableData.map((row) => (
            <GlassCard key={row.feature} hoverable={false} className="p-4 bg-black border-white/20">
              <h3 className="text-sm font-medium text-gray-200 mb-2">{row.feature}</h3>
              <div className="grid grid-cols-2 gap-2 items-center">
                <span className="text-xs text-gray-400">Copilot</span>
                <StatusBadge status={row.copilot.status} text={row.copilot.text} />
                <span className="text-xs text-gray-400">Cursor</span>
                <StatusBadge status={row.cursor.status} text={row.cursor.text} />
                <span className="text-xs text-gray-400">CodeGraphContext</span>
                <div className="bg-gradient-to-r from-purple-600/30 to-indigo-600/30 p-1 rounded">
                  <StatusBadge status={row.cgc.status} text={row.cgc.text} />
                </div>
              </div>
            </GlassCard>
          ))}
        </motion.div>

        {/* Summary / Benefits */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="text-center mt-12"
        >
          <h3 className="text-xl font-semibold text-white mb-4">Key Benefits</h3>
          <ul className="text-sm text-gray-300 list-disc list-inside max-w-xl mx-auto mb-6">
            <li>Instant dependency tracking across repositories</li>
            <li>Deep graph‑based code understanding</li>
            <li>AI‑powered explanations with high accuracy</li>
            <li>Scales flawlessly to massive codebases</li>
          </ul>
          <MagneticButton href="#demo" className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 text-base font-bold rounded-lg transition-colors">
            Get Started
          </MagneticButton>
        </motion.div>
      </div>
    </section>
  );
}
