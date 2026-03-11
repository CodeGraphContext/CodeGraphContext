// src/providers/dependenciesTreeProvider.ts
import * as vscode from 'vscode';
import { CgcManager } from '../cgcManager';

export class DependenciesTreeProvider implements vscode.TreeDataProvider<DependencyTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<DependencyTreeItem | undefined | null | void> = new vscode.EventEmitter<DependencyTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<DependencyTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private currentFile: string | undefined;

    constructor(private cgcManager: CgcManager) {
        // Watch for active editor changes
        vscode.window.onDidChangeActiveTextEditor(editor => {
            if (editor) {
                this.currentFile = editor.document.uri.fsPath;
                this.refresh();
            }
        });

        // Set initial file
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            this.currentFile = editor.document.uri.fsPath;
        }
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: DependencyTreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: DependencyTreeItem): Promise<DependencyTreeItem[]> {
        if (!element) {
            // Root level - show dependencies for current file
            if (!this.currentFile) {
                return [
                    new DependencyTreeItem(
                        'No file selected',
                        '',
                        '',
                        0,
                        'info',
                        'Open a file to see dependencies',
                        vscode.TreeItemCollapsibleState.None
                    )
                ];
            }

            try {
                const dependencies = await this.cgcManager.getDependencies(this.currentFile);

                if (dependencies.length === 0) {
                    return [
                        new DependencyTreeItem(
                            'No dependencies found',
                            '',
                            '',
                            0,
                            'info',
                            '',
                            vscode.TreeItemCollapsibleState.None
                        )
                    ];
                }

                return dependencies.map(d => new DependencyTreeItem(
                    d.name,
                    d.type || 'import',
                    d.file || '',
                    d.line || 0,
                    'dependency',
                    d.file ? `${d.file}:${d.line}` : d.type,
                    vscode.TreeItemCollapsibleState.None
                ));
            } catch (error) {
                return [
                    new DependencyTreeItem(
                        'Error loading dependencies',
                        '',
                        '',
                        0,
                        'error',
                        String(error),
                        vscode.TreeItemCollapsibleState.None
                    )
                ];
            }
        }

        return [];
    }
}

class DependencyTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly type: string,
        public readonly file: string,
        public readonly line: number,
        public readonly contextValue: string,
        public readonly description: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
        this.tooltip = file ? `${label} - ${file}:${line}` : label;

        switch (contextValue) {
            case 'dependency':
                this.iconPath = new vscode.ThemeIcon('package');
                if (file) {
                    this.command = {
                        command: 'cgc.goToDefinition',
                        title: 'Go to Definition',
                        arguments: [{ file, line }]
                    };
                }
                break;
            case 'info':
                this.iconPath = new vscode.ThemeIcon('info');
                break;
            case 'error':
                this.iconPath = new vscode.ThemeIcon('error');
                break;
        }
    }
}
