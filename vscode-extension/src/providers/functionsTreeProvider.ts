// src/providers/functionsTreeProvider.ts
import * as vscode from 'vscode';
import { CgcManager, FunctionInfo } from '../cgcManager';
import * as path from 'path';

export class FunctionsTreeProvider implements vscode.TreeDataProvider<FunctionTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<FunctionTreeItem | undefined | null | void> = new vscode.EventEmitter<FunctionTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<FunctionTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    constructor(private cgcManager: CgcManager) { }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: FunctionTreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: FunctionTreeItem): Promise<FunctionTreeItem[]> {
        if (!element) {
            // Root level - show all functions grouped by file
            try {
                const functions = await this.cgcManager.getFunctions();

                // Group functions by file
                const fileMap = new Map<string, FunctionInfo[]>();
                for (const func of functions) {
                    if (!fileMap.has(func.file)) {
                        fileMap.set(func.file, []);
                    }
                    fileMap.get(func.file)!.push(func);
                }

                // Create tree items for files
                const items: FunctionTreeItem[] = [];
                for (const [file, funcs] of fileMap.entries()) {
                    items.push(new FunctionTreeItem(
                        path.basename(file),
                        file,
                        0,
                        'file',
                        `${funcs.length} functions`,
                        vscode.TreeItemCollapsibleState.Collapsed,
                        funcs
                    ));
                }

                return items.sort((a, b) => a.label.localeCompare(b.label));
            } catch (error) {
                return [];
            }
        } else if (element.contextValue === 'file') {
            // Show functions in this file
            return element.functions.map(f => new FunctionTreeItem(
                f.name,
                f.file,
                f.line,
                'function',
                `Line ${f.line}`,
                vscode.TreeItemCollapsibleState.None
            ));
        }

        return [];
    }
}

class FunctionTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly file: string,
        public readonly line: number,
        public readonly contextValue: string,
        public readonly description: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly functions: FunctionInfo[] = []
    ) {
        super(label, collapsibleState);
        this.tooltip = `${label} - ${file}:${line}`;

        if (contextValue === 'file') {
            this.iconPath = new vscode.ThemeIcon('file-code');
        } else {
            this.iconPath = new vscode.ThemeIcon('symbol-method');
        }

        // Make functions clickable
        if (contextValue === 'function') {
            this.command = {
                command: 'cgc.goToDefinition',
                title: 'Go to Definition',
                arguments: [{ file, line }]
            };
        }
    }
}
