import * as vscode from "vscode";
import { spawn } from "child_process";
import { CgcService } from "../mcp/service";
import { CgcMcpClient } from "../mcp/client";

export class SidebarControlPanel implements vscode.WebviewViewProvider {
  public static readonly viewType = "cgc-control";
  private view?: vscode.WebviewView;

  constructor(
    private readonly service: CgcService,
    private readonly client: CgcMcpClient,
    private readonly context: vscode.ExtensionContext
  ) {}

  resolveWebviewView(view: vscode.WebviewView): void {
    this.view = view;
    view.webview.options = { enableScripts: true };
    this.render();

    view.webview.onDidReceiveMessage(async (msg: Record<string, unknown>) => {
      await this.handleMessage(msg);
    });
  }

  public async refresh(): Promise<void> {
    if (!this.view) return;
    await this.render();
  }

  private async render(): Promise<void> {
    if (!this.view) return;

    const repos = await this.service.listRepositories().catch(() => []);
    const watches = await this.service.listWatches().catch(() => []);
    const hotspots = await this.service.getComplexityHotspots(10).catch(() => []);
    const cfg = vscode.workspace.getConfiguration("cgc");

    const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? "";
    const selectedRepo = cfg.get<string>("repoPath", "") || (repos[0]?.path ?? "");
    const contextMode = cfg.get<string>("contextMode", "global");

    this.view.webview.html = this.buildHtml({
      repos,
      watches,
      hotspots,
      selectedRepo,
      contextMode,
      workspacePath,
      cfg
    });
  }

