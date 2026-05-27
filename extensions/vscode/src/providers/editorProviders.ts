import * as vscode from "vscode";
import { CgcService } from "../mcp/service";
import { DeadCodeEntry } from "../types/cgc";

// ─── Multi-language definition detector ───────────────────────────────────────
// Covers Python, JS/TS, Java, Go, Rust, C/C++, Kotlin, Swift, Ruby, PHP, C#
const DEF_PATTERN =
  /^\s*(?:(?:pub(?:\s+(?:async|unsafe))?|private|protected|public|static|async|export\s+(?:default\s+)?|override|abstract|inline|virtual|extern\s+"C"\s+)?(?:fun|fn|func|def|function|sub|method)\s+([A-Za-z_$][A-Za-z0-9_$]*)|(?:class|interface|struct|enum|trait|protocol|abstract\s+class|sealed\s+class|data\s+class)\s+([A-Za-z_$][A-Za-z0-9_$]*))/;

function symbolAtPosition(document: vscode.TextDocument, position: vscode.Position): string | undefined {
  const range = document.getWordRangeAtPosition(position, /[A-Za-z_$][A-Za-z0-9_$]*/);
  return range ? document.getText(range) : undefined;
}

function collectDefinitionLines(document: vscode.TextDocument): Array<{ line: number; symbol: string; type: "function" | "class" }> {
  const out: Array<{ line: number; symbol: string; type: "function" | "class" }> = [];
  for (let i = 0; i < document.lineCount; i++) {
    const text = document.lineAt(i).text;
    const m = DEF_PATTERN.exec(text);
    if (m) {
      out.push({
        line: i,
        symbol: m[1] ?? m[2],
        type: m[1] ? "function" : "class"
      });
    }
  }
  return out;
}

// ─── CodeLens ─────────────────────────────────────────────────────────────────

