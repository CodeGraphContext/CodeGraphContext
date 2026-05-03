import * as vscode from "vscode";
import { CgcService } from "../mcp/service";
import { DeadCodeEntry } from "../types/cgc";

function symbolAtPosition(document: vscode.TextDocument, position: vscode.Position): string | undefined {
  const range = document.getWordRangeAtPosition(position, /[A-Za-z_][A-Za-z0-9_]*/);
  return range ? document.getText(range) : undefined;
}

function collectDefinitionLines(document: vscode.TextDocument): Array<{ line: number; symbol: string }> {
  const out: Array<{ line: number; symbol: string }> = [];
  for (let i = 0; i < document.lineCount; i += 1) {
    const text = document.lineAt(i).text.trim();
    const match = /^(def|class|function|async def)\s+([A-Za-z_][A-Za-z0-9_]*)/.exec(text);
    if (match) {
      out.push({ line: i, symbol: match[2] });
    }
  }
  return out;
}

// ──────────────────────────────────────────────────────────────────────────
// CodeLens: simple two-lens-per-definition approach.
// Each definition gets a "Complexity | N callers" line fetched lazily.
// Complexity/callers are resolved once per document via onDidChangeCodeLenses.
// ──────────────────────────────────────────────────────────────────────────
const lensCache = new Map<string, { complexity?: number; callers: number }>();

export class CgcCodeLensProvider implements vscode.CodeLensProvider {
  private readonly _onDidChange = new vscode.EventEmitter<void>();
  public readonly onDidChangeCodeLenses = this._onDidChange.event;

  constructor(private readonly service: CgcService) {}

  provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
    const defs = collectDefinitionLines(document);
    const lenses: vscode.CodeLens[] = [];

    for (const def of defs) {
      const range = new vscode.Range(def.line, 0, def.line, 0);
      const cacheKey = `${document.uri.toString()}::${def.symbol}`;
      const cached = lensCache.get(cacheKey);

      const threshold = vscode.workspace.getConfiguration("cgc").get<number>("complexityWarningThreshold", 10);
      const cc = cached?.complexity;
      const callers = cached?.callers ?? 0;

      const complexTitle = cc !== undefined
        ? `CGC: Complexity ${cc}${cc > threshold ? " ⚠️" : ""}`
        : "CGC: Complexity";
      const callersTitle = `CGC: Callers (${callers})`;

      lenses.push(
        new vscode.CodeLens(range, {
          title: complexTitle,
          command: "cgc.showComplexityAtSymbol",
          arguments: [document.uri, def.symbol]
        }),
        new vscode.CodeLens(range, {
          title: callersTitle,
          command: "cgc.showCallersAtSymbol",
          arguments: [document.uri, def.symbol]
        })
      );
    }

    // Kick off async resolution — fires onDidChangeCodeLenses when done
    this._fetchAll(document).catch(() => {});
    return lenses;
  }

  private _fetchingDocs = new Set<string>();

  private async _fetchAll(document: vscode.TextDocument): Promise<void> {
    const docKey = document.uri.toString();
    if (this._fetchingDocs.has(docKey)) return;
    const defs = collectDefinitionLines(document);
    const missing = defs.filter(d => !lensCache.has(`${docKey}::${d.symbol}`));
    if (!missing.length) return;

    this._fetchingDocs.add(docKey);
    try {
      await Promise.all(missing.map(async def => {
        const cacheKey = `${docKey}::${def.symbol}`;
        try {
          const [complexity, callers] = await Promise.all([
            this.service.getComplexity(def.symbol, document.uri.fsPath),
            this.service.findCallers(def.symbol, document.uri.fsPath)
          ]);
          lensCache.set(cacheKey, { complexity, callers: callers.length });
        } catch {
          lensCache.set(cacheKey, { complexity: undefined, callers: 0 });
        }
      }));
      this._onDidChange.fire();
    } finally {
      this._fetchingDocs.delete(docKey);
    }
  }

  public invalidate(): void {
    lensCache.clear();
    this._fetchingDocs.clear();
    this._onDidChange.fire();
  }
}

export class CgcHoverProvider implements vscode.HoverProvider {
  constructor(private readonly service: CgcService) {}

