import * as vscode from "vscode";
import { CgcService } from "../mcp/service";

class SimpleItem extends vscode.TreeItem {
  constructor(label: string, collapsibleState: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None) {
    super(label, collapsibleState);
  }
}

export class BundlesTreeProvider implements vscode.TreeDataProvider<SimpleItem> {
  private emitter = new vscode.EventEmitter<SimpleItem | undefined | void>();
  readonly onDidChangeTreeData = this.emitter.event;

  constructor(private readonly service: CgcService) {}

  refresh(): void {
    this.emitter.fire();
  }

  getTreeItem(element: SimpleItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<SimpleItem[]> {
    try {
      const bundles = await this.service.searchBundles("");
      if (!bundles.length) {
        return [new SimpleItem("No bundles found in registry")];
      }
      return bundles.slice(0, 30).map((bundle: any) => {
        const item = new SimpleItem(String(bundle.name ?? bundle.bundle_name ?? "Bundle"));
        item.description = String(bundle.version ?? "");
        item.tooltip = String(bundle.description ?? "");
        return item;
      });
    } catch (err) {
      return [new SimpleItem("Error loading bundles")];
    }
  }
}
