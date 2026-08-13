import React, { useMemo } from "react";
import { FileCode2, FolderOpen, FunctionSquare, Braces, Link2, AlertTriangle, Info } from "lucide-react";

interface GraphNode {
  id?: string;
  type?: string;
  name?: string;
}

interface GraphLink {
  source?: string;
  target?: string;
  type?: string;
}

interface RepositoryGraphData {
  nodes?: GraphNode[];
  links?: GraphLink[];
  files?: string[];
  fileContents?: Record<string, string>;

  circularDependencies?: number;
  unusedExports?: number;
}

interface RepositorySummaryProps {
  graphData: RepositoryGraphData;
  largeFileThreshold?: number;
  isIndexed?: boolean;
}

const RepositorySummary: React.FC<RepositorySummaryProps> = ({
  graphData,
  largeFileThreshold = 500,
  isIndexed = false,
}) => {
  const summary = useMemo(() => {
    const nodes = graphData.nodes ?? [];
    const links = graphData.links ?? [];
    const fileContents = graphData.fileContents ?? {};

    const files = graphData.files?.length ?? Object.keys(fileContents).length;
    const folders = nodes.filter((n) => n.type === "Directory").length;
    const functions = nodes.filter((n) => n.type === "Function").length;
    const classes = nodes.filter((n) => n.type === "Class").length;
    const imports = links.filter((l) => l.type === "IMPORTS").length;

    const largeFiles = Object.values(fileContents).filter(
      (content) =>
        typeof content === "string" && content.length > largeFileThreshold * 50
    ).length;

    return { files, folders, functions, classes, imports, largeFiles };
  }, [graphData, largeFileThreshold]);

  if (!isIndexed) {
    return (
      <div className="inline-flex items-center gap-2 px-4 py-2 bg-black/60 backdrop-blur-xl border border-white/10 rounded-full shadow-2xl">
        <div className="w-3 h-3 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">Indexing Repository</span>
      </div>
    );
  }

  const circularDependencies = graphData.circularDependencies;
  const unusedExports = graphData.unusedExports;

  return (
    <div className="flex flex-col gap-2 w-full max-w-4xl pointer-events-none">
      {/* Main Stats Row */}
      <div className="flex items-center gap-2 pointer-events-auto overflow-x-auto custom-scrollbar pb-2 md:pb-0">
        <div className="flex items-center bg-black/50 backdrop-blur-3xl border border-white/10 rounded-2xl p-1 shadow-2xl">
          <StatPill icon={<FileCode2 />} label="Files" value={summary.files} />
          <Divider />
          <StatPill icon={<FolderOpen />} label="Folders" value={summary.folders} />
          <Divider />
          <StatPill icon={<FunctionSquare />} label="Functions" value={summary.functions} />
          <Divider />
          <StatPill icon={<Braces />} label="Classes" value={summary.classes} />
          <Divider />
          <StatPill icon={<Link2 />} label="Imports" value={summary.imports} />
        </div>
      </div>

      {/* Warnings Row */}
      <div className="flex items-center gap-2 pointer-events-auto">
        <WarningBadge
          title="Circular Dependencies"
          value={circularDependencies !== undefined ? circularDependencies : null}
          isWarning={circularDependencies !== undefined && circularDependencies > 0}
        />
        <WarningBadge
          title="Large Files"
          value={summary.largeFiles}
          isWarning={summary.largeFiles > 0}
        />
        <WarningBadge
          title="Unused Exports"
          value={unusedExports !== undefined ? unusedExports : null}
          isWarning={unusedExports !== undefined && unusedExports > 0}
        />
      </div>
    </div>
  );
};

const Divider = () => <div className="w-px h-6 bg-white/10 mx-1" />;

const StatPill = ({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) => (
  <div className="flex items-center gap-3 px-4 py-2 rounded-xl hover:bg-white/5 transition-colors group">
    <div className="text-gray-500 group-hover:text-cyan-400 transition-colors [&>svg]:w-4 [&>svg]:h-4">
      {icon}
    </div>
    <div className="flex flex-col">
      <span className="text-[14px] font-black text-white leading-tight">{value.toLocaleString()}</span>
      <span className="text-[9px] font-bold uppercase tracking-widest text-gray-500 leading-tight">{label}</span>
    </div>
  </div>
);

const WarningBadge = ({ title, value, isWarning }: { title: string; value: number | null; isWarning: boolean }) => {
  if (value === null) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 bg-black/40 backdrop-blur-xl border border-white/5 rounded-full shadow-lg">
        <Info className="w-3 h-3 text-gray-600" />
        <span className="text-[9px] font-bold uppercase tracking-widest text-gray-500">{title}: Pending</span>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 backdrop-blur-xl border rounded-full shadow-lg transition-colors ${
      isWarning ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' : 'bg-green-500/10 border-green-500/20 text-green-500'
    }`}>
      {isWarning ? <AlertTriangle className="w-3 h-3" /> : <div className="w-1.5 h-1.5 rounded-full bg-green-500" />}
      <span className="text-[9px] font-bold uppercase tracking-widest">
        {value} {title}
      </span>
    </div>
  );
};

export default RepositorySummary;