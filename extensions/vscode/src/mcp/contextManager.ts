import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import { CgcService } from "./service";
import { SidebarControlPanel } from "../views/controlPanel";

export class ContextManager {
  private lastRecommendedPath?: string;

  constructor(
    private readonly service: CgcService,
    private readonly sidebar: SidebarControlPanel
  ) {}

  public async initializeContext(explicitMode?: string): Promise<void> {
    const config = vscode.workspace.getConfiguration("cgc");
    const mode = explicitMode || config.get<string>("contextMode", "global");

    switch (mode) {
      case "global":
        await this.handleGlobalMode();
        break;
      case "shared":
        await this.handleSharedMode();
        break;
      case "per-repo":
        await this.handlePerRepoMode();
        break;
    }
  }

  private async handleGlobalMode(): Promise<void> {
    // Tell the backend to reconnect to the global DB.
    // The backend's switch_context handles "global" specially by using
    // resolve_context() to find ~/.codegraphcontext/global/db/falkordb.
    await this.service.switchContext("global");
    await this.sidebar.refresh();
  }

  private async handleSharedMode(): Promise<void> {
    const activeContext = vscode.workspace.getConfiguration("cgc").get<string>("repoPath", "");
    if (!activeContext) {
      // Don't load anything, wait for user selection in sidebar
      return;
    }
    await this.service.switchContext(activeContext);
    await this.sidebar.refresh();
  }

  private async handlePerRepoMode(): Promise<void> {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders?.length) return;

    const rootPath = workspaceFolders[0].uri.fsPath;

    const rootCgcPath = path.join(rootPath, ".codegraphcontext");

    // Switch context to rootPath if it exists
    await vscode.workspace.getConfiguration("cgc").update("repoPath", rootPath, vscode.ConfigurationTarget.Workspace);
    if (fs.existsSync(rootCgcPath)) {
      await this.service.switchContext(rootPath);
    }
    await this.sidebar.refresh();

    // Deep Child Discovery (if root doesn't have it, but child does)
    if (!fs.existsSync(rootCgcPath)) {
      const matches = await vscode.workspace.findFiles("**/.codegraphcontext/metadata.json", "**/node_modules/**", 10);
      if (matches.length > 0) {
        const bestMatchUri = matches[0];
        const bestMatchPath = path.dirname(path.dirname(bestMatchUri.fsPath));
        this.lastRecommendedPath = bestMatchPath;
        
        vscode.window.showInformationMessage(
          `CGC: Found a local context in '${path.basename(bestMatchPath)}'. Would you like to connect?`,
          "Connect", "Ignore"
        ).then(async (choice) => {
          if (choice === "Connect") {
            await vscode.workspace.getConfiguration("cgc").update("repoPath", bestMatchPath, vscode.ConfigurationTarget.Workspace);
            await this.service.switchContext(bestMatchPath);
            await this.sidebar.refresh();
          }
        });
      }
    }
  }

  public getRecommendedPath(): string | undefined {
    return this.lastRecommendedPath;
  }
}
