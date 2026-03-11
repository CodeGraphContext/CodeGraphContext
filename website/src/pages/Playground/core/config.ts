export const SupportedLanguages = {
  TypeScript: 'typescript',
  JavaScript: 'javascript',
  Python: 'python',
  Java: 'java',
  C: 'c',
  Go: 'go',
  CPlusPlus: 'cpp',
  CSharp: 'c_sharp',
  Rust: 'rust',
  PHP: 'php',
  Swift: 'swift'
} as const;

export type SupportedLanguages = typeof SupportedLanguages[keyof typeof SupportedLanguages];

export function detectLanguage(filename: string): SupportedLanguages | null {
  const ext = filename.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'ts': case 'tsx': return SupportedLanguages.TypeScript;
    case 'js': case 'jsx': return SupportedLanguages.JavaScript;
    case 'py': return SupportedLanguages.Python;
    case 'java': return SupportedLanguages.Java;
    case 'c': case 'h': return SupportedLanguages.C;
    case 'go': return SupportedLanguages.Go;
    case 'cpp': case 'cc': case 'cxx': case 'hpp': return SupportedLanguages.CPlusPlus;
    case 'cs': return SupportedLanguages.CSharp;
    case 'rs': return SupportedLanguages.Rust;
    case 'php': return SupportedLanguages.PHP;
    case 'swift': return SupportedLanguages.Swift;
    default: return null;
  }
}
