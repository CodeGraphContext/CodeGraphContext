"use client";

import type { ComponentType } from "react";

import { motion } from "framer-motion";
import { ArrowRight, AlertTriangle, Check, Github, MousePointer2, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import GlassCard from "./GlassCard";
import SectionDivider from "./SectionDivider";

type StatusLevel = "good" | "warning" | "bad";

type ComparisonRow = {
  feature: string;
  note?: string;
  highlight?: boolean;
  copilot: { text: string; status: StatusLevel };
  cursor: { text: string; status: StatusLevel };
  cgc: { text: string; status: StatusLevel };
};

const tableData: ComparisonRow[] = [
  {
    feature: "Code Completion",
    note: "Inline suggestions for everyday coding flow",
    copilot: { text: "Strong", status: "good" },
    cursor: { text: "Strong", status: "good" },
    cgc: { text: "Strong", status: "good" },
  },
  {
    feature: "Refactoring Guidance",
    note: "Advice that keeps context and structure aligned",
    copilot: { text: "Limited to context length", status: "warning" },
    cursor: { text: "Limited to context length", status: "warning" },
    cgc: { text: "Via dependency tracing", status: "good" },
  },
  {
    feature: "Codebase Understanding",
    note: "How well the tool understands the full repo",
    highlight: true,
    copilot: { text: "Limited", status: "bad" },
    cursor: { text: "Partial local context", status: "warning" },
    cgc: { text: "Deep graph-based", status: "good" },
  },
  {
    feature: "Dependency Tracking",
    note: "Imports, call paths, and multi-hop links",
    highlight: true,
    copilot: { text: "No", status: "bad" },
    cursor: { text: "No", status: "bad" },
    cgc: { text: "Direct + multi-hop", status: "good" },
  },
  {
    feature: "Cross-Repository Navigation",
    note: "Move across files and projects without losing context",
    highlight: true,
    copilot: { text: "Very low", status: "bad" },
    cursor: { text: "Some", status: "warning" },
    cgc: { text: "Complete code paths", status: "good" },
  },
  {
    feature: "AI Explanation Quality",
    note: "Whether the reasoning stays grounded in the graph",
    highlight: true,
    copilot: { text: "Low", status: "bad" },
    cursor: { text: "Can drift", status: "warning" },
    cgc: { text: "Highly grounded", status: "good" },
  },
  {
    feature: "Performance on Large Codebases",
    note: "How the tool holds up as the repo grows",
    copilot: { text: "Slows with size", status: "bad" },
    cursor: { text: "Slows with size", status: "bad" },
    cgc: { text: "Scales with graph DB", status: "good" },
  },
  {
    feature: "Multi-language Extensibility",
    note: "How easily the system expands to other stacks",
    copilot: { text: "Strong", status: "good" },
    cursor: { text: "Strong", status: "good" },
    cgc: { text: "Work in progress", status: "warning" },
  },
  {
    feature: "Setup Time for New Projects",
    note: "How quickly you can start a fresh codebase",
    copilot: { text: "Low", status: "good" },
    cursor: { text: "Moderate", status: "warning" },
    cgc: { text: "Fast once bundled", status: "good" },
  },
];

const columnMeta = [
  { label: "GitHub Copilot", icon: Github, accent: "from-cyan-400/20 to-cyan-400/5" },
  { label: "Cursor", icon: MousePointer2, accent: "from-sky-400/20 to-sky-400/5" },
  { label: "CodeGraphContext", icon: Sparkles, accent: "from-purple-500/25 to-cyan-500/10", recommended: true },
] as const;

const StatusBadge = ({ status, text }: { status: StatusLevel; text: string }) => {
  const styles = {
    good: "bg-cyan-500/10 text-cyan-300 border-cyan-400/20",
    warning: "bg-amber-500/10 text-amber-300 border-amber-400/20",
    bad: "bg-white/5 text-gray-500 border-white/10",
  } as const;

  const icon = {
    good: <Check className="h-3.5 w-3.5 shrink-0" />,
    warning: <AlertTriangle className="h-3.5 w-3.5 shrink-0" />,
    bad: <X className="h-3.5 w-3.5 shrink-0" />,
  } as const;

  return (
    <Badge
      className={`
        inline-flex min-h-11 min-w-[8.75rem] max-w-full items-center justify-center gap-1.5
        rounded-full border px-3 py-2 text-center text-[0.58rem] font-bold uppercase tracking-[0.18em]
        leading-tight transition-colors duration-300 sm:min-w-[9.75rem] sm:text-[0.64rem]
        whitespace-normal ${styles[status]}
      `}
    >
      {icon[status]}
      <span>{text}</span>
    </Badge>
  );
};

const ColumnHeader = ({
  label,
  icon: Icon,
  accent,
  recommended,
}: {
  label: string;
  icon: ComponentType<{ className?: string }>;
  accent: string;
  recommended?: boolean;
}) => {
  return (
    <th className={`sticky top-0 z-20 p-4 text-left align-bottom ${recommended ? "bg-gradient-to-b " + accent : "bg-black"}`}>
      <div className={`rounded-2xl border border-white/10 px-4 py-3 ${recommended ? "bg-white/5 shadow-[0_0_30px_rgba(168,85,247,0.12)]" : "bg-white/[0.03]"}`}>
        <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.28em] text-white sm:text-xs">
          <Icon className="h-4 w-4" />
          <span>{label}</span>
        </div>
        {recommended && (
          <span className="mt-2 inline-flex rounded-full border border-purple-500/30 bg-purple-500/15 px-2.5 py-1 text-[8px] font-black uppercase tracking-[0.3em] text-purple-200">
            Recommended
          </span>
        )}
      </div>
    </th>
  );
};

