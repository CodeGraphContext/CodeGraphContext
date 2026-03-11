// src/statusBarManager.ts
import * as vscode from 'vscode';

export class StatusBarManager {
    private statusBarItem: vscode.StatusBarItem;

    constructor() {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Left,
            100
        );
        this.statusBarItem.command = 'cgc.showStats';
        this.setReady();
        this.statusBarItem.show();
    }

    public setIndexing(isIndexing: boolean): void {
        if (isIndexing) {
            this.statusBarItem.text = '$(sync~spin) CGC: Indexing...';
            this.statusBarItem.tooltip = 'CodeGraphContext is indexing the workspace';
        } else {
            this.setReady();
        }
    }

    public setReady(): void {
        this.statusBarItem.text = '$(database) CGC: Ready';
        this.statusBarItem.tooltip = 'CodeGraphContext is ready. Click for statistics.';
    }

    public setError(message: string): void {
        this.statusBarItem.text = '$(error) CGC: Error';
        this.statusBarItem.tooltip = `CodeGraphContext error: ${message}`;
    }

    public dispose(): void {
        this.statusBarItem.dispose();
    }
}
