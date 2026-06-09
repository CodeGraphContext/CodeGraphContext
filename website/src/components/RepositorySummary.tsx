import React, { useMemo } from "react";

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
  isIndexed?: boolean; // ✅ added for requirement: show after indexing completes
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

    const files =
      graphData.files?.length ?? Object.keys(fileContents).length;

    const folders = nodes.filter((n) => n.type === "Directory").length;
    const functions = nodes.filter((n) => n.type === "Function").length;
    const classes = nodes.filter((n) => n.type === "Class").length;
    const imports = links.filter((l) => l.type === "IMPORTS").length;

    const largeFiles = Object.values(fileContents).filter(
      (content) =>
        typeof content === "string" &&
        content.length > largeFileThreshold * 50
    ).length;

    return {
      files,
      folders,
      functions,
      classes,
      imports,
      largeFiles,
    };
  }, [graphData, largeFileThreshold]);

  // ❌ Requirement: only show AFTER indexing completes
  if (!isIndexed) {
    return (
      <div className="mt-6 mb-4 rounded-xl border border-border bg-background/80 p-4 text-sm text-muted-foreground">
        Indexing repository...
      </div>
    );
  }

  const circularDependencies = graphData.circularDependencies;
  const unusedExports = graphData.unusedExports;

  return (
    <div className="mt-6 mb-4 rounded-xl border border-border bg-background/80 backdrop-blur-sm p-4">
      <h2 className="mb-4 text-lg font-semibold">
        Repository Analysis Summary
      </h2>

      {/* Core Metrics */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatCard label="Files" value={summary.files} />
        <StatCard label="Folders" value={summary.folders} />
        <StatCard label="Functions" value={summary.functions} />
        <StatCard label="Classes" value={summary.classes} />
        <StatCard label="Imports" value={summary.imports} />
      </div>

      {/* Issues */}
      <div className="border-t pt-4">
        <h3 className="mb-3 font-medium">Potential Issues</h3>

        <div className="space-y-2 text-sm">
          <div>
            ⚠ Circular Dependencies:{" "}
            {circularDependencies !== undefined
              ? circularDependencies
              : "—"}
          </div>

          <div>
            ⚠ Large Files: {summary.largeFiles}
          </div>

          <div>
            ⚠ Unused Exports:{" "}
            {unusedExports !== undefined
              ? unusedExports
              : "—"}
          </div>
        </div>
      </div>
    </div>
  );
};

interface StatCardProps {
  label: string;
  value: number;
}

const StatCard: React.FC<StatCardProps> = ({ label, value }) => (
  <div className="rounded-lg border border-border p-3 text-center">
    <div className="text-2xl font-bold">
      {value.toLocaleString()}
    </div>
    <div className="text-sm text-muted-foreground">{label}</div>
  </div>
);

export default RepositorySummary;