const MobileComparisonCard = ({ row, index }: { row: ComparisonRow; index: number }) => {
  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.35, delay: index * 0.04 }}
      className={`rounded-3xl border p-4 shadow-lg transition-transform duration-300 hover:-translate-y-0.5 ${
        row.highlight
          ? "border-purple-500/30 bg-gradient-to-b from-purple-500/10 to-white/[0.02]"
          : "border-white/10 bg-white/[0.03]"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-black uppercase tracking-[0.24em] text-white">{row.feature}</p>
          {row.note && (
            <p className="mt-2 max-w-[26rem] text-[11px] font-mono uppercase tracking-widest text-gray-500">
              {row.note}
            </p>
          )}
        </div>
        {row.highlight && (
          <Badge className="rounded-full border border-purple-500/30 bg-purple-500/15 px-3 py-1 text-[8px] font-black uppercase tracking-[0.28em] text-purple-200">
            Key
          </Badge>
        )}
      </div>

      <div className="mt-4 grid gap-3">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-black/40 p-3">
            <p className="text-[9px] font-black uppercase tracking-[0.28em] text-gray-500">Copilot</p>
            <div className="mt-2 flex justify-center">
              <StatusBadge status={row.copilot.status} text={row.copilot.text} />
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/40 p-3">
            <p className="text-[9px] font-black uppercase tracking-[0.28em] text-gray-500">Cursor</p>
            <div className="mt-2 flex justify-center">
              <StatusBadge status={row.cursor.status} text={row.cursor.text} />
            </div>
          </div>
          <div className="rounded-2xl border border-purple-500/20 bg-purple-500/8 p-3">
            <p className="text-[9px] font-black uppercase tracking-[0.28em] text-purple-200">CodeGraphContext</p>
            <div className="mt-2 flex justify-center">
              <StatusBadge status={row.cgc.status} text={row.cgc.text} />
            </div>
          </div>
        </div>
      </div>
    </motion.article>
  );
};

export default function ComparisonTable() {
  return (
    <section className="relative min-h-screen overflow-hidden bg-black px-4 py-24">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none" />

      <div className="container relative z-10 mx-auto max-w-7xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center"
        >
          <h2 className="py-2 text-3xl font-black uppercase tracking-tight text-white sm:text-4xl md:text-5xl">
            Why CodeGraphContext?
          </h2>
          <p className="mx-auto mb-10 max-w-3xl text-sm font-mono uppercase tracking-[0.28em] text-gray-500 sm:mb-12">
            Compare repo understanding, dependency tracing, and explanation quality at a glance.
          </p>
        </motion.div>

        <SectionDivider className="mb-10" />

        <motion.div
          initial={{ opacity: 0, y: 34 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.55, delay: 0.1 }}
          className="hidden lg:block"
        >
          <GlassCard hoverable={false} className="border border-white/15 bg-black p-2 shadow-2xl shadow-black/40">
            <div className="overflow-hidden rounded-[1.5rem] border border-white/10">
              <table className="w-full min-w-[980px] border-collapse table-fixed">
                <thead>
                  <tr className="border-b border-white/10 bg-black/90">
                    <th className="sticky top-0 z-20 bg-black p-4 text-left align-bottom">
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
                        <div className="text-[10px] font-black uppercase tracking-[0.28em] text-white sm:text-xs">
                          Feature
                        </div>
                        <div className="mt-2 text-[9px] font-mono uppercase tracking-[0.3em] text-gray-500">
                          Shorter, scan-friendly labels
                        </div>
                      </div>
                    </th>
                    {columnMeta.map((column) => (
                      <ColumnHeader
                        key={column.label}
                        label={column.label}
                        icon={column.icon}
                        accent={column.accent}
                        recommended={column.recommended}
                      />
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.map((row, index) => (
                    <motion.tr
                      key={row.feature}
                      initial={{ opacity: 0, y: 18 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true, margin: "-80px" }}
                      transition={{ duration: 0.35, delay: index * 0.035 }}
                        className={`group border-b border-white/10 transition-colors duration-300 hover:bg-white/[0.03] ${
                        row.highlight ? "bg-purple-500/5" : index % 2 === 0 ? "bg-black" : "bg-white/[0.015]"
                      }`}
                    >
                      <td className="p-4 align-top">
                        <div className="rounded-2xl border border-white/10 bg-black/30 px-4 py-3">
                          <p className="text-sm font-bold uppercase tracking-[0.22em] text-white">
                            {row.feature}
                          </p>
                          {row.note && (
                            <p className="mt-2 text-[10px] font-mono uppercase tracking-[0.28em] text-gray-500">
                              {row.note}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="p-4 align-middle">
                        <div className="flex justify-center">
                          <StatusBadge status={row.copilot.status} text={row.copilot.text} />
                        </div>
                      </td>
                      <td className="p-4 align-middle">
                        <div className="flex justify-center">
                          <StatusBadge status={row.cursor.status} text={row.cursor.text} />
                        </div>
                      </td>
                      <td className="bg-gradient-to-b from-purple-500/[0.08] to-white/[0.02] p-4 align-middle">
                        <div className="flex justify-center">
                          <StatusBadge status={row.cgc.status} text={row.cgc.text} />
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </motion.div>

        <div className="grid gap-4 lg:hidden">
          {tableData.map((row, index) => (
            <MobileComparisonCard key={row.feature} row={row} index={index} />
          ))}
        </div>

        <GlassCard className="mt-10 border border-white/10 bg-black/85 p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[10px] font-black uppercase tracking-[0.32em] text-purple-300">
                Quick takeaway
              </p>
              <h3 className="mt-3 text-2xl font-black uppercase tracking-tight text-white sm:text-3xl">
                Understand the whole repo, not just the next autocomplete.
              </h3>
              <p className="mt-4 max-w-2xl text-sm leading-relaxed text-gray-400">
                CodeGraphContext keeps the important parts visible: dependency paths, cross-file relationships,
                and the reasoning trail behind changes. That means faster onboarding, clearer debugging, and less guesswork.
              </p>

              <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  "Map dependencies instantly",
                  "Trace behavior across files",
                  "Explain architectural decisions",
                  "Scale to bigger repos cleanly",
                ].map((item) => (
                  <div
                    key={item}
                    className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-xs font-black uppercase tracking-[0.2em] text-white"
                  >
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="flex shrink-0 flex-col gap-3 sm:flex-row lg:flex-col">
              <Button
                asChild
                className="h-12 rounded-full bg-purple-600 px-6 text-xs font-black uppercase tracking-[0.28em] text-white shadow-[0_0_20px_rgba(168,85,247,0.35)] hover:bg-purple-500"
              >
                <a href="#installation">
                  Get Started
                  <ArrowRight className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button
                variant="outline"
                asChild
                className="h-12 rounded-full border-white/20 px-6 text-xs font-black uppercase tracking-[0.28em] text-white hover:bg-white/5"
              >
                <a href="https://github.com/CodeGraphContext/CodeGraphContext" target="_blank" rel="noopener noreferrer">
                  View Source
                </a>
              </Button>
            </div>
          </div>
        </GlassCard>
      </div>
    </section>
  );
}
