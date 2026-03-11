import * as vscode from 'vscode';
import * as path from 'path';
import { McpClient } from './mcpClient';

export interface SearchResult {
    name: string;
    type: string;
    file: string;
    line: number;
}

export interface FunctionInfo {
    name: string;
    file: string;
    line: number;
    complexity?: number;
    type?: string;
}

export interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

export interface GraphNode {
    id: string;
    label: string;
    type: string;
    file?: string;
    line?: number;
    depth?: number;  // hop distance from focus node; negative = upstream caller chain
}

export interface GraphEdge {
    source: string;
    target: string;
    type: string;
}

export class CgcManager {
    private context: vscode.ExtensionContext;
    private mcpClient: McpClient;
    private outputChannel: vscode.OutputChannel;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.outputChannel = vscode.window.createOutputChannel("CodeGraphContext");
        const cgcPath = this.findCgcExecutable();

        this.outputChannel.appendLine(`[Init] Initializing CgcManager`);
        this.outputChannel.appendLine(`[Init] Using cgc path: ${cgcPath}`);

        let workspaceRoot = '.';
        if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
            workspaceRoot = vscode.workspace.workspaceFolders[0].uri.fsPath;
        }

        // Pass outputChannel to McpClient
        this.mcpClient = new McpClient(cgcPath, workspaceRoot, this.outputChannel);
    }

    /**
     * Find the cgc executable, checking virtual environments first
     */
    private findCgcExecutable(): string {
        const config = vscode.workspace.getConfiguration('cgc');
        const configuredPath = config.get<string>('cgcPath');

        // If user has configured a specific path, use it
        if (configuredPath && configuredPath !== 'cgc') {
            this.outputChannel.appendLine(`[Init] Using configured cgc path: ${configuredPath}`);
            return configuredPath;
        }

        // Try to find cgc in virtual environments
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders && workspaceFolders.length > 0) {
            const workspaceRoot = workspaceFolders[0].uri.fsPath;

            // Common virtual environment folder names (NOT .env which is the dotenv config file)
            const venvNames = ['.venv', 'venv', 'env', '.virtualenv', 'virtualenv'];

            for (const name of venvNames) {
                const venvPath = path.join(workspaceRoot, name);
                const cgcInVenv = this.getCgcPathInVenv(venvPath);
                if (cgcInVenv && this.fileExists(cgcInVenv)) {
                    this.outputChannel.appendLine(`[Init] Found cgc in venv: ${cgcInVenv}`);
                    return cgcInVenv;
                }
            }
        }

        // Try to use Python extension's selected interpreter
        const pythonPath = this.getPythonPath();
        if (pythonPath) {
            const cgcInPythonEnv = this.getCgcPathFromPython(pythonPath);
            if (cgcInPythonEnv && this.fileExists(cgcInPythonEnv)) {
                this.outputChannel.appendLine(`Found cgc using Python interpreter: ${cgcInPythonEnv}`);
                return cgcInPythonEnv;
            }
        }

        // Fallback to system PATH
        this.outputChannel.appendLine('Using cgc from system PATH');
        return 'cgc';
    }

    /**
     * Get cgc path within a virtual environment
     */
    private getCgcPathInVenv(venvPath: string): string {
        const isWindows = process.platform === 'win32';
        if (isWindows) {
            return path.join(venvPath, 'Scripts', 'cgc.exe');
        } else {
            return path.join(venvPath, 'bin', 'cgc');
        }
    }

    /**
     * Get cgc path from Python interpreter path
     */
    private getCgcPathFromPython(pythonPath: string): string {
        const pythonDir = path.dirname(pythonPath);
        const isWindows = process.platform === 'win32';

        if (isWindows) {
            // On Windows, Scripts folder is at the same level as python.exe
            return path.join(pythonDir, 'cgc.exe');
        } else {
            // On Unix, bin folder contains both python and cgc
            return path.join(pythonDir, 'cgc');
        }
    }

    /**
     * Get Python path from VS Code Python extension
     */
    private getPythonPath(): string | undefined {
        const config = vscode.workspace.getConfiguration('python');
        const pythonPath = config.get<string>('pythonPath') || config.get<string>('defaultInterpreterPath');
        return pythonPath;
    }

    /**
     * Check if a file exists synchronously
     */
    private fileExists(filePath: string): boolean {
        try {
            const fs = require('fs');
            return fs.existsSync(filePath);
        } catch {
            return false;
        }
    }

    /**
     * Index a workspace directory
     */
    async indexWorkspace(workspacePath: string): Promise<void> {
        // Use the add_code_to_graph_tool
        this.outputChannel.appendLine(`[Index] Indexing workspace: ${workspacePath}`);
        await this.mcpClient.callTool('add_code_to_graph', { paths: [workspacePath] });
    }

    /**
     * Re-index a workspace directory (force)
     */
    async reindexWorkspace(workspacePath: string): Promise<void> {
        this.outputChannel.appendLine(`[Reindex] Re-indexing workspace: ${workspacePath}`);
        await this.mcpClient.callTool('add_code_to_graph', { paths: [workspacePath] });
    }

    /**
     * Update a single file in the index
     */
    async updateFile(filePath: string): Promise<void> {
        try {
            this.outputChannel.appendLine(`[Update] Updating file: ${filePath}`);
            await this.mcpClient.callTool('add_code_to_graph', { paths: [filePath] });
        } catch (error) {
            this.outputChannel.appendLine(`Failed to update file: ${error}`);
        }
    }

    /**
     * Search for code elements
     */
    async search(query: string): Promise<SearchResult[]> {
        try {
            this.outputChannel.appendLine(`[Search] Searching for: ${query}`);
            const response = await this.mcpClient.callTool('find_code', { query });
            return response.results.map((r: any) => ({
                name: r.name,
                type: r.search_type || r.type || 'unknown',
                file: r.path || r.file_path || r.file,
                line: r.line_number || r.start_line || r.line || 1
            }));
        } catch (error) {
            this.outputChannel.appendLine(`Search failed: ${error}`);
            return [];
        }
    }

    /**
     * Get list of all indexed projects
     */
    async getProjects(): Promise<any[]> {
        try {
            const cypherQuery = `MATCH (r:Repository) RETURN r.name as name, r.path as path, r.is_dependency as is_dependency`;
            const response = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: cypherQuery });

            if (response.success && response.results) {
                return response.results.map((r: any) => ({
                    name: r.name,
                    path: r.path,
                    type: r.is_dependency ? 'Dependency' : 'Project',
                    files: 0,
                    functions: 0
                }));
            }
            return [];
        } catch (error) {
            this.outputChannel.appendLine(`Failed to get projects: ${error}`);
            return [];
        }
    }

    /**
     * Get all functions in the workspace
     */
    async getFunctions(projectPath?: string): Promise<FunctionInfo[]> {
        try {
            // Function nodes have 'path' property, not 'file' property on the node itself, but let's confirm.
            // CodeFinder uses node.path.
            const cypherQuery = projectPath
                ? `MATCH (r:Repository {path: '${projectPath}'})-[:CONTAINS*]->(file:File)-[:CONTAINS]->(f:Function) RETURN f.name as name, file.path as file, f.line_number as line LIMIT 1000`
                : `MATCH (file:File)-[:CONTAINS]->(f:Function) RETURN f.name as name, file.path as file, f.line_number as line LIMIT 1000`;

            const response = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: cypherQuery });

            if (response.success && response.results) {
                return response.results.map((r: any) => ({
                    name: r.name,
                    file: r.file, // From 'file.path as file'
                    line: r.line || 1
                }));
            }
            return [];
        } catch (error) {
            this.outputChannel.appendLine(`Failed to get functions: ${error}`);
            return [];
        }
    }

    /**
     * Get all classes in the workspace
     */
    async getClasses(projectPath?: string): Promise<FunctionInfo[]> {
        try {
            const cypherQuery = projectPath
                ? `MATCH (r:Repository {path: '${projectPath}'})-[:CONTAINS*]->(file:File)-[:CONTAINS]->(c:Class) RETURN c.name as name, file.path as file, c.line_number as line LIMIT 1000`
                : `MATCH (file:File)-[:CONTAINS]->(c:Class) RETURN c.name as name, file.path as file, c.line_number as line LIMIT 1000`;

            const response = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: cypherQuery });

            if (response.success && response.results) {
                return response.results.map((r: any) => ({
                    name: r.name,
                    file: r.file,
                    line: r.line || 1
                }));
            }
            return [];
        } catch (error) {
            this.outputChannel.appendLine(`Failed to get classes: ${error}`);
            return [];
        }
    }

    /**
     * Get call graph for a function (1 hop — direct callers + callees)
     */
    async getCallGraph(functionName: string): Promise<GraphData> {
        try {
            const callers = await this.getCallers(functionName);
            const callees = await this.getCallees(functionName);

            const nodes: GraphNode[] = [];
            const edges: GraphEdge[] = [];
            const nodeSet = new Set<string>();

            nodes.push({ id: functionName, label: functionName, type: 'function', depth: 0 });
            nodeSet.add(functionName);

            for (const caller of callers) {
                if (!nodeSet.has(caller.name)) {
                    nodes.push({ id: caller.name, label: caller.name, type: 'function', file: caller.file, line: caller.line, depth: -1 });
                    nodeSet.add(caller.name);
                }
                edges.push({ source: caller.name, target: functionName, type: 'calls' });
            }

            for (const callee of callees) {
                if (!nodeSet.has(callee.name)) {
                    nodes.push({ id: callee.name, label: callee.name, type: 'function', file: callee.file, line: callee.line, depth: 1 });
                    nodeSet.add(callee.name);
                }
                edges.push({ source: functionName, target: callee.name, type: 'calls' });
            }

            return { nodes, edges };
        } catch (error) {
            this.outputChannel.appendLine(`Failed to get call graph: ${error}`);
            return { nodes: [], edges: [] };
        }
    }

    /**
     * Get the full N-hop call chain — both upstream (callers-of-callers) and
     * downstream (callees-of-callees). `depth` controls how many hops to traverse.
     * Nodes carry a `depth` property: 0 = focus, positive = downstream, negative = upstream.
     */
    async getDeepCallGraph(functionName: string, depth: number): Promise<GraphData> {
        const nodes: GraphNode[] = [];
        const edges: GraphEdge[] = [];
        const nodeSet = new Set<string>();
        const safe = functionName.replace(/'/g, "\\'");

        // Always include the focus node
        nodes.push({ id: functionName, label: functionName, type: 'function', depth: 0 });
        nodeSet.add(functionName);

        try {
            // ── 1. Downstream: functions this function eventually calls ──────────
            const downQ = `
                MATCH path = (start:Function {name: '${safe}'})-[:CALLS*1..${depth}]->(target:Function)
                WITH target, min(length(path)) as hopDist
                OPTIONAL MATCH (f:File)-[:CONTAINS]->(target)
                RETURN target.name as name, f.path as file, target.line_number as line, hopDist as depth
                ORDER BY hopDist
                LIMIT 500
            `;
            const downRes = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: downQ });
            if (downRes.success && downRes.results) {
                for (const r of downRes.results) {
                    if (r.name && !nodeSet.has(r.name)) {
                        nodes.push({ id: r.name, label: r.name, type: 'function', file: r.file, line: r.line, depth: r.depth });
                        nodeSet.add(r.name);
                    }
                }
            }

            // ── 2. Upstream: functions that eventually call this function ────────
            const upQ = `
                MATCH path = (caller:Function)-[:CALLS*1..${depth}]->(target:Function {name: '${safe}'})
                WITH caller, min(length(path)) as hopDist
                OPTIONAL MATCH (f:File)-[:CONTAINS]->(caller)
                RETURN caller.name as name, f.path as file, caller.line_number as line, -(hopDist) as depth
                ORDER BY hopDist
                LIMIT 500
            `;
            const upRes = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: upQ });
            if (upRes.success && upRes.results) {
                for (const r of upRes.results) {
                    if (r.name && !nodeSet.has(r.name)) {
                        nodes.push({ id: r.name, label: r.name, type: 'function', file: r.file, line: r.line, depth: r.depth });
                        nodeSet.add(r.name);
                    }
                }
            }

            // ── 3. Collect all CALLS edges between the nodes found above ─────────
            //    We use a targeted list-based query to get only edges within our set
            const allNames = [...nodeSet].map(n => `'${n.replace(/'/g, "\\'")}' `).join(', ');
            if (allNames.length > 0) {
                const edgeQ = `
                    MATCH (a:Function)-[:CALLS]->(b:Function)
                    WHERE a.name IN [${allNames}] AND b.name IN [${allNames}]
                    RETURN a.name as source, b.name as target
                    LIMIT 3000
                `;
                const edgeRes = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: edgeQ });
                if (edgeRes.success && edgeRes.results) {
                    for (const r of edgeRes.results) {
                        edges.push({ source: r.source, target: r.target, type: 'calls' });
                    }
                }
            }
        } catch (error) {
            this.outputChannel.appendLine(`Failed to get deep call graph: ${error}`);
        }

        this.outputChannel.appendLine(`[DeepCallGraph] ${nodes.length} nodes, ${edges.length} edges for '${functionName}' depth=${depth}`);
        return { nodes, edges };
    }

    /**
     * Get callers of a function
     */
    async getCallers(functionName: string): Promise<FunctionInfo[]> {
        try {
            this.outputChannel.appendLine(`[CgcManager] Fetching callers for: ${functionName}`);

            // Use Cypher query instead of tool call to avoid potential CLI argument issues
            // Matches: (CallerFunction)-[:CALLS]->(TargetFunction)
            // And retrieves the file path from the File node containing the CallerFunction
            const cypherQuery = `
                MATCH (caller:Function)-[:CALLS]->(target:Function {name: '${functionName}'})
                OPTIONAL MATCH (file:File)-[:CONTAINS]->(caller)
                RETURN caller.name as name, file.path as file, caller.line_number as line
                LIMIT 100
            `;

            this.outputChannel.appendLine(`[CgcManager] Executing Cypher: ${cypherQuery}`);
            const response = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: cypherQuery });
            this.outputChannel.appendLine(`[CgcManager] Cypher response: ${JSON.stringify(response, null, 2)}`);

            if (response.success && response.results) {
                return response.results.map((r: any) => ({
                    name: r.name,
                    file: r.file || '',
                    line: r.line || 1,
                    type: 'caller'
                }));
            }
            return [];
        } catch (error: any) {
            this.outputChannel.appendLine(`Failed to get callers: ${error.message || error}`);
            return [];
        }
    }

    /**
     * Get callees of a function (what this function calls)
     */
    async getCallees(functionName: string): Promise<FunctionInfo[]> {
        try {
            this.outputChannel.appendLine(`[CgcManager] Fetching callees for: ${functionName}`);

            // Use Cypher query instead of tool call
            const cypherQuery = `
                MATCH (source:Function {name: '${functionName}'})-[:CALLS]->(target:Function)
                OPTIONAL MATCH (file:File)-[:CONTAINS]->(target)
                RETURN target.name as name, file.path as file, target.line_number as line
                LIMIT 100
            `;

            this.outputChannel.appendLine(`[CgcManager] Executing Cypher: ${cypherQuery}`);
            const response = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: cypherQuery });
            this.outputChannel.appendLine(`[CgcManager] Cypher response: ${JSON.stringify(response, null, 2)}`);

            if (response.success && response.results) {
                return response.results.map((r: any) => ({
                    name: r.name,
                    file: r.file || '',
                    line: r.line || 1,
                    type: 'callee'
                }));
            }
            return [];
        } catch (error: any) {
            this.outputChannel.appendLine(`Failed to get callees: ${error.message || error}`);
            return [];
        }
    }

    /**
     * Get dependencies for a file
     */
    async getDependencies(filePath: string): Promise<any[]> {
        try {
            const cypherQuery = `
                MATCH (file:File {path: '${filePath}'})-[:IMPORTS]->(dep)
                RETURN dep.name as name, 'import' as type, dep.path as file, dep.line_number as line
            `;
            const response = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: cypherQuery });
            if (response.success && response.results) {
                return response.results;
            }
            return [];
        } catch (error) {
            this.outputChannel.appendLine(`Failed to get dependencies: ${error}`);
            return [];
        }
    }

    /**
     * Analyze all calls in the workspace
     */
    async analyzeCalls(): Promise<any[]> {
        try {
            // Updated to use 'path' and 'line_number', which are consistent with CodeFinder
            const cypherQuery = `MATCH (a)-[:CALLS]->(b) RETURN a.name as caller, b.name as callee, a.path as file, a.line_number as line LIMIT 100`;
            const response = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: cypherQuery });
            if (response.success && response.results) {
                return response.results;
            }
            return [];
        } catch (error) {
            this.outputChannel.appendLine(`Failed to analyze calls: ${error}`);
            return [];
        }
    }

    /**
     * Analyze complexity
     */
    async analyzeComplexity(threshold: number): Promise<FunctionInfo[]> {
        try {
            const response = await this.mcpClient.callTool('find_most_complex_functions', { limit: 100 });
            if (response.success && response.results) {
                return response.results
                    .filter((r: any) => r.complexity >= threshold)
                    .map((r: any) => ({
                        name: r.name,
                        complexity: r.complexity,
                        file: r.path || r.file_path || r.file,
                        line: r.line_number || r.start_line || r.line || 1
                    }));
            }
            return [];
        } catch (error) {
            this.outputChannel.appendLine(`Failed to analyze complexity: ${error}`);
            return [];
        }
    }

    /**
     * Find dead code
     */
    async findDeadCode(): Promise<SearchResult[]> {
        try {
            const response = await this.mcpClient.callTool('find_dead_code', {});
            // The tool returns { success: true, results: { potentially_unused_functions: [...] } }
            if (response.success && response.results && response.results.potentially_unused_functions) {
                return response.results.potentially_unused_functions.map((r: any) => ({
                    name: r.name,
                    type: r.type || 'unknown',
                    file: r.path || r.file_path || r.file,
                    line: r.line_number || r.start_line || r.line || 1
                }));
            }
            return [];
        } catch (error) {
            this.outputChannel.appendLine(`Failed to find dead code: ${error}`);
            // Log full response for debugging
            this.outputChannel.appendLine(`Error details: ${JSON.stringify(error)}`);
            return [];
        }
    }

    /**
     * Get project statistics
     */
    async getStats(): Promise<any> {
        try {
            const response = await this.mcpClient.callTool('get_repository_stats', {});
            return response.stats || response;
        } catch (error) {
            this.outputChannel.appendLine(`Failed to get stats: ${error}`);
            return {};
        }
    }

    /**
     * Get the full repository graph for a given project path (or all indexed) —
     * Returns all repos, files, classes, functions and their CALLS/CONTAINS edges.
     */
    async getRepoGraph(projectPath?: string): Promise<GraphData> {
        const nodes: GraphNode[] = [];
        const edges: GraphEdge[] = [];
        const nodeSet = new Set<string>();

        const addNode = (id: string, label: string, type: string, extra: Partial<GraphNode> = {}) => {
            if (!nodeSet.has(id)) {
                nodes.push({ id, label, type, ...extra });
                nodeSet.add(id);
            }
        };

        try {
            // 1. All files (and their parent repo)
            const pathFilter = projectPath ? `{path: '${projectPath}'}` : '';
            const fileQ = `
                MATCH (r:Repository ${pathFilter})-[:CONTAINS*]->(f:File)
                RETURN r.path as repo, f.path as file, f.name as fname
                LIMIT 500
            `;
            const fileRes = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: fileQ });
            if (fileRes.success && fileRes.results) {
                for (const row of fileRes.results) {
                    addNode(row.repo, row.repo.split('/').pop() || row.repo, 'repository', { file: row.repo });
                    addNode(row.file, row.fname || row.file.split('/').pop() || row.file, 'file', { file: row.file });
                    edges.push({ source: row.repo, target: row.file, type: 'contains' });
                }
            }

            // 2. Functions inside files
            const funcQ = `
                MATCH (f:File)-[:CONTAINS]->(fn:Function)
                ${projectPath ? `WHERE f.path STARTS WITH '${projectPath}'` : ''}
                RETURN f.path as file, fn.name as name, fn.line_number as line
                LIMIT 2000
            `;
            const funcRes = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: funcQ });
            if (funcRes.success && funcRes.results) {
                for (const row of funcRes.results) {
                    const fnId = `fn:${row.file}:${row.name}`;
                    addNode(fnId, row.name, 'function', { file: row.file, line: row.line });
                    if (nodeSet.has(row.file)) {
                        edges.push({ source: row.file, target: fnId, type: 'contains' });
                    }
                }
            }

            // 3. Classes inside files
            const classQ = `
                MATCH (f:File)-[:CONTAINS]->(c:Class)
                ${projectPath ? `WHERE f.path STARTS WITH '${projectPath}'` : ''}
                RETURN f.path as file, c.name as name, c.line_number as line
                LIMIT 1000
            `;
            const classRes = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: classQ });
            if (classRes.success && classRes.results) {
                for (const row of classRes.results) {
                    const cId = `cls:${row.file}:${row.name}`;
                    addNode(cId, row.name, 'class', { file: row.file, line: row.line });
                    if (nodeSet.has(row.file)) {
                        edges.push({ source: row.file, target: cId, type: 'contains' });
                    }
                }
            }

            // 4. CALLS edges between functions
            const callsQ = `
                MATCH (a:Function)-[:CALLS]->(b:Function)
                OPTIONAL MATCH (fa:File)-[:CONTAINS]->(a)
                OPTIONAL MATCH (fb:File)-[:CONTAINS]->(b)
                ${projectPath ? `WHERE fa.path STARTS WITH '${projectPath}'` : ''}
                RETURN fa.path as afile, a.name as aname, fb.path as bfile, b.name as bname
                LIMIT 3000
            `;
            const callsRes = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: callsQ });
            if (callsRes.success && callsRes.results) {
                for (const row of callsRes.results) {
                    const aId = `fn:${row.afile}:${row.aname}`;
                    const bId = `fn:${row.bfile}:${row.bname}`;
                    if (nodeSet.has(aId) && nodeSet.has(bId)) {
                        edges.push({ source: aId, target: bId, type: 'calls' });
                    }
                }
            }
        } catch (error) {
            this.outputChannel.appendLine(`Failed to get repo graph: ${error}`);
        }

        return { nodes, edges };
    }

    /**
     * Get inheritance tree for a class
     */
    async getInheritanceTree(className: string): Promise<GraphData> {
        try {
            const cypherQuery = `
                MATCH (p:Class)<-[:INHERITS_FROM*]-(c:Class {name: '${className}'})
                RETURN c.name as child, p.name as parent
                LIMIT 50
             `;
            const response = await this.mcpClient.callTool('execute_cypher_query', { cypher_query: cypherQuery });

            const nodes: GraphNode[] = [];
            const edges: GraphEdge[] = [];
            const nodeSet = new Set<string>();

            nodes.push({ id: className, label: className, type: 'class' });
            nodeSet.add(className);

            if (response.success && response.results) {
                for (const r of response.results) {
                    if (!nodeSet.has(r.parent)) {
                        nodes.push({ id: r.parent, label: r.parent, type: 'class' });
                        nodeSet.add(r.parent);
                    }
                    edges.push({ source: className, target: r.parent, type: 'inherits' });
                }
            }

            return { nodes, edges };
        } catch (error) {
            this.outputChannel.appendLine(`Failed to get inheritance tree: ${error}`);
            return { nodes: [], edges: [] };
        }
    }

    /**
     * Load a bundle
     */
    async loadBundle(bundleName: string): Promise<void> {
        await this.mcpClient.callTool('load_bundle', { bundle_name: bundleName });
    }

    dispose() {
        this.mcpClient.dispose();
        this.outputChannel.dispose();
    }
}

