import * as cp from 'child_process';
import * as vscode from 'vscode';
import * as rpc from 'vscode-jsonrpc/node';
import * as fs from 'fs';
import * as path from 'path';
import { LineMessageReader, LineMessageWriter } from './lineBasedMessageRW';

export class McpClient {
    private connection: rpc.MessageConnection;
    private process: cp.ChildProcess;
    private isReady: boolean = false;
    private outputChannel?: vscode.OutputChannel;
    private initPromise: Promise<void> | null = null;

    constructor(cgcPath: string, workspaceRoot: string, outputChannel?: vscode.OutputChannel) {
        this.outputChannel = outputChannel;

        // ── Load workspace .env so sub-process has DB credentials ──────
        const envVars = this.loadWorkspaceEnv(workspaceRoot);
        const spawnEnv = { ...process.env, PYTHONUNBUFFERED: '1', ...envVars };

        this.outputChannel?.appendLine(
            `[MCP] Spawning: ${cgcPath} mcp start  (cwd=${workspaceRoot})`
        );
        if (envVars.DATABASE_TYPE) {
            this.outputChannel?.appendLine(`[MCP] Database backend: ${envVars.DATABASE_TYPE}`);
        }

        this.process = cp.spawn(cgcPath, ['mcp', 'start'], {
            cwd: workspaceRoot,
            env: spawnEnv
        });

        // 2. Establish JSON-RPC connection over Stdio (using Line Delimited JSON)
        this.connection = rpc.createMessageConnection(
            new LineMessageReader(this.process.stdout!),
            new LineMessageWriter(this.process.stdin!)
        );

        this.connection.listen();

        // Log errors from stderr (since stdout is used for RPC)
        let stderrBuf = '';
        this.process.stderr?.on('data', (data) => {
            const msg = data.toString();
            stderrBuf += msg;
            this.outputChannel?.appendLine(`[CGC Server] ${msg.trim()}`);
        });

        this.process.on('error', (error) => {
            const msg = `CGC Server Process Error: ${error.message}\n` +
                `Make sure the CGC path is correct in settings (cgc.cgcPath).`;
            vscode.window.showErrorMessage(msg);
            this.outputChannel?.appendLine(msg);
        });

        this.process.on('exit', (code) => {
            if (code !== 0 && code !== null) {
                const msg = `CGC Server exited with code ${code}`;
                this.outputChannel?.appendLine(msg);
                if (stderrBuf.toLowerCase().includes('connection refused') ||
                    stderrBuf.toLowerCase().includes('unable to connect')) {
                    vscode.window.showErrorMessage(
                        '❌ CGC: Database connection failed. ' +
                        'Open CGC Configuration (CGC: Open Configuration) to set your .env variables.',
                        'Open Configuration'
                    ).then(choice => {
                        if (choice === 'Open Configuration') {
                            vscode.commands.executeCommand('cgc.openConfig');
                        }
                    });
                }
                this.isReady = false;
            }
        });
    }

