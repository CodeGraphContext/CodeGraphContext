// src/providers/projectsTreeProvider.ts
import * as vscode from 'vscode';
import { CgcManager } from '../cgcManager';
import * as path from 'path';

export class ProjectsTreeProvider implements vscode.TreeDataProvider<ProjectTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<ProjectTreeItem | undefined | null | void> = new vscode.EventEmitter<ProjectTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<ProjectTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    constructor(private cgcManager: CgcManager) { }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: ProjectTreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: ProjectTreeItem): Promise<ProjectTreeItem[]> {
        if (!element) {
            // Root level — show all indexed repos
            try {
                const projects = await this.cgcManager.getProjects();
                if (projects.length === 0) {
                    return [];
                }
                return projects.map(p => new ProjectTreeItem(
                    path.basename(p.path),
                    p.path,
                    p.type === 'Dependency' ? 'dependency' : 'project',
                    `${p.type} • Click to visualize`,
                    vscode.TreeItemCollapsibleState.None
                ));
            } catch (error) {
                return [];
            }
        }
        return [];
    }
}

export class ProjectTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly projectPath: string,
        public readonly contextValue: string,
        public readonly description: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
        this.tooltip = projectPath || label;

        // Single-click on a project row opens the full graph
        if (projectPath) {
            this.command = {
                command: 'cgc.visualizeRepo',
                title: 'Visualize Repository Graph',
                arguments: [this]
            };
            this.iconPath = new vscode.ThemeIcon(
                contextValue === 'dependency' ? 'package' : 'type-hierarchy',
                new vscode.ThemeColor('charts.purple')
            );
        } else {
            this.iconPath = new vscode.ThemeIcon('info');
        }
    }
}
