import * as vscode from "vscode";
import { CgcService } from "../mcp/service";

class SimpleItem extends vscode.TreeItem {
  constructor(label: string, collapsibleState = vscode.TreeItemCollapsibleState.None) {
    super(label, collapsibleState);
  }
}

export class ReposTreeProvider implements vscode.TreeDataProvider<SimpleItem> {
  private readonly emitter = new vscode.EventEmitter<void>();
  public readonly onDidChangeTreeData = this.emitter.event;

  constructor(private readonly service: CgcService) {}

  refresh(): void {
    this.emitter.fire();
  }

  getTreeItem(element: SimpleItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<SimpleItem[]> {
    const repos = await this.service.listRepositories();
    if (!repos.length) {
      return [new SimpleItem("No indexed repositories")];
    }
    return repos.map((r) => {
      const item = new SimpleItem(r.repo_name ?? r.path ?? "Repository");
      item.description = r.path;
      return item;
    });
  }
}

export class BundlesTreeProvider implements vscode.TreeDataProvider<SimpleItem> {
  private readonly emitter = new vscode.EventEmitter<void>();
  public readonly onDidChangeTreeData = this.emitter.event;

  constructor(private readonly service: CgcService) {}

  refresh(): void {
    this.emitter.fire();
  }

  getTreeItem(element: SimpleItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<SimpleItem[]> {
    const bundles = await this.service.searchBundles("");
    if (!bundles.length) {
      return [new SimpleItem("No bundles found in registry")];
    }
    return bundles.slice(0, 30).map((bundle) => {
      const item = new SimpleItem(String(bundle.name ?? bundle.bundle_name ?? "Bundle"));
      item.description = String(bundle.version ?? "");
      return item;
    });
  }
}
