import type { PRGraphData, PRLink, PRNode } from "./pr-mock-data";

export type PRRiskLevel = "low" | "medium" | "high";

export interface PRKeySymbol {
  id: string;
  name: string;
  file: string;
  reason: string;
}

export interface PRCallPath {
  source: string;
  target: string;
  sourceName: string;
  targetName: string;
  type: string;
  label: string;
}

export interface PRInsights {
  riskLevel: PRRiskLevel;
  riskScore: number;
  summary: string;
  reviewVerdict: string;
  keySymbols: PRKeySymbol[];
  meaningfulCallPaths: PRCallPath[];
  signalNodeCount: number;
  noiseNodeCount: number;
  noiseRatio: number;
  meaningfulOrphanCount: number;
  falsePositiveOrphanCount: number;
  recommendations: string[];
  changedFileCount: number;
  primaryImpactCount: number;
}

function nodeName(id: string): string {
  return id.includes("::") ? id.split("::").pop() || id : id;
}

function diffAddsOrRemovesSymbol(diff: string, name: string, kind: "def" | "class"): boolean {
  const pattern = new RegExp(`^[+-]${kind}\\s+${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*[(:]`, "m");
  return pattern.test(diff);
}

function hasAnchorBodyEdit(diff: string): boolean {
  const lines = diff.split("\n").slice(1);
  for (const line of lines) {
    if (/^\+def\s/.test(line) || /^\+class\s/.test(line)) return false;
    if (/^[-+]\s{4,}/.test(line)) return true;
  }
  return false;
}

function isLikelyNoiseNode(node: PRNode, directNodes: PRNode[]): boolean {
  if (node.prZone !== "direct") return false;

  const sameDiffCount = directNodes.filter(
    (n) => n.gitDiff && node.gitDiff && n.gitDiff === node.gitDiff
  ).length;

  const diff = node.gitDiff || "";

  if (node.type === "Variable") return sameDiffCount > 1;

  if (node.type === "Function" || node.type === "Class") {
    const diffHeaderMatch = diff.match(/^@@[^\n]*@@[^\n]*/)?.[0] || "";
    const isHunkAnchor =
      diffHeaderMatch.includes(`def ${node.name}`) ||
      diffHeaderMatch.includes(`class ${node.name}`);

    const addedOrChanged =
      diffAddsOrRemovesSymbol(diff, node.name, "def") ||
      diffAddsOrRemovesSymbol(diff, node.name, "class") ||
      (isHunkAnchor && hasAnchorBodyEdit(diff));

    if (!addedOrChanged && sameDiffCount > 1) return true;
    if (node.name === "<module>" && !diff.startsWith("@@ -0,0")) return true;
  }

  return false;
}

function isMeaningfulOrphan(node: PRNode, links: PRLink[]): boolean {
  if (!node.isOrphan) return false;
  if (node.status === "added") return false;
  if (node.prZone === "primary" || node.prZone === "secondary") return false;
  if (node.type === "Variable") return false;
  if (node.name.startsWith("test_")) return false;
  const hasOutgoing = links.some(
    (l) => (typeof l.source === "object" ? (l.source as any).id : l.source) === node.id
  );
  return !hasOutgoing;
}

