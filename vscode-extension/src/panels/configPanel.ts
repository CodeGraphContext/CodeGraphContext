// src/panels/configPanel.ts
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export class ConfigPanel {
  private static currentPanel: ConfigPanel | undefined;
  private readonly panel: vscode.WebviewPanel;
  private readonly workspacePath: string;
  private disposables: vscode.Disposable[] = [];

  public static render(extensionUri: vscode.Uri) {
    if (ConfigPanel.currentPanel) {
      ConfigPanel.currentPanel.panel.reveal(vscode.ViewColumn.Two);
      return;
    }
    const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    const panel = vscode.window.createWebviewPanel(
      'cgcConfig',
      'CGC Configuration',
      vscode.ViewColumn.Two,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    ConfigPanel.currentPanel = new ConfigPanel(panel, extensionUri, workspacePath);
  }

  private constructor(
    panel: vscode.WebviewPanel,
    _extensionUri: vscode.Uri,
    workspacePath: string
  ) {
    this.panel = panel;
    this.workspacePath = workspacePath;
    this.panel.iconPath = new vscode.ThemeIcon('gear');

    // Load current settings
    const envVars = this.loadEnv();
    const vsConfig = vscode.workspace.getConfiguration('cgc');
    const currentCgcPath = vsConfig.get<string>('cgcPath') || 'cgc';
    const detectedCgcPath = this.detectCgcPath();

    this.panel.webview.html = this._getHtml(envVars, currentCgcPath, detectedCgcPath);

    this.panel.webview.onDidReceiveMessage(async (msg) => {
      switch (msg.command) {
        case 'saveAll': {
          // 1. Save .env
          const content = this.buildEnvContent(msg.env);
          const envFilePath = path.join(this.workspacePath, '.env');
          try {
            fs.writeFileSync(envFilePath, content, 'utf8');
          } catch (err) {
            vscode.window.showErrorMessage(`Failed to write .env: ${err}`);
            return;
          }
          // 2. Save cgcPath to VS Code settings
          if (msg.cgcPath) {
            await vscode.workspace.getConfiguration('cgc').update(
              'cgcPath', msg.cgcPath, vscode.ConfigurationTarget.Workspace
            );
          }
          vscode.window.showInformationMessage(
            '✅ Configuration saved! Reload the window to apply changes.',
            'Reload Now'
          ).then(choice => {
            if (choice === 'Reload Now') {
              vscode.commands.executeCommand('workbench.action.reloadWindow');
            }
          });
          break;
        }
        case 'openEnvFile': {
          const envFilePath = path.join(this.workspacePath, '.env');
          if (fs.existsSync(envFilePath)) {
            const doc = await vscode.workspace.openTextDocument(envFilePath);
            await vscode.window.showTextDocument(doc);
          } else {
            vscode.window.showWarningMessage('No .env file yet — save the form first.');
          }
          break;
        }
        case 'autoDetect': {
          const detected = this.detectCgcPath();
          this.panel.webview.postMessage({ command: 'detectedPath', path: detected });
          break;
        }
        case 'browseCgcPath': {
          const result = await vscode.window.showOpenDialog({
            canSelectFiles: true,
            canSelectFolders: false,
            canSelectMany: false,
            title: 'Select cgc executable',
            filters: process.platform === 'win32' ? { 'Executable': ['exe', 'cmd', 'bat'] } : {}
          });
          if (result && result[0]) {
            this.panel.webview.postMessage({ command: 'detectedPath', path: result[0].fsPath });
          }
          break;
        }
      }
    }, null, this.disposables);

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
  }

  /** Auto-detect where cgc is installed */
  private detectCgcPath(): string {
    const root = this.workspacePath;
    const isWin = process.platform === 'win32';
    const bin = isWin ? 'Scripts' : 'bin';
    const exe = isWin ? 'cgc.exe' : 'cgc';
    const venvNames = ['.venv', 'venv', 'env', '.virtualenv', 'virtualenv'];
    for (const name of venvNames) {
      const candidate = path.join(root, name, bin, exe);
      if (fs.existsSync(candidate)) { return candidate; }
    }
    // Try Python extension interpreter
    const pyConfig = vscode.workspace.getConfiguration('python');
    const pyPath = pyConfig.get<string>('pythonPath') || pyConfig.get<string>('defaultInterpreterPath');
    if (pyPath) {
      const candidate = path.join(path.dirname(pyPath), exe);
      if (fs.existsSync(candidate)) { return candidate; }
    }
    return 'cgc'; // fall back to PATH
  }

  public static parseEnvFile(content: string): Record<string, string> {
    const env: Record<string, string> = {};
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
      env[key] = val;
    }
    return env;
  }

  private loadEnv(): Record<string, string> {
    // Only read the actual workspace .env, NOT .env.example
    // (.env.example has Docker hostnames as defaults which break local setup)
    const p = path.join(this.workspacePath, '.env');
    if (fs.existsSync(p)) {
      return ConfigPanel.parseEnvFile(fs.readFileSync(p, 'utf8'));
    }
    return {};
  }

  private buildEnvContent(data: Record<string, string>): string {
    // Helper: only write a line if the value is non-empty
    const line = (key: string, val: string, comment?: string) => {
      if (val && val.trim()) {
        return `${key}=${val}`;
      }
      // Comment it out so it doesn't override global config
      return comment ? `# ${key}=  # ${comment}` : `# ${key}=`;
    };

    const db = data.DATABASE_TYPE || 'falkordb';
    return [
      '# CodeGraphContext Workspace Configuration',
      '# Generated by VS Code CGC Extension — ' + new Date().toISOString(),
      '# Values here OVERRIDE ~/.codegraphcontext/.env',
      '# Comment out lines to fall back to the global config.',
      '',
      '# Database Backend: falkordb | falkordb-remote | neo4j',
      `DEFAULT_DATABASE=${db}`,
      '',
      '# ── Neo4j ────────────────────────────────────────────────────',
      line('NEO4J_URI', data.NEO4J_URI || '', 'e.g. neo4j://localhost:7687'),
      line('NEO4J_USERNAME', data.NEO4J_USERNAME || '', 'e.g. neo4j'),
      line('NEO4J_PASSWORD', data.NEO4J_PASSWORD || '', 'your password'),
      '',
      '# ── FalkorDB Remote ──────────────────────────────────────────',
      line('FALKORDB_HOST', data.FALKORDB_HOST || '', 'e.g. localhost'),
      line('FALKORDB_PORT', data.FALKORDB_PORT || '', '6379'),
      line('FALKORDB_PASSWORD', data.FALKORDB_PASSWORD || '', ''),
      line('FALKORDB_USERNAME', data.FALKORDB_USERNAME || '', 'default'),
      line('FALKORDB_SSL', data.FALKORDB_SSL === 'true' ? 'true' : '', 'true|false'),
      line('FALKORDB_GRAPH_NAME', data.FALKORDB_GRAPH_NAME || '', 'codegraph'),
      '',
      '# ── App ──────────────────────────────────────────────────────',
      line('CGC_HOME', data.CGC_HOME || '', 'leave empty for ~/.codegraphcontext'),
      line('LOG_LEVEL', data.LOG_LEVEL || '', 'DEBUG|INFO|WARNING|ERROR'),
      'PYTHONUNBUFFERED=1',
    ].join('\n') + '\n';
  }

  private _getHtml(env: Record<string, string>, cgcPath: string, detectedPath: string): string {
    const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    const v = (key: string, fallback = '') => esc(env[key] ?? fallback);
    const sel = (key: string, opt: string) => (env[key] === opt) ? 'selected' : '';
    const chk = (key: string) => env[key] === 'true' ? 'checked' : '';
    const backend = env.DATABASE_TYPE || 'falkordb';
    const envExists = fs.existsSync(path.join(this.workspacePath, '.env'));

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>CGC Configuration</title>
<style>
:root{--bg:#080812;--surf:#0f0f1e;--border:#1a1a30;--acc:#6366f1;--acc2:#22d3ee;--text:#e2e8f0;--muted:#64748b;--ok:#4ade80;--warn:#fbbf24;--r:8px}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);padding:18px;font-size:13px;line-height:1.6}
h1{font-size:18px;font-weight:700;background:linear-gradient(135deg,var(--acc),var(--acc2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:2px}
.sub{color:var(--muted);font-size:11px;margin-bottom:18px}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;margin-left:6px;vertical-align:middle}
.ok{background:#4ade8022;color:var(--ok);border:1px solid #4ade8040}
.miss{background:#fbbf2422;color:var(--warn);border:1px solid #fbbf2440}
section{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);padding:16px;margin-bottom:12px}
h2{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:14px;display:flex;align-items:center;gap:6px}
h2::before{content:'';width:3px;height:13px;border-radius:2px;background:linear-gradient(var(--acc),var(--acc2))}
.field{margin-bottom:11px}
label{display:block;font-size:11px;font-weight:600;color:var(--muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em}
input[type=text],input[type=password],select{width:100%;padding:7px 10px;background:#08081a;border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:12px;font-family:'Cascadia Code','Fira Code',monospace;outline:none;transition:border-color .15s}
input[type=text]:focus,input[type=password]:focus,select:focus{border-color:var(--acc);box-shadow:0 0 0 3px #6366f118}
select option{background:#0f0f1e}
.hint{font-size:10px;color:var(--muted);margin-top:3px}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.row3{display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px}
.toggle{display:flex;align-items:center;gap:8px;margin-bottom:10px;cursor:pointer}
.toggle label{color:var(--text);font-size:12px;cursor:pointer;font-weight:normal;text-transform:none;letter-spacing:0;font-family:inherit}
input[type=checkbox]{width:14px;height:14px;accent-color:var(--acc);cursor:pointer}
.tabs{display:flex;gap:6px;margin-bottom:14px}
.tab{flex:1;padding:9px 6px;border:1px solid var(--border);border-radius:6px;cursor:pointer;text-align:center;font-size:11px;font-weight:600;background:transparent;color:var(--muted);transition:all .15s;line-height:1.4}
.tab.on{background:linear-gradient(135deg,#6366f122,#22d3ee11);border-color:var(--acc);color:var(--text)}
.tab span{display:block;font-weight:400;font-size:10px;color:var(--muted);margin-top:2px}
.panel{display:none}
.panel.on{display:block}
.path-row{display:flex;gap:6px}
.path-row input{flex:1}
.path-row button{padding:7px 10px;font-size:11px;white-space:nowrap}
.actions{display:flex;gap:8px;margin-top:4px}
button{padding:8px 14px;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;transition:all .15s;background:var(--surf);border:1px solid var(--border);color:var(--text)}
button:hover{border-color:var(--acc)}
.btn-save{background:linear-gradient(135deg,var(--acc),#818cf8);color:#fff;border:none;flex:1}
.btn-save:hover{opacity:.88;transform:translateY(-1px)}
.preview{background:#04040d;border:1px solid var(--border);border-radius:6px;padding:12px;font-family:'Cascadia Code','Fira Code',monospace;font-size:10px;line-height:1.8;color:#94a3b8;max-height:200px;overflow:auto;white-space:pre}
.c{color:#334155}.k{color:var(--acc2)}.val{color:var(--ok)}
.saved{font-size:11px;color:var(--ok);margin-left:8px;opacity:0;transition:opacity .3s}
.saved.show{opacity:1}
</style>
</head>
<body>
<h1>⚙️ CGC Configuration</h1>
<p class="sub">
  <code>${esc(this.workspacePath)}</code>
  <span class="badge ${envExists ? 'ok' : 'miss'}">${envExists ? '.env ✓' : 'no .env'}</span>
</p>

<!-- ── CGC Runtime ───────────────────────────────────────── -->
<section>
  <h2>CGC Runtime</h2>
  <div class="field">
    <label>CGC Executable Path</label>
    <div class="path-row">
      <input type="text" id="cgcPath" value="${esc(cgcPath)}" placeholder="cgc or full path to cgc binary"/>
      <button type="button" onclick="autoDetect()">🔍 Auto-detect</button>
      <button type="button" onclick="browse()">📂 Browse</button>
    </div>
    <div class="hint">
      Auto-detected: <code id="detectedPath">${esc(detectedPath)}</code>
      &nbsp;—&nbsp;Leave as <code>cgc</code> to use system PATH, or set full path to venv's cgc
      (e.g. <code>.venv/bin/cgc</code>)
    </div>
  </div>
</section>

<!-- ── Database Backend ─────────────────────────────────── -->
<section>
  <h2>Database Backend</h2>
  <div class="tabs">
    <div class="tab ${backend === 'falkordb' ? 'on' : ''}" onclick="setBackend('falkordb',this)">
      🟢 FalkorDB Lite<span>local, zero-config</span>
    </div>
    <div class="tab ${backend === 'falkordb-remote' ? 'on' : ''}" onclick="setBackend('falkordb-remote',this)">
      ☁️ FalkorDB Remote<span>cloud / Docker</span>
    </div>
    <div class="tab ${backend === 'neo4j' ? 'on' : ''}" onclick="setBackend('neo4j',this)">
      🔵 Neo4j<span>enterprise-grade</span>
    </div>
  </div>
  <input type="hidden" id="DATABASE_TYPE" value="${esc(backend)}"/>
  <div class="hint" id="backend-hint">${backend === 'falkordb'
        ? '✅ FalkorDB Lite runs locally with no configuration needed.'
        : backend === 'neo4j'
          ? 'Fill in the Neo4j section below.'
          : 'Fill in the FalkorDB Remote section below.'
      }</div>
</section>

<!-- ── Neo4j ────────────────────────────────────────────── -->
<section id="sec-neo4j" class="panel ${backend === 'neo4j' ? 'on' : ''}">
  <h2>Neo4j Connection</h2>
  <div class="field">
    <label>Bolt URI</label>
    <input type="text" id="NEO4J_URI" value="${v('NEO4J_URI', 'bolt://localhost:7687')}" placeholder="bolt://localhost:7687"/>
    <div class="hint">Docker: <code>bolt://neo4j:7687</code> &nbsp; Local: <code>bolt://localhost:7687</code></div>
  </div>
  <div class="row2">
    <div class="field">
      <label>Username</label>
      <input type="text" id="NEO4J_USERNAME" value="${v('NEO4J_USERNAME', 'neo4j')}" placeholder="neo4j"/>
    </div>
    <div class="field">
      <label>Password</label>
      <input type="password" id="NEO4J_PASSWORD" value="${v('NEO4J_PASSWORD', '')}"/>
    </div>
  </div>
</section>

<!-- ── FalkorDB Remote ───────────────────────────────────── -->
<section id="sec-falkordb-remote" class="panel ${backend === 'falkordb-remote' ? 'on' : ''}">
  <h2>FalkorDB Remote Connection</h2>
  <div class="row3">
    <div class="field">
      <label>Host</label>
      <input type="text" id="FALKORDB_HOST" value="${v('FALKORDB_HOST', '')}" placeholder="localhost"/>
    </div>
    <div class="field">
      <label>Port</label>
      <input type="text" id="FALKORDB_PORT" value="${v('FALKORDB_PORT', '6379')}" placeholder="6379"/>
    </div>
    <div class="field">
      <label>Graph Name</label>
      <input type="text" id="FALKORDB_GRAPH_NAME" value="${v('FALKORDB_GRAPH_NAME', 'codegraph')}" placeholder="codegraph"/>
    </div>
  </div>
  <div class="row2">
    <div class="field">
      <label>Username</label>
      <input type="text" id="FALKORDB_USERNAME" value="${v('FALKORDB_USERNAME', 'default')}" placeholder="default"/>
    </div>
    <div class="field">
      <label>Password</label>
      <input type="password" id="FALKORDB_PASSWORD" value="${v('FALKORDB_PASSWORD', '')}"/>
    </div>
  </div>
  <div class="toggle">
    <input type="checkbox" id="FALKORDB_SSL" ${chk('FALKORDB_SSL')}/>
    <label for="FALKORDB_SSL">Use TLS / SSL</label>
  </div>
</section>

<!-- ── App Settings ─────────────────────────────────────── -->
<section>
  <h2>App Settings</h2>
  <div class="row2">
    <div class="field">
      <label>Log Level</label>
      <select id="LOG_LEVEL">
        <option value="DEBUG"   ${sel('LOG_LEVEL', 'DEBUG')}>DEBUG — verbose</option>
        <option value="INFO"    ${!env.LOG_LEVEL || env.LOG_LEVEL === 'INFO' ? 'selected' : ''}>INFO (default)</option>
        <option value="WARNING" ${sel('LOG_LEVEL', 'WARNING')}>WARNING</option>
        <option value="ERROR"   ${sel('LOG_LEVEL', 'ERROR')}>ERROR — quiet</option>
      </select>
    </div>
    <div class="field">
      <label>CGC Home Directory</label>
      <input type="text" id="CGC_HOME" value="${v('CGC_HOME', '')}" placeholder="default: ~/.codegraphcontext"/>
    </div>
  </div>
</section>

<!-- ── .env Preview ──────────────────────────────────────── -->
<section>
  <h2>.env Preview</h2>
  <div class="preview" id="preview"></div>
  <div class="actions" style="margin-top:12px">
    <button class="btn-save" onclick="saveAll()">💾 Save Configuration</button>
    <button onclick="openFile()">📂 Open .env</button>
    <span class="saved" id="saved-msg">✔ Saved</span>
  </div>
</section>

<script>
const vscode = acquireVsCodeApi();

function getId(id){ return document.getElementById(id); }
function val(id){ const el=getId(id); if(!el)return''; return el.type==='checkbox'?String(el.checked):el.value; }

function setBackend(type, el) {
    getId('DATABASE_TYPE').value = type;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
    el.classList.add('on');
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('on'));
    const sec = getId('sec-' + type);
    if (sec) sec.classList.add('on');
    const hints = {
        'falkordb': '✅ FalkorDB Lite runs locally with no configuration needed.',
        'falkordb-remote': 'Fill in the FalkorDB Remote section below.',
        'neo4j': 'Fill in the Neo4j section below.'
    };
    getId('backend-hint').textContent = hints[type] || '';
    renderPreview();
}

function autoDetect() {
    vscode.postMessage({ command: 'autoDetect' });
}
function browse() {
    vscode.postMessage({ command: 'browseCgcPath' });
}
function openFile() {
    vscode.postMessage({ command: 'openEnvFile' });
}

function getEnv() {
    return {
        DATABASE_TYPE:      val('DATABASE_TYPE'),
        NEO4J_URI:          val('NEO4J_URI'),
        NEO4J_USERNAME:     val('NEO4J_USERNAME'),
        NEO4J_PASSWORD:     val('NEO4J_PASSWORD'),
        FALKORDB_HOST:      val('FALKORDB_HOST'),
        FALKORDB_PORT:      val('FALKORDB_PORT'),
        FALKORDB_PASSWORD:  val('FALKORDB_PASSWORD'),
        FALKORDB_USERNAME:  val('FALKORDB_USERNAME'),
        FALKORDB_SSL:       val('FALKORDB_SSL'),
        FALKORDB_GRAPH_NAME:val('FALKORDB_GRAPH_NAME'),
        CGC_HOME:           val('CGC_HOME'),
        LOG_LEVEL:          val('LOG_LEVEL'),
    };
}

function renderPreview() {
    const e = getEnv();
    const lines = [
        ['# CodeGraphContext .env', null],
        ['', null],
        ['DATABASE_TYPE', e.DATABASE_TYPE],
        ['NEO4J_URI', e.NEO4J_URI],
        ['NEO4J_USERNAME', e.NEO4J_USERNAME],
        ['NEO4J_PASSWORD', e.NEO4J_PASSWORD ? '••••••••' : ''],
        ['FALKORDB_HOST', e.FALKORDB_HOST],
        ['FALKORDB_PORT', e.FALKORDB_PORT],
        ['FALKORDB_USERNAME', e.FALKORDB_USERNAME],
        ['FALKORDB_PASSWORD', e.FALKORDB_PASSWORD ? '••••••••' : ''],
        ['FALKORDB_SSL', e.FALKORDB_SSL],
        ['FALKORDB_GRAPH_NAME', e.FALKORDB_GRAPH_NAME],
        ['CGC_HOME', e.CGC_HOME],
        ['LOG_LEVEL', e.LOG_LEVEL],
        ['PYTHONUNBUFFERED', '1'],
    ];
    const html = lines.map(([k, v]) => {
        if (k.startsWith('#')) return '<span class="c">' + k + '</span>';
        if (!k) return '';
        if (v === null || v === undefined) return '';
        return '<span class="k">' + k + '</span>=<span class="val">' + (v||'') + '</span>';
    }).filter(l => l !== '').join('\n');
    getId('preview').innerHTML = html;
}

function saveAll() {
    vscode.postMessage({
        command: 'saveAll',
        env: getEnv(),
        cgcPath: val('cgcPath')
    });
    const el = getId('saved-msg');
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2500);
}

// Update preview when any input changes
document.addEventListener('input', renderPreview);
document.addEventListener('change', renderPreview);

// Messages from extension
window.addEventListener('message', ev => {
    if (ev.data.command === 'detectedPath') {
        const p = ev.data.path;
        getId('cgcPath').value = p;
        getId('detectedPath').textContent = p;
    }
});

renderPreview();
</script>
</body>
</html>`;
  }

  dispose() {
    ConfigPanel.currentPanel = undefined;
    this.panel.dispose();
    while (this.disposables.length) { this.disposables.pop()?.dispose(); }
  }
}
