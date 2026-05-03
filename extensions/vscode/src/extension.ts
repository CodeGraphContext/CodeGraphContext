import * as vscode from "vscode";
import { CgcMcpClient } from "./mcp/client";
import { CgcService } from "./mcp/service";
import { CgcCodeLensProvider, CgcDeadCodeCodeActionProvider, CgcDeadCodeDiagnostics, CgcHoverProvider } from "./providers/editorProviders";
import { BundlesTreeProvider, ReposTreeProvider } from "./views/explorerViews";
import { SidebarControlPanel } from "./views/controlPanel";
import { CallGraphPanel } from "./webview/callGraphPanel";
import { extractDeclarationSignature } from "./testing/parser";
import { DashboardPanel } from "./webview/dashboardPanel";
import { SetupPanel } from "./webview/setupPanel";

function extractSymbolAtCursor(editor: vscode.TextEditor): string | undefined {
  const range = editor.document.getWordRangeAtPosition(editor.selection.active, /[A-Za-z_][A-Za-z0-9_]*/);
  return range ? editor.document.getText(range) : undefined;
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const client = new CgcMcpClient(context);
  await client.ensureStarted();
  const service = new CgcService(client);
  const callGraphPanel = new CallGraphPanel(service);
  const dashboardPanel = new DashboardPanel(service);
  const sidebarControl = new SidebarControlPanel(service, client, context);

  const diagnostics = new CgcDeadCodeDiagnostics(service);
  const codeLensProvider = new CgcCodeLensProvider(service);
  const hoverProvider = new CgcHoverProvider(service);
  const reposProvider = new ReposTreeProvider(service);
  const bundlesProvider = new BundlesTreeProvider(service);

  const previousSignatures = new Map<string, string>();
  const watcher = vscode.workspace.createFileSystemWatcher("**/.codegraphcontext/**");

  context.subscriptions.push(
    vscode.languages.registerCodeLensProvider({ scheme: "file" }, codeLensProvider),
    vscode.languages.registerHoverProvider({ scheme: "file" }, hoverProvider),
    vscode.languages.registerCodeActionsProvider({ scheme: "file" }, new CgcDeadCodeCodeActionProvider(), {
      providedCodeActionKinds: CgcDeadCodeCodeActionProvider.providedCodeActionKinds
    }),
    vscode.window.registerTreeDataProvider("cgc-repos", reposProvider),
    vscode.window.registerTreeDataProvider("cgc-bundles", bundlesProvider),
    vscode.window.registerWebviewViewProvider(SidebarControlPanel.viewType, sidebarControl),
    diagnostics,
    watcher
  );

  const refreshDiagnostics = async (doc?: vscode.TextDocument): Promise<void> => {
    const target = doc ?? vscode.window.activeTextEditor?.document;
    if (!target) return;
    try {
      await diagnostics.refreshForDocument(target);
    } catch (err) {
      vscode.window.setStatusBarMessage(`CGC diagnostics error: ${String(err)}`, 4000);
    }
  };

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
          line: c.call_line_number ?? c.caller_line_number ?? 1
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
        { location: vscode.ProgressLocation.Notification, title: "Refreshing CodeGraphContext index..." },
        async () => {
          await service.indexWorkspace(workspace);
          await service.watchWorkspace(workspace);
        }
      );
      reposProvider.refresh();
      await sidebarControl.refresh();
      await refreshDiagnostics();
    }),
    vscode.commands.registerCommand("cgc.refreshExtension", async () => {
      client.dispose();
      await client.ensureStarted();
      await sidebarControl.refresh();
      vscode.window.showInformationMessage("CGC extension restarted.");
    }),
    vscode.commands.registerCommand("cgc.runIndexWizard", async () => {
      const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!workspace) return;
      const choice = await vscode.window.showQuickPick(["Index only", "Index + Watch"], {
        title: "CodeGraphContext setup"
      });
      if (!choice) return;
      await service.indexWorkspace(workspace);
      if (choice === "Index + Watch") {
        await service.watchWorkspace(workspace);
      }
      vscode.window.showInformationMessage("CGC setup complete for this workspace.");
      reposProvider.refresh();
      await sidebarControl.refresh();
    }),
    vscode.commands.registerCommand("cgc.openEngineConfig", () => {
      SetupPanel.createOrShow(context, client);
    }),
    vscode.commands.registerCommand("cgc.runCypherQuery", async (query?: string) => {
      // Open dashboard with the query
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
          label: String(row.name ?? row.variable_name ?? variable),
          description: String(row.path ?? row.file_path ?? ""),
          detail: JSON.stringify(row)
        })),
        { title: `Impact Radius for ${variable}` }
      );
      if (picked?.description) {
        const doc = await vscode.workspace.openTextDocument(picked.description);
        await vscode.window.showTextDocument(doc);
      }
    }),
    vscode.workspace.onDidSaveTextDocument(async (doc) => {
      await refreshDiagnostics(doc);
      const currentSig = extractDeclarationSignature(doc.lineAt(0).text) ?? "";
      const prev = previousSignatures.get(doc.uri.fsPath);
      if (prev && prev !== currentSig) {
        const impact = await service.findCallers(currentSig || prev, doc.uri.fsPath);
        if (impact.length > 0) {
          vscode.window.showWarningMessage(
            `CGC impact warning: ${impact.length} caller(s) may be affected by signature change.`,
            "Show Call Graph"
          ).then((choice) => {
            if (choice === "Show Call Graph") {
              callGraphPanel.show(context, currentSig || prev);
            }
          });
        }
      }
      previousSignatures.set(doc.uri.fsPath, currentSig);
      dashboardPanel.notifyRefresh("index/save event");
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
      dashboardPanel.notifyRefresh(".codegraphcontext created");
      await dashboardPanel.refresh();
      await sidebarControl.refresh();
    }),
    watcher.onDidChange(async () => {
      dashboardPanel.notifyRefresh(".codegraphcontext changed");
      await dashboardPanel.refresh();
    }),
    watcher.onDidDelete(async () => {
      dashboardPanel.notifyRefresh(".codegraphcontext deleted");
      await dashboardPanel.refresh();
    })
  );

  dashboardPanel.show();
  await refreshDiagnostics();
}

export function deactivate(): void {
  // no-op, resources are disposed by extension subscriptions
}