  private async handleMessage(msg: Record<string, unknown>): Promise<void> {
    const type = msg.type as string;

    switch (type) {
      case "change-repo": {
        const path = msg.value as string;
        await vscode.workspace.getConfiguration("cgc").update("repoPath", path, vscode.ConfigurationTarget.Workspace);
        await this.render();
        break;
      }
      case "change-context": {
        const mode = msg.value as string;
        await vscode.workspace.getConfiguration("cgc").update("contextMode", mode, vscode.ConfigurationTarget.Global);
        await this.render();
        break;
      }
      case "visualize-repo": {
        await this.launchVizServer();
        break;
      }
      case "get-active-file": {
        const editor = vscode.window.activeTextEditor;
        const filePath = editor?.document.uri.fsPath ?? "";
        this.view?.webview.postMessage({ type: "active-file", value: filePath });
        break;
      }
      case "toggle-watch": {
        const path = msg.path as string;
        if (path) {
          await this.service.watchWorkspace(path);
          await this.render();
        }
        break;
      }
      case "refresh-extension": {
        this.client.dispose();
        await this.client.ensureStarted();
        await this.render();
        vscode.window.showInformationMessage("CGC extension restarted.");
        break;
      }
      case "save-config": {
        await this.saveConfig(msg);
        await this.render();
        break;
      }
      case "run-smart-query": {
        await this.runSmartQuery(msg);
        break;
      }
      case "get-editor-selection": {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
          const sel = editor.selection;
          const word = editor.document.getText(sel).trim() ||
            editor.document.getText(editor.document.getWordRangeAtPosition(sel.active, /[A-Za-z_][A-Za-z0-9_.]*/)) || "";
          this.view?.webview.postMessage({ type: "editor-selection", value: word, field: msg.field });
        }
        break;
      }
      case "index-workspace": {
        const wp = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (wp) {
          await vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title: "Indexing workspace…" },
            async () => { await this.service.indexWorkspace(wp); }
          );
          await this.render();
        }
        break;
      }
    }
  }

  private async saveConfig(msg: Record<string, unknown>): Promise<void> {
    const cfg = vscode.workspace.getConfiguration("cgc");
    const keys: Array<[string, string]> = [
      ["executable", "executable"],
      ["databaseMode", "databaseMode"],
      ["pythonPackagePath", "pythonPackagePath"],
      ["neo4jUri", "neo4jUri"],
      ["maxToolResponseTokens", "maxToolResponseTokens"],
      ["complexityWarningThreshold", "complexityWarningThreshold"],
      ["maxDeadCodeDiagnostics", "maxDeadCodeDiagnostics"],
    ];
    for (const [msgKey, cfgKey] of keys) {
      if (msg[msgKey] !== undefined) {
        const val = msgKey.includes("max") || msgKey.includes("Threshold") || msgKey.includes("Diagnostics")
          ? Number(msg[msgKey])
          : msg[msgKey] as string;
        await cfg.update(cfgKey, val, vscode.ConfigurationTarget.Global);
      }
    }
    this.client.dispose();
    await this.client.ensureStarted();
    vscode.window.showInformationMessage("CGC config saved and restarted.");
  }

  private async launchVizServer(): Promise<void> {
    const cfg = vscode.workspace.getConfiguration("cgc");
    const executable = cfg.get<string>("executable", "cgc").trim() || "cgc";
    const repoPath = cfg.get<string>("repoPath", "").trim()
      || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath
      || "";

    const port = 8000;
    const args = ["visualize", "--port", String(port)];
    if (repoPath) args.push("--repo", repoPath);

    const terminal = vscode.window.createTerminal({ name: "CGC Visualize" });
    terminal.show(false);
    terminal.sendText(`${executable} ${args.join(" ")}`);

    // Open the explore URL WITHOUT repo_path in the query string.
    // The CGC viz server's /api/graph endpoint filters by repo_path stored in its
    // own session context (set via --repo flag to the server process). Adding
    // repo_path as a query param on the frontend overrides that and can return 0
    // nodes when the stored path doesn't match exactly.
    await new Promise(r => setTimeout(r, 2500));
    const url = `http://localhost:${port}/explore?backend=${encodeURIComponent(`http://localhost:${port}`)}` ;
    await vscode.env.openExternal(vscode.Uri.parse(url));
  }


  private async runSmartQuery(msg: Record<string, unknown>): Promise<void> {
    const queryType = msg.queryType as string;
    let results: unknown[] = [];
    let error = "";

    try {
      switch (queryType) {
        case "list-functions": {
          const repoPath = vscode.workspace.getConfiguration("cgc").get<string>("repoPath", "") || undefined;
          results = await this.service.listFunctions(repoPath);
          break;
        }
        case "list-classes": {
          const repoPath = vscode.workspace.getConfiguration("cgc").get<string>("repoPath", "") || undefined;
          results = await this.service.listClasses(repoPath);
          break;
        }
        case "list-imports": {
          results = await this.service.listImports(msg.file as string);
          break;
        }
        case "list-callers": {
          results = await this.service.findCallers(msg.target as string, (msg.file as string) || undefined);
          break;
        }
        case "list-callees": {
          const depth = Number(msg.depth ?? 1);
          results = await this.service.listCallees(msg.target as string, (msg.file as string) || undefined, depth);
          break;
        }
        case "call-chain": {
          results = await this.service.findCallChain(
            msg.from as string,
            msg.to as string,
            (msg.fromFile as string) || undefined,
            (msg.toFile as string) || undefined
          );
          break;
        }
      }
    } catch (err) {
      error = String(err);
    }

    this.view?.webview.postMessage({ type: "query-result", results, error, queryType });
  }

  private buildHtml(data: {
    repos: Array<{ repo_name?: string; path?: string }>;
    watches: string[];
    hotspots: Array<{ function_name?: string; cyclomatic_complexity?: number; path?: string }>;
    selectedRepo: string;
    contextMode: string;
    workspacePath: string;
    cfg: vscode.WorkspaceConfiguration;
  }): string {
    const { repos, watches, hotspots, selectedRepo, contextMode, workspacePath, cfg } = data;

    const repoOptions = [
      `<option value="">Auto (workspace)</option>`,
      ...repos.map(r => {
        const p = r.path ?? "";
        const sel = p === selectedRepo ? "selected" : "";
        return `<option value="${esc(p)}" ${sel}>${esc((r.repo_name ?? p) || "Repository")}</option>`;
      })
    ].join("");

    const watchItems = watches.map(w =>
      `<label class="watch-item"><input type="checkbox" checked value="${esc(w)}"> <span title="${esc(w)}">${esc(w.split("/").slice(-2).join("/"))}</span></label>`
    ).join("") || `<div class="empty-state">No active watches</div>`;

    const hotspotRows = hotspots.slice(0, 10).map(h => {
      // Python returns 'complexity' (aliased from cyclomatic_complexity column)
      const score = (h as { complexity?: number; cyclomatic_complexity?: number }).complexity ?? h.cyclomatic_complexity ?? 0;
      const bar = Math.min(100, score * 5);
      const color = score > 15 ? "#f85149" : score > 8 ? "#e3b341" : "#3fb950";
      return `<div class="hotspot-row" title="${esc(h.path ?? "")}">
        <span class="fn-name">${esc(h.function_name ?? "fn")}</span>
        <div class="bar-wrap"><div class="bar-fill" style="width:${bar}%;background:${color}"></div></div>
        <span class="score" style="color:${color}">${score}</span>
      </div>`;
    }).join("") || `<div class="empty-state">Run an index first</div>`;

    const executable = esc(cfg.get<string>("executable", "cgc"));
    const dbMode = cfg.get<string>("databaseMode", "falkordb");
    const pythonPkg = esc(cfg.get<string>("pythonPackagePath", ""));
    const neo4jUri = esc(cfg.get<string>("neo4jUri", ""));
    const maxTokens = cfg.get<number>("maxToolResponseTokens", 0);
    const complexityThreshold = cfg.get<number>("complexityWarningThreshold", 10);
    const maxDead = cfg.get<number>("maxDeadCodeDiagnostics", 100);

    const dbOptions = ["falkordb", "ladybugdb", "neo4j"].map(d =>
      `<option value="${d}" ${d === dbMode ? "selected" : ""}>${d}</option>`
    ).join("");

    const contextOptions = ["global", "per-repo", "named"].map(m =>
      `<option value="${m}" ${m === contextMode ? "selected" : ""}>${m}</option>`
    ).join("");

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--vscode-font-family);font-size:var(--vscode-font-size);color:var(--vscode-foreground);background:var(--vscode-sideBar-background);padding:0;overflow-x:hidden}

