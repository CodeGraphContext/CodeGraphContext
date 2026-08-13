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

const StatusBadge = ({ status, text, isCGC }: { status: string; text: string; isCGC?: boolean }) => {
  const getStyles = () => {
    if (isCGC) {
      // For CodeGraphContext, it's always the purple pill
      return "bg-[#1e1138] text-cyan-400 border border-purple-500/30 w-full hover:bg-[#251545] transition-colors";
    }
    switch (status) {
      case "good":
        return "bg-[#042025] text-teal-400 border-none";
      case "warning":
        return "bg-[#291c06] text-amber-500 border-none";
      case "bad":
        return "bg-[#141414] text-gray-500 border-none";
      default:
        return "bg-black text-gray-500 border-white/10";
    }
  };
  const getIcon = () => {
    switch (status) {
      case "good":
        return "✓";
      case "warning":
        return "▲";
      case "bad":
        return "✕";
      default:
        return "";
    }
  };
  return (
    <Badge
      className={`${getStyles()} font-bold uppercase tracking-widest text-[0.65rem] px-3 py-2 rounded-full min-w-[100px] text-center justify-center flex items-center shadow-none`}
    >
      <span className="mr-1.5 font-black text-[0.55rem]">{getIcon()}</span>
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
          className="hidden md:block w-full"
        >
          <div className="bg-[#050505] border border-white/10 rounded-2xl overflow-hidden shadow-2xl mx-auto w-full max-w-[1000px]">
            <table className="w-full table-auto border-collapse">
              <thead className="bg-[#0a0a0a] border-b border-white/10">
                <tr>
                  <th className="px-6 py-5 text-left text-sm font-bold text-gray-300 w-1/3">Feature</th>
                  <th className="px-4 py-5 text-center w-1/6">
                    <div className="w-5 h-5 mx-auto rounded-full bg-[#2a3862] text-[10px] font-bold flex items-center justify-center text-blue-300">C</div>
                  </th>
                  <th className="px-4 py-5 text-center w-1/6">
                    <div className="w-5 h-5 mx-auto rounded-full bg-[#1b3d2f] text-[10px] font-bold flex items-center justify-center text-green-300">R</div>
                  </th>
                  <th className="px-6 py-5 text-center w-1/3">
                    <div className="flex items-center justify-center gap-2">
                      <span className="font-bold text-white text-sm">CodeGraphContext</span>
                    </div>
                  </th>
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
                      className={`border-b border-white/5 hover:bg-white/[0.02] transition-colors`}
                    >
                      <td className="px-6 py-4 text-sm font-semibold text-gray-200">{row.feature}</td>
                      <td className="px-4 py-4 text-center">
                        <StatusBadge status={row.copilot.status} text={row.copilot.text} />
                      </td>
                      <td className="px-4 py-4 text-center">
                        <StatusBadge status={row.cursor.status} text={row.cursor.text} />
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className={`p-0.5 rounded-full ${row.highlight ? "bg-gradient-to-r from-purple-500/50 to-indigo-500/50" : ""}`}>
                           <StatusBadge status={row.cgc.status} text={row.cgc.text} isCGC={true} />
                        </div>
                      </td>
                    </motion.tr>
                  ))}
              </tbody>
            </table>
          </div>
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

      </div>
    </section>
  );
}