export function computePRInsights(data: PRGraphData): PRInsights {
  const nodes = data.nodes || [];
  const links = data.links || [];
  const directNodes = nodes.filter((n) => n.prZone === "direct");
  const primaryNodes = nodes.filter((n) => n.prZone === "primary");

  const signalNodes = directNodes.filter((n) => !isLikelyNoiseNode(n, directNodes));
  const noiseNodes = directNodes.filter((n) => isLikelyNoiseNode(n, directNodes));
  const noiseRatio = directNodes.length
    ? Math.round((noiseNodes.length / directNodes.length) * 100)
    : 0;

  const addedSymbols = signalNodes.filter((n) => n.status === "added");
  const modifiedSymbols = signalNodes.filter(
    (n) => n.status === "modified" && (n.type === "Function" || n.type === "Class")
  );

  const keySymbols: PRKeySymbol[] = [];
  const seen = new Set<string>();

  for (const node of [...addedSymbols, ...modifiedSymbols]) {
    if (seen.has(node.id)) continue;
    if (isLikelyNoiseNode(node, directNodes)) continue;
    seen.add(node.id);
    keySymbols.push({
      id: node.id,
      name: node.name,
      file: node.file,
      reason:
        node.status === "added"
          ? "New symbol added in this PR"
          : "Directly modified function/class",
    });
  }

  for (const link of links) {
    const targetId = typeof link.target === "object" ? (link.target as any).id : link.target;
    const target = nodes.find((n) => n.id === targetId);
    if (!target || target.prZone !== "direct") continue;
    if (seen.has(target.id)) continue;
    if (isLikelyNoiseNode(target, directNodes)) continue;
    seen.add(target.id);
    keySymbols.push({
      id: target.id,
      name: target.name,
      file: target.file,
      reason: "Downstream target of a call edge in the impact graph",
    });
  }

  const meaningfulCallPaths: PRCallPath[] = links
    .filter((l) => {
      const sId = typeof l.source === "object" ? (l.source as any).id : l.source;
      const tId = typeof l.target === "object" ? (l.target as any).id : l.target;
      const source = nodes.find((n) => n.id === sId);
      const target = nodes.find((n) => n.id === tId);
      if (!source || !target) return false;
      const touchesChange =
        (source.prZone === "direct" && !isLikelyNoiseNode(source, directNodes)) ||
        (target.prZone === "direct" && !isLikelyNoiseNode(target, directNodes));
      return touchesChange && (source.prZone !== "none" || target.prZone !== "none");
    })
    .slice(0, 8)
    .map((l) => {
      const sId = typeof l.source === "object" ? (l.source as any).id : l.source;
      const tId = typeof l.target === "object" ? (l.target as any).id : l.target;
      const source = nodes.find((n) => n.id === sId)!;
      const target = nodes.find((n) => n.id === tId)!;
      const srcLabel =
        source.prZone === "primary"
          ? `${source.name} (caller)`
          : source.name.startsWith("test_")
            ? `${source.name} (test)`
            : source.name;
      const tgtLabel =
        target.prZone === "direct" ? `${target.name} (changed)` : target.name;
      return {
        source: sId,
        target: tId,
        sourceName: source.name,
        targetName: target.name,
        type: l.type,
        label: `${srcLabel} → ${tgtLabel}`,
      };
    });

  const orphanNodes = nodes.filter((n) => n.isOrphan);
  const meaningfulOrphans = orphanNodes.filter((n) => isMeaningfulOrphan(n, links));
  const falsePositiveOrphans = orphanNodes.filter((n) => !isMeaningfulOrphan(n, links));

  const violations = links.filter((l) => l.isViolation).length;
  const highComplexity = signalNodes.filter((n) => (n.complexityDelta || 0) >= 10).length;
  const signatureChanges = signalNodes.filter((n) => n.signatureChanged).length;

  let riskScore = 0;
  riskScore += Math.min(primaryNodes.length * 2, 30);
  riskScore += meaningfulOrphans.length * 5;
  riskScore += violations * 15;
  riskScore += highComplexity * 10;
  riskScore += signatureChanges * 20;
  riskScore += Math.min(keySymbols.length * 3, 25);
  riskScore = Math.min(100, riskScore);

  let riskLevel: PRRiskLevel = "low";
  if (riskScore >= 55) riskLevel = "high";
  else if (riskScore >= 25) riskLevel = "medium";

  const recommendations: string[] = [];
  if (noiseRatio >= 40) {
    recommendations.push(
      "Graph contains significant noise — focus on key symbols and call paths below rather than raw node count."
    );
  }
  if (falsePositiveOrphans.length > 0) {
    recommendations.push(
      `${falsePositiveOrphans.length} orphan flag(s) look like indexing artifacts (e.g. unchanged tests/variables), not dead code.`
    );
  }
  if (meaningfulOrphans.length > 0) {
    recommendations.push(
      `Review ${meaningfulOrphans.length} symbol(s) that may have lost all callers after this change.`
    );
  }
  if (primaryNodes.length > 0) {
    recommendations.push(
      `Verify behavior for ${primaryNodes.length} upstream caller(s) in the primary impact zone.`
    );
  }
  if (violations > 0) {
    recommendations.push("Resolve architectural boundary violations before merge.");
  }
  if (signatureChanges > 0) {
    recommendations.push("Audit all callers affected by API signature changes.");
  }
  if (recommendations.length === 0) {
    recommendations.push("Low blast radius — standard review should suffice.");
  }

  const summary =
    keySymbols.length <= 3
      ? `Focused change: ${keySymbols.length} key symbol(s) across ${data.files?.length || 0} file(s).`
      : `Broad change: ${keySymbols.length} key symbol(s), ${primaryNodes.length} upstream caller(s), ${data.files?.length || 0} file(s).`;

  const reviewVerdict =
    riskLevel === "low"
      ? "Safe to fast-track — localized change with limited downstream impact."
      : riskLevel === "medium"
        ? "Standard review — check call paths and tests touching changed symbols."
        : "Deep review required — wide blast radius or high-risk flags detected.";

  return {
    riskLevel,
    riskScore,
    summary,
    reviewVerdict,
    keySymbols: keySymbols.slice(0, 12),
    meaningfulCallPaths,
    signalNodeCount: signalNodes.length,
    noiseNodeCount: noiseNodes.length,
    noiseRatio,
    meaningfulOrphanCount: meaningfulOrphans.length,
    falsePositiveOrphanCount: falsePositiveOrphans.length,
    recommendations,
    changedFileCount: data.files?.length || 0,
    primaryImpactCount: primaryNodes.length,
  };
}

export function getNodeLabel(id: string): string {
  return nodeName(id);
}
