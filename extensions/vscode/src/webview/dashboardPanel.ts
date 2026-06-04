import * as vscode from "vscode";
import { CgcService } from "../mcp/service";
import { CgcMcpClient } from "../mcp/client";
import { cgcEvents } from "../mcp/eventBus";
import { renderDashboardHtml } from "./dashboardTemplate";

export class DashboardPanel {
  private panel?: vscode.WebviewPanel;
  private disposables: Array<{ dispose(): void }> = [];

  constructor(
    private readonly service: CgcService,
    private readonly client: CgcMcpClient
  ) {
    // Listen for events emitted by other components (sidebar, etc.)
    this.disposables.push(
      { dispose: cgcEvents.on("repo:changed", () => this.refresh()) },
      { dispose: cgcEvents.on("context:changed", () => this.refresh()) },
      { dispose: cgcEvents.on("graph:changed", () => this.refresh()) },
      { dispose: cgcEvents.on("index:done", () => this.refresh()) }
    );
  }

  /** Read selected repo from the VS Code config — single source of truth. */
  private getSelectedRepo(repos: Array<{ path?: string }>): string {
    const fromConfig = vscode.workspace.getConfiguration("cgc").get<string>("repoPath", "").trim();
    if (fromConfig) return fromConfig;
    return repos[0]?.path ?? "";
  }

  public show(): void {
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel("cgc.dashboard", "CGC Command Center", vscode.ViewColumn.One, {
        enableScripts: true,
        retainContextWhenHidden: true
      });
      this.panel.onDidDispose(() => {
        this.panel = undefined;
      });
      // Auto-refresh when the panel becomes visible (e.g. user clicks the tab).
      // This catches external changes like repos deleted via CLI.
      this.panel.onDidChangeViewState((e) => {
        if (e.webviewPanel.visible) {
          this.refresh();
        }
      });
      this.panel.webview.onDidReceiveMessage(async (msg: { type: string; value?: string; query?: string }) => {
        if (msg.type === "index-workspace") {
          const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
          if (workspace) {
            await this.service.indexWorkspace(workspace);
            vscode.window.showInformationMessage("CGC indexing started.");
            cgcEvents.emit("graph:changed");
            await this.refresh();
          }
        } else if (msg.type === "toggle-watch") {
          const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
          if (workspace) {
            await this.service.watchWorkspace(workspace);
            vscode.window.showInformationMessage("CGC live watch enabled.");
            cgcEvents.emit("graph:changed");
            await this.refresh();
          }
        } else if (msg.type === "change-repo") {
          const newRepo = msg.value ?? "";
          await vscode.workspace.getConfiguration("cgc").update("repoPath", newRepo, vscode.ConfigurationTarget.Workspace);
          // Emit event so sidebar and other components sync
          cgcEvents.emit("repo:changed", { source: "dashboard", repoPath: newRepo });
          await this.refresh();
        } else if (msg.type === "run-search" && msg.query) {
          const rows = await this.service.findCode(msg.query, true);
          this.panel?.webview.postMessage({ type: "search-results", rows });
        } else if (msg.type === "run-cypher" && msg.query) {
          const rows = await this.service.runCypher(msg.query);
          this.panel?.webview.postMessage({ type: "cypher-results", rows });
          await vscode.commands.executeCommand("cgc.runCypherQuery", msg.query);
        } else if (msg.type === "save-config") {
          await vscode.commands.executeCommand("cgc.openEngineConfig");
        } else if (msg.type === "refresh") {
          // Manual refresh — restart the MCP server to get a fresh DB connection,
          // then re-query. This is the nuclear option that catches external changes
          // like repos deleted via the CLI, which the long-running MCP process
          // doesn't know about.
          await this.client.restart();
          cgcEvents.emit("graph:changed");
          await this.refresh();
        }
      });
    }
    this.refresh().catch((err) => vscode.window.showErrorMessage(`CGC dashboard failed: ${String(err)}`));
    this.panel.reveal(vscode.ViewColumn.One);
  }

  public async refresh(): Promise<void> {
    if (!this.panel) {
      return;
    }
    const repos = await this.service.listRepositories();
    const selectedRepo = this.getSelectedRepo(repos);
    const hotspots = await this.service.getComplexityHotspots(8);
    this.panel.webview.html = renderDashboardHtml({ repos, hotspots, selectedRepo });
  }

  public notifyRefresh(reason: string): void {
    this.panel?.webview.postMessage({ type: "refresh-notice", reason });
  }

  public dispose(): void {
    for (const d of this.disposables) d.dispose();
    this.disposables = [];
    this.panel?.dispose();
  }
}
