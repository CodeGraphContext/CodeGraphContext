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

  if (!isIndexed) {
    return (
      <div className="mt-1 mb-2 w-full rounded-xl border border-border bg-background p-3 shadow-sm">
        Indexing repository...
      </div>
    );
  }

  const circularDependencies = graphData.circularDependencies;
  const unusedExports = graphData.unusedExports;

  return (
    <div className="mt-1 mb-2 w-full rounded-xl border border-border/60 bg-background p-4 shadow-sm">
      <div className="mb-3">
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          Repository Analysis
        </h2>

        <p className="mt-1 text-sm text-muted-foreground">
          Quick overview of the indexed repository structure and potential
          maintainability concerns.
        </p>
      </div>

      {/* Repository Overview */}
      <div className="mb-3">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Repository Overview
        </h3>

        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          <StatCard icon="📄" label="Files" value={summary.files} />
          <StatCard icon="📁" label="Folders" value={summary.folders} />
          <StatCard icon="⚙️" label="Functions" value={summary.functions} />
          <StatCard icon="🏗️" label="Classes" value={summary.classes} />
          <StatCard icon="🔗" label="Imports" value={summary.imports} />
        </div>
      </div>

      {/* Analysis Warnings */}
      <div className="border-t border-border pt-3">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Analysis Warnings
        </h3>

        <div className="grid gap-2 md:grid-cols-3">
          <IssueCard
            title="Circular Dependencies"
            value={
              circularDependencies !== undefined
                ? circularDependencies.toString()
                : "Backend support pending"
            }
          />

          <IssueCard
            title="Large Files"
            value={summary.largeFiles.toString()}
          />

          <IssueCard
            title="Unused Exports"
            value={
              unusedExports !== undefined
                ? unusedExports.toString()
                : "Backend support pending"
            }
          />
        </div>
      </div>
    </div>
  );
};

interface StatCardProps {
  label: string;
  value: number;
  icon: string;
}

const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  icon,
}) => (
  <div className="rounded-lg border border-border bg-card p-3 text-center shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md">
    <div className="mb-1 text-xl">
      {icon}
    </div>

    <div className="text-2xl font-bold">
      {value.toLocaleString()}
    </div>

    <div className="text-xs font-medium text-muted-foreground">
      {label}
    </div>
  </div>
);

interface IssueCardProps {
  title: string;
  value: string;
}

const IssueCard: React.FC<IssueCardProps> = ({
  title,
  value,
}) => (
  <div className="rounded-lg border border-yellow-500/30 bg-yellow-50 p-3 shadow-sm dark:bg-yellow-500/5">
    <div className="mb-1 text-sm font-semibold">
      ⚠ {title}
    </div>

    <div className="text-xs text-muted-foreground">
      {value}
    </div>
  </div>
);

export default RepositorySummary;