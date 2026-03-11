// src/providers/codeLensProvider.ts
import * as vscode from 'vscode';
import { CgcManager } from '../cgcManager';

export class CgcCodeLensProvider implements vscode.CodeLensProvider {
    private _onDidChangeCodeLenses: vscode.EventEmitter<void> = new vscode.EventEmitter<void>();
    public readonly onDidChangeCodeLenses: vscode.Event<void> = this._onDidChangeCodeLenses.event;

    constructor(private cgcManager: CgcManager) { }

    public refresh(): void {
        this._onDidChangeCodeLenses.fire();
    }

    public async provideCodeLenses(
        document: vscode.TextDocument,
        token: vscode.CancellationToken
    ): Promise<vscode.CodeLens[]> {
        const codeLenses: vscode.CodeLens[] = [];

        try {
            // Get all functions in this file
            const functions = await this.cgcManager.getFunctions();
            const fileFunctions = functions.filter(f => f.file === document.uri.fsPath);

            for (const func of fileFunctions) {
                const line = Math.max(0, func.line - 1);
                const range = new vscode.Range(line, 0, line, 0);

                // Get callers count
                const callers = await this.cgcManager.getCallers(func.name);
                const callersCount = callers.length;

                // Get callees count
                const callees = await this.cgcManager.getCallees(func.name);
                const calleesCount = callees.length;

                // Add "X callers" code lens
                if (callersCount > 0) {
                    codeLenses.push(new vscode.CodeLens(range, {
                        title: `$(arrow-left) ${callersCount} caller${callersCount !== 1 ? 's' : ''}`,
                        command: 'cgc.showCallers',
                        arguments: [{ label: func.name }]
                    }));
                }

                // Add "X callees" code lens
                if (calleesCount > 0) {
                    codeLenses.push(new vscode.CodeLens(range, {
                        title: `$(arrow-right) ${calleesCount} callee${calleesCount !== 1 ? 's' : ''}`,
                        command: 'cgc.showCallees',
                        arguments: [{ label: func.name }]
                    }));
                }

                // Add "Show Call Graph" code lens
                codeLenses.push(new vscode.CodeLens(range, {
                    title: '$(graph) Show Call Graph',
                    command: 'cgc.showCallGraph',
                    arguments: [{ label: func.name }]
                }));
            }
        } catch (error) {
            console.error('Error providing code lenses:', error);
        }

        return codeLenses;
    }
}