    /** Parse a .env file from the workspace root and return key=value pairs */
    private loadWorkspaceEnv(workspaceRoot: string): Record<string, string> {
        const envPath = path.join(workspaceRoot, '.env');
        if (!fs.existsSync(envPath)) {
            this.outputChannel?.appendLine(
                `[MCP] No .env found at ${envPath} — using process.env only. ` +
                `Run "CGC: Open Configuration" to create one.`
            );
            return {};
        }
        this.outputChannel?.appendLine(`[MCP] Loading .env from ${envPath}`);
        const content = fs.readFileSync(envPath, 'utf8');
        const result: Record<string, string> = {};
        for (const line of content.split('\n')) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) { continue; }
            const idx = trimmed.indexOf('=');
            if (idx === -1) { continue; }
            const key = trimmed.slice(0, idx).trim();
            let val = trimmed.slice(idx + 1).trim();
            if ((val.startsWith('"') && val.endsWith('"')) ||
                (val.startsWith("'") && val.endsWith("'"))) {
                val = val.slice(1, -1);
            }
            if (key && val !== undefined) { result[key] = val; }
        }
        return result;
    }

    async initialize(): Promise<void> {
        if (this.isReady) return;
        if (this.initPromise) return this.initPromise;

        this.initPromise = this._doInitialize();
        return this.initPromise;
    }

    private _doInitialize(): Promise<void> {
        return Promise.resolve(vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'CodeGraphContext: Starting MCP server…',
            cancellable: false
        }, async (progress) => {
            try {
                // ── Step 1: wait for the Python process to emit its first output ──
                // This confirms it has started and is processing.
                progress.report({ message: 'Waiting for cgc server to start…' });
                await this._waitForProcessReady(20_000);   // up to 20 s
                this.outputChannel?.appendLine('[MCP] Process produced output — sending initialize…');

                // ── Step 2: send the MCP initialize handshake ──────────────────
                progress.report({ message: 'Handshaking with MCP server…' });
                const timeoutMs = 45_000;
                const response = await Promise.race([
                    this.connection.sendRequest('initialize', {
                        protocolVersion: '2024-11-05',
                        clientInfo: { name: 'vscode-extension', version: '0.1.0' }
                    }),
                    new Promise<never>((_, rej) =>
                        setTimeout(() => rej(new Error(
                            `MCP initialize timed out after ${timeoutMs / 1000}s. ` +
                            `Check the "CodeGraphContext" output channel for server logs.`
                        )), timeoutMs)
                    )
                ]);

                this.outputChannel?.appendLine(`[MCP] Initialize OK: ${JSON.stringify(response)}`);
                this.connection.sendNotification('notifications/initialized', {});
                this.isReady = true;
                progress.report({ message: 'Ready!' });
                this.outputChannel?.appendLine('[MCP] Client ready.');
            } catch (error) {
                this.initPromise = null;   // allow retry next call
                this.outputChannel?.appendLine(`[MCP] Initialization failed: ${error}`);
                throw error;
            }
        }));  // end withProgress + Promise.resolve
    }

    /**
     * Wait for the MCP server to be ready.
     * IMPORTANT: we ONLY listen on stderr here — stdout is the JSON-RPC transport
     * channel and must not be touched before the RPC connection takes over.
     * The cgc MCP server writes all startup logs to stderr.
     */
    private _waitForProcessReady(timeoutMs: number): Promise<void> {
        return new Promise((resolve, reject) => {
            let resolved = false;
            let stderrAccum = '';

            const done = (err?: Error) => {
                if (!resolved) {
                    resolved = true;
                    clearTimeout(timer);
                    err ? reject(err) : resolve();
                }
            };

            // Collect stderr and look for the server-ready marker
            // cgc mcp start prints one of these when it is accepting requests:
            //   "Starting CodeGraphContext Server"
            //   "Server running" / "MCP server" / "Listening"
            const READY_MARKERS = [
                'starting codeGraphContext server',
                'server running',
                'mcp server',
                'listening',
                'services initialized',
            ];

            const onStderr = (chunk: Buffer) => {
                const text = chunk.toString();
                stderrAccum += text;
                this.outputChannel?.appendLine(`[CGC Server] ${text.trimEnd()}`);

                // Resolve as soon as we see a ready marker OR any output
                // (some startup message means Python at least launched)
                if (!resolved) {
                    const lower = stderrAccum.toLowerCase();
                    if (READY_MARKERS.some(m => lower.includes(m)) || stderrAccum.length > 0) {
                        // Give the server a short extra moment to finish initializing
                        // before we send the JSON-RPC handshake
                        setTimeout(() => done(), 1500);
                    }
                }
            };

            this.process.stderr?.on('data', onStderr);

            // If the process dies, report the real error from stderr
            this.process.once('exit', (code) => {
                this.process.stderr?.off('data', onStderr);
                if (!resolved) {
                    const hint = stderrAccum.includes('neo4j:7687') || stderrAccum.includes('DNS')
                        ? ' Tip: The .env is pointing to "bolt://neo4j:7687" (Docker hostname). ' +
                        'Open "CGC: Open Configuration" and change NEO4J_URI to bolt://localhost:7687, ' +
                        'or switch DATABASE_TYPE to falkordb for zero-config local use.'
                        : ' Open "CGC: Open Configuration" to check your database settings.';
                    done(new Error(
                        `CGC server exited with code ${code} before it was ready.${hint}\n` +
                        `Last server output:\n${stderrAccum.slice(-600)}`
                    ));
                }
            });

            const timer = setTimeout(() => {
                done(new Error(
                    `CGC server did not respond within ${timeoutMs / 1000}s.\n` +
                    `Last output: ${stderrAccum.slice(-300) || '(none — cgc binary may not be found)'}\n` +
                    `Try running "CGC: Open Configuration" to fix the path or database settings.`
                ));
            }, timeoutMs);
        });
    }

    async callTool(toolName: string, args: any): Promise<any> {
        if (!this.isReady) {
            await this.initialize();
        }

        // Call a tool defined in server.py
        try {
            this.outputChannel?.appendLine(`[MCP] Calling tool: ${toolName} with args: ${JSON.stringify(args)}`);
            const response: any = await this.connection.sendRequest('tools/call', {
                name: toolName,
                arguments: args
            });
            this.outputChannel?.appendLine(`[MCP] Tool response: ${JSON.stringify(response)}`);

            // Result is wrapped in { content: [{ type: 'text', text: '...' }] } structure from MCP spec
            if (response && response.content && Array.isArray(response.content) && response.content.length > 0) {
                const resultText = response.content[0].text;
                try {
                    return JSON.parse(resultText);
                } catch (e) {
                    // If it's not JSON, return the text directly
                    return resultText;
                }
            } else if (response && response.isError) {
                // Handle MCP error format
                throw new Error(response.content?.[0]?.text || "Unknown error");
            }

            return response;
        } catch (error) {
            console.error(`Tool call '${toolName}' failed:`, error);
            this.outputChannel?.appendLine(`Tool call '${toolName}' failed: ${error}`);
            throw error;
        }
    }

    // --- Helper Wrapper Methods matching previous CgcManager functionality ---

    async getStats() {
        return this.callTool('get_repository_stats', {});
    }

    async search(query: string) {
        // server.py: find_code
        return this.callTool('find_code', { query: query });
    }

    async indexWorkspace(path: string) {
        // server.py: add_code_to_graph
        // args: paths=[path]
        return this.callTool('add_code_to_graph', { paths: [path] });
    }

    async watchDirectory(path: string) {
        // server.py: watch_directory
        return this.callTool('watch_directory', { path: path });
    }

    async getFunctions(projectPath?: string) {
        const cypherQuery = projectPath
            ? `MATCH (r:Repository {path: '${projectPath}'})-[:CONTAINS*]->(file:File)-[:CONTAINS]->(f:Function) RETURN f.name as name, file.path as file, f.line_number as line LIMIT 1000`
            : `MATCH (file:File)-[:CONTAINS]->(f:Function) RETURN f.name as name, file.path as file, f.line_number as line LIMIT 1000`;
        return this.callTool('execute_cypher_query', { cypher_query: cypherQuery });
    }

    async getClasses(projectPath?: string) {
        const cypherQuery = projectPath
            ? `MATCH (r:Repository {path: '${projectPath}'})-[:CONTAINS*]->(file:File)-[:CONTAINS]->(c:Class) RETURN c.name as name, file.path as file, c.line_number as line LIMIT 1000`
            : `MATCH (file:File)-[:CONTAINS]->(c:Class) RETURN c.name as name, file.path as file, c.line_number as line LIMIT 1000`;
        return this.callTool('execute_cypher_query', { cypher_query: cypherQuery });
    }

    async analyzeCalls() {
        // server.py: analyze_code_relationships
        // But mapped to analyzeCalls command in extension, usually just a list.
        // Let's use custom cypher or the dedicated tool if available.
        // server.py map: "analyze_code_relationships": self.analyze_code_relationships_tool
        // Tool arg: relation_types=['CALLS']
        return this.callTool('analyze_code_relationships', { relation_types: ['CALLS'] });
    }

    async executeCypher(query: string) {
        return this.callTool('execute_cypher_query', { cypher_query: query });
    }

    dispose() {
        try {
            this.connection.dispose();
            this.process.kill();
        } catch (e) {
            console.error('Error disposing McpClient:', e);
        }
    }
}