  async provideHover(document: vscode.TextDocument, position: vscode.Position): Promise<vscode.Hover | undefined> {
    const symbol = symbolAtPosition(document, position);
    if (!symbol) return undefined;

    const [complexity, callers, callees] = await Promise.all([
      this.service.getComplexity(symbol, document.uri.fsPath),
      this.service.findCallers(symbol, document.uri.fsPath),
      this.service.findCallees(symbol, document.uri.fsPath)
    ]);

    const threshold = vscode.workspace.getConfiguration("cgc").get<number>("complexityWarningThreshold", 10);
    const md = new vscode.MarkdownString(undefined, true);
    md.appendMarkdown(`**${symbol}**  \n`);
    if (typeof complexity === "number") {
      md.appendMarkdown(`Complexity: \`${complexity}\`${complexity > threshold ? " ⚠️ high complexity" : ""}  \n`);
    }
    md.appendMarkdown(`Incoming callers: \`${callers.length}\`  \n`);
    md.appendMarkdown(`Outgoing callees: \`${callees.length}\`  \n`);
    md.appendMarkdown("\nMini-map: ");
    md.appendMarkdown(renderMiniMapSvg(symbol, callers.length, callees.length));
    md.appendMarkdown(" Powered by CodeGraphContext MCP.");
    return new vscode.Hover(md);
  }
}

export class CgcDeadCodeDiagnostics {
  private readonly collection = vscode.languages.createDiagnosticCollection("cgc-dead-code");
  private readonly strikeDecoration = vscode.window.createTextEditorDecorationType({
    textDecoration: "line-through 1px",
    opacity: "0.75"
  });
  private readonly index = new Map<string, DeadCodeEntry>();

  constructor(private readonly service: CgcService) {}

  public dispose(): void {
    this.collection.dispose();
    this.strikeDecoration.dispose();
  }

  public async refreshForDocument(document: vscode.TextDocument): Promise<void> {
    if (document.uri.scheme !== "file") return;
    const all = await this.service.findDeadCode();
    this.index.clear();
    for (const entry of all) {
      const key = `${entry.path}:${entry.line_number}:${entry.function_name ?? entry.class_name}`;
      this.index.set(key, entry);
    }
    const max = vscode.workspace.getConfiguration("cgc").get<number>("maxDeadCodeDiagnostics", 100);
    const diagnostics: vscode.Diagnostic[] = [];

    for (const entry of all.slice(0, max)) {
      if (entry.path !== document.uri.fsPath || typeof entry.line_number !== "number") continue;
      const line = Math.max(0, entry.line_number - 1);
      if (line >= document.lineCount) continue;
      const text = document.lineAt(line).text;
      const range = new vscode.Range(line, 0, line, Math.max(1, text.length));
      const targetName = entry.function_name ?? entry.class_name ?? "symbol";
      const diagnostic = new vscode.Diagnostic(range, `Potentially unused: ${targetName}`, vscode.DiagnosticSeverity.Hint);
      diagnostic.code = "cgc.deadCode";
      diagnostics.push(diagnostic);
    }
    this.collection.set(document.uri, diagnostics);
    const active = vscode.window.visibleTextEditors.find(e => e.document.uri.toString() === document.uri.toString());
    if (active) {
      active.setDecorations(this.strikeDecoration, diagnostics.map(d => d.range));
    }
  }
}

export class CgcDeadCodeCodeActionProvider implements vscode.CodeActionProvider {
  public static readonly providedCodeActionKinds = [vscode.CodeActionKind.QuickFix];

  provideCodeActions(document: vscode.TextDocument, range: vscode.Range): vscode.CodeAction[] {
    const line = document.lineAt(range.start.line);
    const commentAction = new vscode.CodeAction("CGC: Comment out dead code", vscode.CodeActionKind.QuickFix);
    commentAction.edit = new vscode.WorkspaceEdit();
    commentAction.edit.replace(document.uri, line.range, `# ${line.text}`);
    return [commentAction];
  }
}

function renderMiniMapSvg(symbol: string, callerCount: number, calleeCount: number): string {
  const escaped = symbol.replace(/"/g, "").slice(0, 12);
  return new vscode.MarkdownString(
    `<svg width="220" height="90" viewBox="0 0 220 90" xmlns="http://www.w3.org/2000/svg">
      <rect x="85" y="30" width="50" height="24" rx="6" fill="#4b8bbe"/>
      <text x="110" y="46" font-size="10" text-anchor="middle" fill="#fff">${escaped}</text>
      <circle cx="25" cy="42" r="12" fill="#6dbf73"/><text x="25" y="46" font-size="9" text-anchor="middle" fill="#111">${callerCount}</text>
      <circle cx="195" cy="42" r="12" fill="#f4b860"/><text x="195" y="46" font-size="9" text-anchor="middle" fill="#111">${calleeCount}</text>
      <path d="M37 42 L85 42" stroke="#9fb0c5" stroke-width="2"/><path d="M135 42 L183 42" stroke="#9fb0c5" stroke-width="2"/>
    </svg>`,
    true
  ).value;
}
