import * as vscode from "vscode";
import { CgcService } from "../mcp/service";
import { renderDashboardHtml } from "./dashboardTemplate";

export class DashboardPanel {
  private panel?: vscode.WebviewPanel;
  private selectedRepo = "";

  constructor(private readonly service: CgcService) {}

  public show(): void {
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel("cgc.dashboard", "CGC Command Center", vscode.ViewColumn.One, {
        enableScripts: true,
        retainContextWhenHidden: true
      });
      this.panel.onDidDispose(() => {
        this.panel = undefined;
      });
      this.panel.webview.onDidReceiveMessage(async (msg: { type: string; value?: string; query?: string }) => {
        if (msg.type === "index-workspace") {
          const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
          if (workspace) {
            await this.service.indexWorkspace(workspace);
            vscode.window.showInformationMessage("CGC indexing started.");
            await this.refresh();
          }
        } else if (msg.type === "toggle-watch") {
          const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
          if (workspace) {
            await this.service.watchWorkspace(workspace);
            vscode.window.showInformationMessage("CGC live watch enabled.");
            await this.refresh();
          }
        } else if (msg.type === "change-repo") {
          this.selectedRepo = msg.value ?? "";
          await vscode.workspace.getConfiguration("cgc").update("repoPath", this.selectedRepo, vscode.ConfigurationTarget.Workspace);
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
    if (!this.selectedRepo && repos.length) {
      this.selectedRepo = repos[0].path ?? "";
    }
    const hotspots = await this.service.getComplexityHotspots(8);
    this.panel.webview.html = renderDashboardHtml({ repos, hotspots, selectedRepo: this.selectedRepo });
  }

  public notifyRefresh(reason: string): void {
    this.panel?.webview.postMessage({ type: "refresh-notice", reason });
  }
}

