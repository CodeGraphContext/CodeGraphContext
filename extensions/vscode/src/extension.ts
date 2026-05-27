import * as vscode from "vscode";
import { CgcMcpClient } from "./mcp/client";
import { CgcService } from "./mcp/service";
import { cgcEvents } from "./mcp/eventBus";
import { JobPoller } from "./mcp/jobPoller";
import {
  CgcCodeLensProvider,
  CgcDeadCodeCodeActionProvider,
  CgcDeadCodeDiagnostics,
  CgcHoverProvider,
} from "./providers/editorProviders";
import { BundlesTreeProvider } from "./views/explorerViews";
import { SidebarControlPanel } from "./views/controlPanel";
import { CgcStatusBarItem } from "./views/statusBarItem";
import { CallGraphPanel } from "./webview/callGraphPanel";
import { extractDeclarationSignature } from "./testing/parser";
import { DashboardPanel } from "./webview/dashboardPanel";
import { ContextManager } from "./mcp/contextManager";

function extractSymbolAtCursor(editor: vscode.TextEditor): string | undefined {
  const range = editor.document.getWordRangeAtPosition(
    editor.selection.active,
    /[A-Za-z_$][A-Za-z0-9_$]*/
  );
  return range ? editor.document.getText(range) : undefined;
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  // ── Core infrastructure ───────────────────────────────────────────────────
  const client = new CgcMcpClient(context);
  const jobPoller = new JobPoller(new CgcService(client)); // use service on client before full start

  try {
    await client.ensureStarted();
    cgcEvents.emit("mcp:online");
  } catch (err) {
    cgcEvents.emit("mcp:offline");
    vscode.window.showWarningMessage(
      `CGC: Could not start MCP server — ${String(err)}. Check the CGC output channel.`
    );
  }

  const service = new CgcService(client);
  const statusBar = new CgcStatusBarItem(client);

  // ── UI providers ──────────────────────────────────────────────────────────
  const callGraphPanel = new CallGraphPanel(service);
  const dashboardPanel = new DashboardPanel(service, client);
  const sidebarControl = new SidebarControlPanel(service, client, context);

  const diagnostics = new CgcDeadCodeDiagnostics(service);
  const codeLensProvider = new CgcCodeLensProvider(service);
  const hoverProvider = new CgcHoverProvider(service);

  const bundlesProvider = new BundlesTreeProvider(service);
  const contextManager = new ContextManager(service, sidebarControl);

  contextManager.initializeContext().catch(err => {
    console.error("CGC: Context initialization failed", err);
  });

  // ─── Menu Context Management ────────────────────────────────────────────────
  const updateMenuContext = (editor: vscode.TextEditor | undefined) => {
    if (!editor) return;
    const pos = editor.selection.active;
    const lineText = editor.document.lineAt(pos.line).text;
    const isClass = /^\s*(?:pub\s+|private\s+|protected\s+|public\s+|static\s+|export\s+)?(?:class|interface|struct|enum|trait|protocol)\b/.test(lineText);
    const isFunction = /^\s*(?:pub\s+|private\s+|protected\s+|public\s+|static\s+|async\s+|export\s+)?(?:fun|fn|func|def|function|sub|method)\b/.test(lineText);
    
    vscode.commands.executeCommand("setContext", "cgc:isClass", isClass);
    vscode.commands.executeCommand("setContext", "cgc:isFunction", isFunction);
  };

  context.subscriptions.push(
    vscode.window.onDidChangeTextEditorSelection(e => updateMenuContext(e.textEditor)),
    vscode.window.onDidChangeActiveTextEditor(updateMenuContext)
  );
  updateMenuContext(vscode.window.activeTextEditor);

  const previousSignatures = new Map<string, string>();
  const watcher = vscode.workspace.createFileSystemWatcher("**/.codegraphcontext/**");

  context.subscriptions.push(
    statusBar,
    jobPoller,
    vscode.languages.registerCodeLensProvider({ scheme: "file" }, codeLensProvider),
    vscode.languages.registerHoverProvider({ scheme: "file" }, hoverProvider),
    vscode.languages.registerCodeActionsProvider(
      { scheme: "file" },
      new CgcDeadCodeCodeActionProvider(),
      { providedCodeActionKinds: CgcDeadCodeCodeActionProvider.providedCodeActionKinds }
    ),

    vscode.window.registerTreeDataProvider("cgc-bundles", bundlesProvider),
    vscode.window.registerWebviewViewProvider(SidebarControlPanel.viewType, sidebarControl),
    diagnostics,
    watcher
  );

  // ── Diagnostics helpers ───────────────────────────────────────────────────
  const refreshDiagnostics = async (doc?: vscode.TextDocument): Promise<void> => {
    const target = doc ?? vscode.window.activeTextEditor?.document;
    if (!target) return;
    try {
      await diagnostics.refreshForDocument(target);
    } catch (err) {
      vscode.window.setStatusBarMessage(`CGC diagnostics error: ${String(err)}`, 4000);
    }
  };

  // ─── Event Coordination ─────────────────────────────────────────────────────
  const invalidateAll = () => {
    codeLensProvider.invalidate();
    refreshDiagnostics().catch(() => {});
  };

  cgcEvents.on("graph:changed", invalidateAll);
  cgcEvents.on("index:done", invalidateAll);
  cgcEvents.on("repo:changed", invalidateAll);
  cgcEvents.on("context:changed", invalidateAll);

  // ── Commands ──────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("cgc.openDashboard", () => {
      dashboardPanel.show();
    }),

    vscode.commands.registerCommand("cgc.visualizeRepo", () => {
      dashboardPanel.show();
    }),

    vscode.commands.registerCommand("cgc.showCallGraph", () => {
      const editor = vscode.window.activeTextEditor;
      callGraphPanel.show(context, editor ? extractSymbolAtCursor(editor) : undefined);
    }),

    vscode.commands.registerCommand("cgc.analyzeRelationships", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const symbol = extractSymbolAtCursor(editor);
      if (!symbol) return;
      const callers = await service.findCallers(symbol, editor.document.uri.fsPath);
      const selected = await vscode.window.showQuickPick(
        callers.map((c) => ({
          label: c.caller_name ?? "caller",
          description: c.caller_file_path,
          line: c.call_line_number ?? c.caller_line_number ?? 1,
        })),
        { title: `Callers of ${symbol}` }
      );
      if (selected?.description) {
        const doc = await vscode.workspace.openTextDocument(selected.description);
        const nextEditor = await vscode.window.showTextDocument(doc);
        const pos = new vscode.Position(Math.max(0, selected.line - 1), 0);
        nextEditor.selection = new vscode.Selection(pos, pos);
        nextEditor.revealRange(new vscode.Range(pos, pos));
      }
    }),

    vscode.commands.registerCommand("cgc.refreshIndex", async () => {
      const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!workspace) return;
      await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: "Refreshing CodeGraphContext index…" },
        async () => {
          const jobId = await service.indexWorkspace(workspace);
          if (jobId) jobPoller.startPolling(jobId);
          await service.watchWorkspace(workspace);
        }
      );
      cgcEvents.emit("graph:changed");
      await refreshDiagnostics();
    }),

    vscode.commands.registerCommand("cgc.runIndexWizard", async () => {
      const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!workspace) return;
      const choice = await vscode.window.showQuickPick(["Index only", "Index + Watch"], {
        title: "CodeGraphContext setup",
      });
      if (!choice) return;
      const jobId = await service.indexWorkspace(workspace);
      if (jobId) jobPoller.startPolling(jobId);
      if (choice === "Index + Watch") {
        await service.watchWorkspace(workspace);
      }
      vscode.window.showInformationMessage("CGC setup complete for this workspace.");
      cgcEvents.emit("graph:changed");
    }),

    vscode.commands.registerCommand("cgc.openEngineConfig", () => {
      vscode.commands.executeCommand("workbench.action.openSettings", "cgc");
    }),

    vscode.commands.registerCommand("cgc.runCypherQuery", async () => {
      dashboardPanel.show();
    }),

    vscode.commands.registerCommand("cgc.showComplexityAtSymbol", async (uri: vscode.Uri, symbol: string) => {
      const complexity = await service.getComplexity(symbol, uri.fsPath);
      vscode.window.showInformationMessage(`Complexity for ${symbol}: ${complexity ?? "unknown"}`);
    }),

    vscode.commands.registerCommand("cgc.showCallersAtSymbol", async (uri: vscode.Uri, symbol: string) => {
      const callers = await service.findCallers(symbol, uri.fsPath);
      vscode.window.showInformationMessage(`${symbol} has ${callers.length} caller(s).`);
    }),

    vscode.commands.registerCommand("cgc.showVariableImpact", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const variable = extractSymbolAtCursor(editor);
      if (!variable) return;
      const impacts = await service.variableImpactRadius(variable, editor.document.uri.fsPath);
      const picked = await vscode.window.showQuickPick(
        impacts.slice(0, 50).map((row) => ({
          label: String(row["name"] ?? row["variable_name"] ?? variable),
          description: String(row["path"] ?? row["file_path"] ?? ""),
          detail: JSON.stringify(row),
        })),
        { title: `Impact Radius for ${variable}` }
      );
      if (picked?.description) {
        const doc = await vscode.workspace.openTextDocument(picked.description);
        await vscode.window.showTextDocument(doc);
      }
    }),

    vscode.commands.registerCommand("cgc.showClassHierarchy", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const className = extractSymbolAtCursor(editor);
      if (!className) return;
      const hierarchy = await service.findClassHierarchy(className, editor.document.uri.fsPath);
      if (!hierarchy.length) {
        vscode.window.showInformationMessage(`No inheritance data found for ${className}.`);
        return;
      }
      const picked = await vscode.window.showQuickPick(
        hierarchy.slice(0, 50).map((row) => ({
          label: String(row["name"] ?? row["class_name"] ?? "?"),
          description: String(row["path"] ?? row["file_path"] ?? ""),
          detail: String(row["relationship"] ?? row["type"] ?? ""),
        })),
        { title: `Class Hierarchy for ${className}` }
      );
      if (picked?.description) {
        const doc = await vscode.workspace.openTextDocument(picked.description);
        await vscode.window.showTextDocument(doc);
      }
    }),

    vscode.commands.registerCommand("cgc.generateReport", async () => {
      await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: "CGC: Generating code health report…", cancellable: false },
        async () => {
          const outputPath = await service.generateReport();
          vscode.window.showInformationMessage(`Report written to: ${outputPath}`, "Open").then(async (choice) => {
            if (choice === "Open") {
              try {
                const doc = await vscode.workspace.openTextDocument(outputPath);
                await vscode.window.showTextDocument(doc);
              } catch {
                vscode.window.showWarningMessage(`Could not open report at ${outputPath}`);
              }
            }
          });
        }
      );
    }),

    vscode.commands.registerCommand("cgc.discoverContexts", async () => {
      const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      const contexts = await service.discoverContexts(workspace);
      if (!contexts.length) {
        vscode.window.showInformationMessage("No sub-project .codegraphcontext folders found.");
        return;
      }
      const picked = await vscode.window.showQuickPick(
        contexts.map((c) => ({ label: c.name ?? c.path, description: c.path })),
        { title: "Switch CGC context to…" }
      );
      if (picked?.description) {
        await service.switchContext(picked.description);
        cgcEvents.emit("context:changed", { source: "command", contextPath: picked.description });
        vscode.window.showInformationMessage(`CGC context switched to: ${picked.label}`);
      }
    }),

    vscode.commands.registerCommand("cgc.suppressDeadCode", (uri: vscode.Uri, line: number) => {
      // No-op placeholder — suppression list would be stored in workspace settings
      vscode.window.showInformationMessage(`CGC: Dead code warning suppressed for line ${line + 1}.`);
    }),

    // Internal: jump-to-location used by hover card command links
    vscode.commands.registerCommand("cgc._jumpToLocation", async (uriStr: string, line: number) => {
      try {
        const doc = await vscode.workspace.openTextDocument(vscode.Uri.parse(uriStr));
        const editor = await vscode.window.showTextDocument(doc);
        const pos = new vscode.Position(Math.max(0, line - 1), 0);
        editor.selection = new vscode.Selection(pos, pos);
        editor.revealRange(new vscode.Range(pos, pos));
      } catch {
        // silently fail — file may not exist on disk
      }
    }),

    // ── Event listeners ────────────────────────────────────────────────────
    vscode.workspace.onDidSaveTextDocument(async (doc) => {
      await refreshDiagnostics(doc);
      const currentSig = extractDeclarationSignature(doc.lineAt(0).text) ?? "";
      const prev = previousSignatures.get(doc.uri.fsPath);
      if (prev && prev !== currentSig) {
        const impact = await service.findCallers(currentSig || prev, doc.uri.fsPath);
        if (impact.length > 0) {
          vscode.window
            .showWarningMessage(
              `CGC: ${impact.length} caller(s) may be affected by signature change in ${doc.fileName.split("/").pop()}.`,
              "Show Call Graph"
            )
            .then((choice) => {
              if (choice === "Show Call Graph") {
                callGraphPanel.show(context, currentSig || prev);
              }
            });
        }
      }
      previousSignatures.set(doc.uri.fsPath, currentSig);
      dashboardPanel.notifyRefresh("save event");
      await dashboardPanel.refresh();
    }),

    vscode.window.onDidChangeActiveTextEditor(async (editor) => {
      if (!editor) return;
      await refreshDiagnostics(editor.document);
      const symbol = extractSymbolAtCursor(editor);
      if (symbol) {
        callGraphPanel.postEditorSelection(editor.document.uri.fsPath, symbol);
      }
    }),

    vscode.window.onDidChangeTextEditorSelection((evt) => {
      const symbol = extractSymbolAtCursor(evt.textEditor);
      if (symbol) {
        callGraphPanel.postEditorSelection(evt.textEditor.document.uri.fsPath, symbol);
      }
    }),

    watcher.onDidCreate(async () => {
      cgcEvents.emit("graph:changed");
      dashboardPanel.notifyRefresh(".codegraphcontext created");
    }),

    watcher.onDidChange(async () => {
      cgcEvents.emit("graph:changed");
      dashboardPanel.notifyRefresh(".codegraphcontext changed");
    }),

    watcher.onDidDelete(async () => {
      cgcEvents.emit("graph:changed");
      dashboardPanel.notifyRefresh(".codegraphcontext deleted");
    })
  );

  dashboardPanel.show();
  await refreshDiagnostics();
}

export function deactivate(): void {
  // Resources are disposed via extension subscriptions
}