const lensCache = new Map<string, { complexity?: number; callers: number; callees: number }>();

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

      if (def.type === "class") {
        const title = `🏛️ Class Hierarchy`;
        lenses.push(
          new vscode.CodeLens(range, {
            title,
            command: "cgc.showClassHierarchy",
            arguments: [def.symbol],
            tooltip: `Show Class Hierarchy for ${def.symbol}`
          })
        );
      } else {
        const threshold = vscode.workspace.getConfiguration("cgc").get<number>("complexityWarningThreshold", 10);
        const cc = cached?.complexity;
        const callers = cached?.callers ?? 0;
        const callees = cached?.callees ?? 0;

        const ccLabel = cc !== undefined ? `cc:${cc}${cc > threshold ? " ⚠️" : ""}` : "cc:…";
        const title = `⚡ ${ccLabel}  ←${callers} callers  →${callees} callees`;

        lenses.push(
          new vscode.CodeLens(range, {
            title,
            command: "cgc.showCallGraph",
            arguments: [document.uri, def.symbol],
            tooltip: `Open Call Graph for ${def.symbol}`
          })
        );
      }
    }

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
          const [complexity, callers, callees] = await Promise.all([
            this.service.getComplexity(def.symbol, document.uri.fsPath),
            this.service.findCallers(def.symbol, document.uri.fsPath),
            this.service.findCallees(def.symbol, document.uri.fsPath),
          ]);
          lensCache.set(cacheKey, { complexity, callers: callers.length, callees: callees.length });
        } catch {
          lensCache.set(cacheKey, { complexity: undefined, callers: 0, callees: 0 });
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

// ─── Hover Provider ───────────────────────────────────────────────────────────

export class CgcHoverProvider implements vscode.HoverProvider {
  constructor(private readonly service: CgcService) {}

  async provideHover(document: vscode.TextDocument, position: vscode.Position): Promise<vscode.Hover | undefined> {
    const symbol = symbolAtPosition(document, position);
    if (!symbol) return undefined;

    const [complexity, callers, callees] = await Promise.all([
      this.service.getComplexity(symbol, document.uri.fsPath),
      this.service.findCallers(symbol, document.uri.fsPath),
      this.service.findCallees(symbol, document.uri.fsPath),
    ]).catch(() => [undefined, [], []] as const);

    const threshold = vscode.workspace.getConfiguration("cgc").get<number>("complexityWarningThreshold", 10);
    const md = new vscode.MarkdownString(undefined, true);
    md.isTrusted = true;
    md.supportHtml = true;

    // Header
    md.appendMarkdown(`**\`${symbol}\`**`);
    if (typeof complexity === "number" && complexity > threshold) {
      md.appendMarkdown(` — ⚠️ High complexity`);
    }
    md.appendMarkdown(`\n\n`);

    // Metrics row
    const ccStr = typeof complexity === "number" ? `\`${complexity}\`` : "_unknown_";
    md.appendMarkdown(`| | |\n|---|---|\n`);
    md.appendMarkdown(`| **Complexity** | ${ccStr}${typeof complexity === "number" && complexity > threshold ? " ⚠️" : ""} |\n`);
    md.appendMarkdown(`| **←&nbsp;Callers** | \`${callers.length}\` |\n`);
    md.appendMarkdown(`| **→&nbsp;Callees** | \`${callees.length}\` |\n\n`);

    // Top callers
    const topCallers = callers.slice(0, 3);
    if (topCallers.length > 0) {
      md.appendMarkdown(`**Called by:** `);
      const callerLinks = topCallers.map(c => {
        const name = c.caller_name ?? "caller";
        const file = c.caller_file_path;
        const line = c.call_line_number ?? c.caller_line_number ?? 1;
        if (file) {
          const args = encodeURIComponent(JSON.stringify([vscode.Uri.file(file).toString(), line]));
          return `[${name}](command:cgc._jumpToLocation?${args})`;
        }
        return `\`${name}\``;
      });
      md.appendMarkdown(callerLinks.join(" · "));
      if (callers.length > 3) md.appendMarkdown(` +${callers.length - 3} more`);
      md.appendMarkdown(`\n\n`);
    }

    // Top callees
    const topCallees = callees.slice(0, 3);
    if (topCallees.length > 0) {
      md.appendMarkdown(`**Calls:** `);
      const calleeNames = topCallees.map(c => `\`${c.called_name ?? "?"}\``);
      md.appendMarkdown(calleeNames.join(" · "));
      if (callees.length > 3) md.appendMarkdown(` +${callees.length - 3} more`);
      md.appendMarkdown(`\n\n`);
    }

    // Actions
    const cgArgs = encodeURIComponent(JSON.stringify([symbol]));
    md.appendMarkdown(`[→ Open Call Graph](command:cgc.showCallGraph?${cgArgs})&nbsp;&nbsp;`);
    md.appendMarkdown(`[↗ Analyze Callers](command:cgc.analyzeRelationships)`);
    md.appendMarkdown(`\n\n_Powered by CodeGraphContext_`);

    return new vscode.Hover(md);
  }
}

// ─── Dead Code Diagnostics ────────────────────────────────────────────────────

export class CgcDeadCodeDiagnostics {
  private readonly collection = vscode.languages.createDiagnosticCollection("cgc-dead-code");
  private readonly strikeDecoration = vscode.window.createTextEditorDecorationType({
    textDecoration: "line-through 1px rgba(255,255,255,0.35)",
    opacity: "0.70",
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
      const diagnostic = new vscode.Diagnostic(
        range,
        `CGC: Potentially unused — \`${targetName}\``,
        vscode.DiagnosticSeverity.Hint
      );
      diagnostic.code = { value: "cgc.deadCode", target: vscode.Uri.parse("https://github.com/Shashank-KanakapuraSrinivas/CodeGraphContext") };
      diagnostic.tags = [vscode.DiagnosticTag.Unnecessary];
      diagnostics.push(diagnostic);
    }
    this.collection.set(document.uri, diagnostics);
    const active = vscode.window.visibleTextEditors.find(
      e => e.document.uri.toString() === document.uri.toString()
    );
    if (active) {
      active.setDecorations(this.strikeDecoration, diagnostics.map(d => d.range));
    }
  }
}

// ─── Dead Code Quick Fix ──────────────────────────────────────────────────────

export class CgcDeadCodeCodeActionProvider implements vscode.CodeActionProvider {
  public static readonly providedCodeActionKinds = [vscode.CodeActionKind.QuickFix];

  provideCodeActions(document: vscode.TextDocument, range: vscode.Range): vscode.CodeAction[] {
    const actions: vscode.CodeAction[] = [];
    const line = document.lineAt(range.start.line);
    const lineText = line.text;

    // Detect language-specific comment prefix
    const langId = document.languageId;
    let commentChar = "#";
    if (["javascript", "typescript", "java", "go", "rust", "c", "cpp", "csharp", "swift", "kotlin", "dart"].includes(langId)) {
      commentChar = "//";
    } else if (["html", "xml"].includes(langId)) {
      commentChar = "<!--";
    }

    // Comment-out action
    const commentAction = new vscode.CodeAction(
      `CGC: Comment out dead code (${commentChar})`,
      vscode.CodeActionKind.QuickFix
    );
    commentAction.edit = new vscode.WorkspaceEdit();
    const prefix = commentChar === "<!--" ? "<!-- " : `${commentChar} `;
    commentAction.edit.replace(document.uri, line.range, `${" ".repeat(lineText.match(/^\s*/)?.[0].length ?? 0)}${prefix}${lineText.trimStart()}`);
    actions.push(commentAction);

    // Suppress this diagnostic action
    const suppressAction = new vscode.CodeAction(
      "CGC: Suppress dead code warning for this line",
      vscode.CodeActionKind.QuickFix
    );
    suppressAction.command = {
      command: "cgc.suppressDeadCode",
      title: "Suppress",
      arguments: [document.uri, range.start.line]
    };
    actions.push(suppressAction);

    return actions;
  }
}
