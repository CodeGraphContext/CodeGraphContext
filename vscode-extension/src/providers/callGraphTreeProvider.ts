// src/providers/callGraphTreeProvider.ts
import * as vscode from 'vscode';
import { CgcManager, FunctionInfo } from '../cgcManager';

export class CallGraphTreeProvider implements vscode.TreeDataProvider<CallGraphTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<CallGraphTreeItem | undefined | null | void> = new vscode.EventEmitter<CallGraphTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<CallGraphTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private currentFunction: string | undefined;

    constructor(private cgcManager: CgcManager) { }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    setCurrentFunction(functionName: string) {
        this.currentFunction = functionName;
        this.refresh();
    }

    getTreeItem(element: CallGraphTreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: CallGraphTreeItem): Promise<CallGraphTreeItem[]> {
        if (!element) {
            // Root level - show current function or prompt
            if (!this.currentFunction) {
                // Try to get function at cursor
                const editor = vscode.window.activeTextEditor;
                if (editor) {
                    const position = editor.selection.active;
                    const wordRange = editor.document.getWordRangeAtPosition(position);
                    if (wordRange) {
                        this.currentFunction = editor.document.getText(wordRange);
                    }
                }
            }

            if (!this.currentFunction) {
                return [
                    new CallGraphTreeItem(
                        'No function selected',
                        '',
                        0,
                        'info',
                        'Use "Show Call Graph" command',
                        vscode.TreeItemCollapsibleState.None
                    )
                ];
            }

            return [
                new CallGraphTreeItem(
                    this.currentFunction,
                    '',
                    0,
                    'current',
                    'Current function',
                    vscode.TreeItemCollapsibleState.Expanded
                )
            ];
        } else if (element.contextValue === 'current') {
            // Show callers and callees
            return [
                new CallGraphTreeItem(
                    'Callers',
                    '',
                    0,
                    'callers',
                    '',
                    vscode.TreeItemCollapsibleState.Collapsed
                ),
                new CallGraphTreeItem(
                    'Callees',
                    '',
                    0,
                    'callees',
                    '',
                    vscode.TreeItemCollapsibleState.Collapsed
                )
            ];
        } else if (element.contextValue === 'callers') {
            // Show callers
            try {
                const callers = await this.cgcManager.getCallers(this.currentFunction!);
                return callers.map(c => new CallGraphTreeItem(
                    c.name,
                    c.file,
                    c.line,
                    'function',
                    `${c.file}:${c.line}`,
                    vscode.TreeItemCollapsibleState.None
                ));
            } catch (error) {
                return [];
            }
        } else if (element.contextValue === 'callees') {
            // Show callees
            try {
                const callees = await this.cgcManager.getCallees(this.currentFunction!);
                return callees.map(c => new CallGraphTreeItem(
                    c.name,
                    c.file,
                    c.line,
                    'function',
                    `${c.file}:${c.line}`,
                    vscode.TreeItemCollapsibleState.None
                ));
            } catch (error) {
                return [];
            }
        }

        return [];
    }
}

class CallGraphTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly file: string,
        public readonly line: number,
        public readonly contextValue: string,
        public readonly description: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
        this.tooltip = file ? `${label} - ${file}:${line}` : label;

        switch (contextValue) {
            case 'current':
                this.iconPath = new vscode.ThemeIcon('target');
                break;
            case 'callers':
                this.iconPath = new vscode.ThemeIcon('arrow-left');
                break;
            case 'callees':
                this.iconPath = new vscode.ThemeIcon('arrow-right');
                break;
            case 'function':
                this.iconPath = new vscode.ThemeIcon('symbol-method');
                this.command = {
                    command: 'cgc.goToDefinition',
                    title: 'Go to Definition',
                    arguments: [{ file, line }]
                };
                break;
            case 'info':
                this.iconPath = new vscode.ThemeIcon('info');
                break;
        }
    }
}
