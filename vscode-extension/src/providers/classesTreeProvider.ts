// src/providers/classesTreeProvider.ts
import * as vscode from 'vscode';
import { CgcManager, FunctionInfo } from '../cgcManager';
import * as path from 'path';

export class ClassesTreeProvider implements vscode.TreeDataProvider<ClassTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<ClassTreeItem | undefined | null | void> = new vscode.EventEmitter<ClassTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<ClassTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    constructor(private cgcManager: CgcManager) { }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: ClassTreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: ClassTreeItem): Promise<ClassTreeItem[]> {
        if (!element) {
            try {
                const classes = await this.cgcManager.getClasses();

                // Group classes by file
                const fileMap = new Map<string, FunctionInfo[]>();
                for (const cls of classes) {
                    if (!fileMap.has(cls.file)) { fileMap.set(cls.file, []); }
                    fileMap.get(cls.file)!.push(cls);
                }

                const items: ClassTreeItem[] = [];
                for (const [file, clss] of fileMap.entries()) {
                    items.push(new ClassTreeItem(
                        path.basename(file),
                        file,
                        0,
                        'file',
                        `${clss.length} classes`,
                        vscode.TreeItemCollapsibleState.Collapsed,
                        clss
                    ));
                }

                return items.sort((a, b) => a.label.localeCompare(b.label));
            } catch (error) {
                return [];
            }
        } else if (element.contextValue === 'file') {
            return element.classes.map(c => new ClassTreeItem(
                c.name,
                c.file,
                c.line,
                'class',
                `Line ${c.line} • click to visualize inheritance`,
                vscode.TreeItemCollapsibleState.None
            ));
        }

        return [];
    }
}

export class ClassTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly file: string,
        public readonly line: number,
        public readonly contextValue: string,
        public readonly description: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly classes: FunctionInfo[] = []
    ) {
        super(label, collapsibleState);
        this.tooltip = contextValue === 'class'
            ? `${label} — click to visualize inheritance graph\n${file}:${line}`
            : `${label} (${file})`;

        if (contextValue === 'file') {
            this.iconPath = new vscode.ThemeIcon('file-code');
        } else {
            // Purple type-hierarchy icon — matches the class colour in the graph
            this.iconPath = new vscode.ThemeIcon(
                'type-hierarchy-sub',
                new vscode.ThemeColor('charts.purple')
            );
            // Single-click → show inheritance graph
            this.command = {
                command: 'cgc.showInheritance',
                title: 'Show Inheritance Graph',
                arguments: [this]
            };
        }
    }
}
