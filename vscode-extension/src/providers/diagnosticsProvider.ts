// src/providers/diagnosticsProvider.ts
import * as vscode from 'vscode';
import { CgcManager } from '../cgcManager';

export class CgcDiagnosticsProvider implements vscode.Disposable {
    private diagnosticCollection: vscode.DiagnosticCollection;
    private disposables: vscode.Disposable[] = [];

    constructor(private cgcManager: CgcManager) {
        this.diagnosticCollection = vscode.languages.createDiagnosticCollection('cgc');

        // Watch for document changes
        vscode.workspace.onDidSaveTextDocument(this.onDocumentSave, this, this.disposables);

        // Initial refresh
        this.refresh();
    }

    public async refresh(): Promise<void> {
        // Clear all diagnostics first
        this.diagnosticCollection.clear();

        const config = vscode.workspace.getConfiguration('cgc');
        const complexityThreshold = config.get<number>('complexityThreshold') || 10;

        try {
            // Get dead code
            const deadCode = await this.cgcManager.findDeadCode();

            // Get complex functions
            const complexFunctions = await this.cgcManager.analyzeComplexity(complexityThreshold);

            // Group diagnostics by file
            const diagnosticsByFile = new Map<string, vscode.Diagnostic[]>();

            // Add dead code diagnostics
            for (const item of deadCode) {
                if (!diagnosticsByFile.has(item.file)) {
                    diagnosticsByFile.set(item.file, []);
                }

                const line = Math.max(0, item.line - 1);
                const range = new vscode.Range(line, 0, line, 100);
                const diagnostic = new vscode.Diagnostic(
                    range,
                    `Unused ${item.type}: ${item.name}`,
                    vscode.DiagnosticSeverity.Warning
                );
                diagnostic.source = 'CGC';
                diagnostic.code = 'dead-code';
                diagnosticsByFile.get(item.file)!.push(diagnostic);
            }

            // Add complexity diagnostics
            for (const func of complexFunctions) {
                if (!diagnosticsByFile.has(func.file)) {
                    diagnosticsByFile.set(func.file, []);
                }

                const line = Math.max(0, func.line - 1);
                const range = new vscode.Range(line, 0, line, 100);
                const diagnostic = new vscode.Diagnostic(
                    range,
                    `High complexity (${func.complexity}): Consider refactoring`,
                    vscode.DiagnosticSeverity.Information
                );
                diagnostic.source = 'CGC';
                diagnostic.code = 'high-complexity';
                diagnosticsByFile.get(func.file)!.push(diagnostic);
            }

            // Set diagnostics for each file
            for (const [file, diagnostics] of diagnosticsByFile.entries()) {
                const uri = vscode.Uri.file(file);
                this.diagnosticCollection.set(uri, diagnostics);
            }
        } catch (error) {
            console.error('Error refreshing diagnostics:', error);
        }
    }

    private async onDocumentSave(document: vscode.TextDocument): Promise<void> {
        // Refresh diagnostics for the saved file
        await this.refresh();
    }

    public dispose(): void {
        this.diagnosticCollection.dispose();
        this.disposables.forEach(d => d.dispose());
    }
}