/* --- Accordion --- */
.section{border-bottom:1px solid var(--vscode-widget-border)}
.section-header{display:flex;align-items:center;gap:6px;padding:8px 12px;cursor:pointer;user-select:none;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--vscode-sideBarSectionHeader-foreground);background:var(--vscode-sideBarSectionHeader-background);transition:background .15s}
.section-header:hover{background:var(--vscode-list-hoverBackground)}
.section-header .arrow{font-size:9px;transition:transform .2s;display:inline-block}
.section-body{padding:10px 12px;display:none}
.section.open .section-body{display:block}
.section.open .arrow{transform:rotate(90deg)}
.section-icon{font-size:13px;width:16px;text-align:center}

/* --- Form controls --- */
select,input[type=text],input[type=number]{width:100%;padding:5px 8px;background:var(--vscode-input-background);color:var(--vscode-input-foreground);border:1px solid var(--vscode-input-border);border-radius:4px;font-size:12px;font-family:inherit}
select:focus,input:focus{outline:1px solid var(--vscode-focusBorder);border-color:var(--vscode-focusBorder)}
label.field-label{display:block;font-size:11px;opacity:.75;margin-bottom:3px;margin-top:8px}
label.field-label:first-child{margin-top:0}

/* --- Buttons --- */
.btn{display:inline-flex;align-items:center;gap:5px;padding:5px 10px;cursor:pointer;border:none;border-radius:4px;font-size:12px;font-family:inherit;font-weight:500;transition:opacity .15s,transform .1s}
.btn:hover{opacity:.85}
.btn:active{transform:scale(.97)}
.btn-primary{background:var(--vscode-button-background);color:var(--vscode-button-foreground);width:100%;justify-content:center;margin-top:8px}
.btn-secondary{background:var(--vscode-button-secondaryBackground);color:var(--vscode-button-secondaryForeground);width:100%;justify-content:center;margin-top:6px}
.btn-icon{background:transparent;color:var(--vscode-foreground);padding:3px 6px;border:1px solid var(--vscode-widget-border);border-radius:3px;font-size:11px}
.btn-danger{background:var(--vscode-inputValidation-errorBackground,#5a1d1d);color:#f85149;width:100%;justify-content:center;margin-top:6px}

/* --- Hotspots --- */
.hotspot-row{display:grid;grid-template-columns:1fr 80px 28px;align-items:center;gap:6px;padding:3px 0}
.fn-name{font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;opacity:.9}
.bar-wrap{height:5px;background:var(--vscode-scrollbarSlider-background,#ffffff1a);border-radius:99px;overflow:hidden}
.bar-fill{height:100%;border-radius:99px;transition:width .4s}
.score{font-size:11px;text-align:right;font-weight:600;font-variant-numeric:tabular-nums}

/* --- Smart Query --- */
.query-card{border:1px solid var(--vscode-widget-border);border-radius:6px;padding:8px;margin-bottom:8px;cursor:pointer;transition:background .15s;background:var(--vscode-editor-background)}
.query-card:hover{background:var(--vscode-list-hoverBackground)}
.query-card.active{border-color:var(--vscode-focusBorder);background:var(--vscode-list-activeSelectionBackground);color:var(--vscode-list-activeSelectionForeground)}
.query-title{font-size:12px;font-weight:600}
.query-desc{font-size:11px;opacity:.65;margin-top:2px}
.query-form{margin-top:8px;display:none}
.query-form.show{display:block}
.input-row{display:flex;gap:4px;margin-top:6px}
.input-row input{flex:1}
.result-box{margin-top:8px;max-height:200px;overflow:auto;font-size:11px;font-family:var(--vscode-editor-font-family,monospace);background:var(--vscode-editor-background);border:1px solid var(--vscode-widget-border);border-radius:4px;padding:6px;white-space:pre-wrap;word-break:break-all}
.result-empty{opacity:.5;font-style:italic}
.result-error{color:#f85149}

/* --- Watch items --- */
.watch-item{display:flex;align-items:center;gap:6px;font-size:12px;padding:3px 0;overflow:hidden}
.watch-item span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;opacity:.8}

/* --- Status badge --- */
.badge{display:inline-block;padding:2px 6px;border-radius:99px;font-size:10px;font-weight:600}
.badge-green{background:#3fb95022;color:#3fb950}
.badge-yellow{background:#e3b34122;color:#e3b341}

.empty-state{font-size:11px;opacity:.45;font-style:italic;padding:4px 0}
.divider{height:1px;background:var(--vscode-widget-border);margin:8px 0}
.row{display:flex;gap:6px;align-items:center}
.row>*{flex:1}
.mt4{margin-top:4px}
</style>
</head>
<body>

<!-- ═══ 1. ACTIVE CONTEXT ═══ -->
<div class="section open" id="sec-context">
  <div class="section-header" onclick="toggle('sec-context')">
    <span class="section-icon">🌐</span> Context
    <span class="arrow" style="margin-left:auto">▶</span>
  </div>
  <div class="section-body">
    <label class="field-label">Context Mode</label>
    <select id="contextMode" onchange="changeContext(this.value)">
      ${contextOptions}
    </select>
    <label class="field-label" style="margin-top:8px">Active Repository</label>
    <select id="repoSelect" onchange="changeRepo(this.value)">
      ${repoOptions}
    </select>
  </div>
</div>

<!-- ═══ 2. ACTIONS ═══ -->
<div class="section open" id="sec-actions">
  <div class="section-header" onclick="toggle('sec-actions')">
    <span class="section-icon">⚡</span> Actions
    <span class="arrow" style="margin-left:auto">▶</span>
  </div>
  <div class="section-body">
    <button class="btn btn-primary" onclick="visualize()">🗺 Visualize Entire Repo</button>
    <button class="btn btn-secondary" onclick="refreshExtension()">🔄 Refresh Extension</button>
    <button class="btn btn-secondary" onclick="indexWorkspace()">📦 Re-Index Workspace</button>
  </div>
</div>

<!-- ═══ 3. LIVE WATCH ═══ -->
<div class="section" id="sec-watch">
  <div class="section-header" onclick="toggle('sec-watch')">
    <span class="section-icon">👁</span> Live Watch
    <span class="arrow" style="margin-left:auto">▶</span>
  </div>
  <div class="section-body">
    <div id="watchList">${watchItems}</div>
    <div class="divider"></div>
    <label class="field-label">Watch new path</label>
    <div class="row mt4">
      <input type="text" id="newWatchPath" placeholder="${esc(workspacePath)}" value="${esc(workspacePath)}">
      <button class="btn btn-icon" onclick="addWatch()">+ Add</button>
    </div>
  </div>
</div>

<!-- ═══ 4. COMPLEXITY HOTSPOTS ═══ -->
<div class="section" id="sec-hotspots">
  <div class="section-header" onclick="toggle('sec-hotspots')">
    <span class="section-icon">🔥</span> Most Complex Functions
    <span class="arrow" style="margin-left:auto">▶</span>
  </div>
  <div class="section-body">
    <div id="hotspots">${hotspotRows}</div>
  </div>
</div>

<!-- ═══ 5. SMART QUERIES ═══ -->
<div class="section open" id="sec-query">
  <div class="section-header" onclick="toggle('sec-query')">
    <span class="section-icon">🔍</span> Smart Query
    <span class="arrow" style="margin-left:auto">▶</span>
  </div>
  <div class="section-body">

    <!-- List Functions -->
    <div class="query-card" id="qc-list-functions" onclick="selectQuery('list-functions')">
      <div class="query-title">List all functions</div>
      <div class="query-desc">Show every function in the active repo</div>
    </div>

    <!-- List Classes -->
    <div class="query-card" id="qc-list-classes" onclick="selectQuery('list-classes')">
      <div class="query-title">List all classes</div>
      <div class="query-desc">Show every class in the active repo</div>
    </div>

    <!-- Imports of file -->
    <div class="query-card" id="qc-list-imports" onclick="selectQuery('list-imports')">
      <div class="query-title">List all imports of file <span class="badge badge-yellow">file</span></div>
      <div class="query-desc">What does this file import?</div>
      <div class="query-form" id="qf-list-imports">
        <label class="field-label">File path (absolute) — defaults to active file</label>
        <div class="input-row">
          <input type="text" id="qi-import-file" placeholder="auto-fills active file">
          <button class="btn btn-icon" title="Use active editor file" onclick="useActiveFile(event,'qi-import-file')">📄</button>
          <button class="btn btn-icon" title="Use editor selection" onclick="fillFromEditor(event,'qi-import-file')">📍</button>
        </div>
      </div>
    </div>

    <!-- Callers of -->
    <div class="query-card" id="qc-list-callers" onclick="selectQuery('list-callers')">
      <div class="query-title">List all callers of <span class="badge badge-yellow">fn</span></div>
      <div class="query-desc">Who calls this function?</div>
      <div class="query-form" id="qf-list-callers">
        <label class="field-label">Function name</label>
        <div class="input-row">
          <input type="text" id="qi-caller-target" placeholder="e.g. processData">
          <button class="btn btn-icon" onclick="fillFromEditor(event,'qi-caller-target')">📍</button>
        </div>
        <label class="field-label">File path (optional — narrows scope)</label>
        <div class="input-row">
          <input type="text" id="qi-caller-file" placeholder="e.g. /path/to/file.py">
          <button class="btn btn-icon" onclick="useActiveFile(event,'qi-caller-file')">📄</button>
        </div>
      </div>
    </div>

    <!-- Callees of -->
    <div class="query-card" id="qc-list-callees" onclick="selectQuery('list-callees')">
      <div class="query-title">List all callees of <span class="badge badge-yellow">fn</span></div>
      <div class="query-desc">What does this function call?</div>
      <div class="query-form" id="qf-list-callees">
        <label class="field-label">Function name</label>
        <div class="input-row">
          <input type="text" id="qi-callee-target" placeholder="e.g. buildGraph">
          <button class="btn btn-icon" onclick="fillFromEditor(event,'qi-callee-target')">📍</button>
        </div>
        <label class="field-label">File path (optional)</label>
        <div class="input-row">
          <input type="text" id="qi-callee-file" placeholder="e.g. /path/to/file.py">
          <button class="btn btn-icon" onclick="useActiveFile(event,'qi-callee-file')">📄</button>
        </div>
        <label class="field-label">Depth (1 = direct calls, 2+ = transitive)</label>
        <input type="number" id="qi-callee-depth" value="1" min="1" max="10" style="margin-top:4px">
      </div>
    </div>

    <!-- Call chain -->
    <div class="query-card" id="qc-call-chain" onclick="selectQuery('call-chain')">
      <div class="query-title">Find call chain <span class="badge badge-yellow">A</span> → <span class="badge badge-yellow">B</span></div>
      <div class="query-desc">Trace execution path between two functions</div>
      <div class="query-form" id="qf-call-chain">
        <label class="field-label">From function</label>
        <div class="input-row">
          <input type="text" id="qi-chain-from" placeholder="e.g. main">
          <button class="btn btn-icon" onclick="fillFromEditor(event,'qi-chain-from')">📍</button>
        </div>
        <label class="field-label">From file path (optional)</label>
        <div class="input-row">
          <input type="text" id="qi-chain-from-file" placeholder="e.g. /path/to/entry.py">
          <button class="btn btn-icon" onclick="useActiveFile(event,'qi-chain-from-file')">📄</button>
        </div>
        <label class="field-label">To function</label>
        <div class="input-row">
          <input type="text" id="qi-chain-to" placeholder="e.g. saveData">
          <button class="btn btn-icon" onclick="fillFromEditor(event,'qi-chain-to')">📍</button>
        </div>
        <label class="field-label">To file path (optional)</label>
        <div class="input-row">
          <input type="text" id="qi-chain-to-file" placeholder="e.g. /path/to/storage.py">
          <button class="btn btn-icon" onclick="useActiveFile(event,'qi-chain-to-file')">📄</button>
        </div>
      </div>
    </div>

    <button class="btn btn-primary" id="runQueryBtn" onclick="runQuery()" style="display:none">▶ Run Query</button>
    <div id="queryResult" class="result-box" style="display:none"></div>
  </div>
</div>

<!-- ═══ 6. CONFIG ═══ -->
<div class="section" id="sec-config">
  <div class="section-header" onclick="toggle('sec-config')">
    <span class="section-icon">⚙️</span> Configuration
    <span class="arrow" style="margin-left:auto">▶</span>
  </div>
  <div class="section-body">
    <label class="field-label">CGC Executable</label>
    <input type="text" id="cfg-executable" value="${executable}" placeholder="cgc or /path/to/cgc">

    <label class="field-label">Database Mode</label>
    <select id="cfg-dbMode">${dbOptions}</select>

    <label class="field-label">Python Package Path / uvx</label>
    <input type="text" id="cfg-pythonPkg" value="${pythonPkg}" placeholder="Leave blank to use PATH">

    <label class="field-label">Neo4j URI</label>
    <input type="text" id="cfg-neo4jUri" value="${neo4jUri}" placeholder="bolt://localhost:7687">

    <label class="field-label">Max Tool Response Tokens (0 = unlimited)</label>
    <input type="number" id="cfg-maxTokens" value="${maxTokens}" min="0">

    <label class="field-label">Complexity Warning Threshold</label>
    <input type="number" id="cfg-complexityThreshold" value="${complexityThreshold}" min="1">

    <label class="field-label">Max Dead Code Diagnostics</label>
    <input type="number" id="cfg-maxDead" value="${maxDead}" min="0">

    <button class="btn btn-primary" onclick="saveConfig()">💾 Save &amp; Restart</button>
  </div>
</div>

<script>
const vscode = acquireVsCodeApi();
let activeQuery = null;

function toggle(id) {
  const sec = document.getElementById(id);
  sec.classList.toggle('open');
}

function changeContext(val) { vscode.postMessage({ type: 'change-context', value: val }); }
function changeRepo(val)    { vscode.postMessage({ type: 'change-repo', value: val }); }
function visualize()        { vscode.postMessage({ type: 'visualize-repo' }); }
function refreshExtension() { vscode.postMessage({ type: 'refresh-extension' }); }
function indexWorkspace()   { vscode.postMessage({ type: 'index-workspace' }); }
function addWatch() {
  const path = document.getElementById('newWatchPath').value.trim();
  if (path) vscode.postMessage({ type: 'toggle-watch', path });
}

function selectQuery(type) {
  document.querySelectorAll('.query-card').forEach(c => c.classList.remove('active'));
  document.querySelectorAll('.query-form').forEach(f => f.classList.remove('show'));
  activeQuery = type;
  const card = document.getElementById('qc-' + type);
  const form = document.getElementById('qf-' + type);
  if (card) card.classList.add('active');
  if (form) form.classList.add('show');
  document.getElementById('runQueryBtn').style.display = 'flex';
  document.getElementById('queryResult').style.display = 'none';
  // Auto-fill active file for imports
  if (type === 'list-imports') vscode.postMessage({ type: 'get-active-file' });
}

function fillFromEditor(e, fieldId) {
  e.stopPropagation();
  vscode.postMessage({ type: 'get-editor-selection', field: fieldId });
}
function useActiveFile(e, fieldId) {
  e.stopPropagation();
  vscode.postMessage({ type: 'get-active-file', field: fieldId });
}

function v(id) { return (document.getElementById(id)?.value ?? '').trim(); }

function runQuery() {
  if (!activeQuery) return;
  const btn = document.getElementById('runQueryBtn');
  btn.textContent = '⏳ Running…'; btn.disabled = true;
  const box = document.getElementById('queryResult');
  box.style.display = 'block'; box.textContent = 'Loading…'; box.className = 'result-box';

  const msg = { type: 'run-smart-query', queryType: activeQuery };

  if (activeQuery === 'list-imports') {
    msg.file = v('qi-import-file');
  } else if (activeQuery === 'list-callers') {
    msg.target = v('qi-caller-target');
    msg.file   = v('qi-caller-file');
  } else if (activeQuery === 'list-callees') {
    msg.target = v('qi-callee-target');
    msg.file   = v('qi-callee-file');
    msg.depth  = Number(v('qi-callee-depth') || 1);
  } else if (activeQuery === 'call-chain') {
    msg.from     = v('qi-chain-from');
    msg.to       = v('qi-chain-to');
    msg.fromFile = v('qi-chain-from-file');
    msg.toFile   = v('qi-chain-to-file');
  }
  vscode.postMessage(msg);
}

function saveConfig() {
  vscode.postMessage({
    type: 'save-config',
    executable: v('cfg-executable'),
    databaseMode: document.getElementById('cfg-dbMode').value,
    pythonPackagePath: v('cfg-pythonPkg'),
    neo4jUri: v('cfg-neo4jUri'),
    maxToolResponseTokens: Number(v('cfg-maxTokens') || 0),
    complexityWarningThreshold: Number(v('cfg-complexityThreshold') || 10),
    maxDeadCodeDiagnostics: Number(v('cfg-maxDead') || 100),
  });
}

window.addEventListener('message', e => {
  const m = e.data;
  if (m.type === 'query-result') {
    const btn = document.getElementById('runQueryBtn');
    btn.textContent = '▶ Run Query'; btn.disabled = false;
    const box = document.getElementById('queryResult');
    if (m.error) {
      box.className = 'result-box result-error';
      box.textContent = 'Error: ' + m.error;
    } else if (!m.results || m.results.length === 0) {
      box.className = 'result-box result-empty';
      box.textContent = 'No results found.';
    } else {
      box.className = 'result-box';
      box.textContent = JSON.stringify(m.results, null, 2);
    }
  }
  if (m.type === 'editor-selection' && m.field) {
    const el = document.getElementById(m.field);
    if (el) { el.value = m.value; el.focus(); }
  }
  if (m.type === 'active-file') {
    // If a specific field is targeted, fill it; otherwise default for imports
    const targetField = m.field || (activeQuery === 'list-imports' ? 'qi-import-file' : null);
    if (targetField) {
      const el = document.getElementById(targetField);
      if (el && m.value) { el.value = m.value; }
    }
  }
});
</script>
</body>
</html>`;
  }
}

function esc(v: string): string {
  return v.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
