export function extractDeclarationSignature(line: string): string | undefined {
  const trimmed = line.trim();
  const match = /^(def|class|function)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\([^)]*\))?/.exec(trimmed);
  if (!match) {
    return undefined;
  }
  return `${match[1]} ${match[2]}${match[3] ?? ""}`;
}
