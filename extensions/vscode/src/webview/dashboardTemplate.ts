import { ComplexityEntry, IndexedRepository } from "../types/cgc";

type DashboardPayload = {
  repos: IndexedRepository[];
  hotspots: ComplexityEntry[];
  selectedRepo: string;
};

export function renderDashboardHtml(payload: DashboardPayload): string {
  const repoOptions = payload.repos
    .map((repo) => {
      const path = repo.path ?? "";
      const selected = path === payload.selectedRepo ? "selected" : "";
      return `<option value="${escapeHtml(path)}" ${selected}>${escapeHtml((repo.repo_name ?? path) || "Repository")}</option>`;
    })
    .join("");

  const hotspots = payload.hotspots
    .map((h) => {
      const score = (h as { complexity?: number }).complexity ?? h.cyclomatic_complexity ?? 0;
      const width = Math.min(100, score * 4);
      return `<div class="risk-row"><span>${escapeHtml(h.function_name ?? "function")}</span><div class="bar"><div style="width:${width}%"></div></div><span>${score}</span></div>`;
    })
    .join("");

  return `<!DOCTYPE html>
<html><body>
<style>
body{font-family:Inter,var(--vscode-font-family);padding:16px;background:linear-gradient(135deg,var(--vscode-editor-background),color-mix(in srgb,var(--vscode-editor-background) 80%, var(--vscode-focusBorder)));color:var(--vscode-foreground)}
.shell{border:1px solid var(--vscode-widget-border);border-radius:16px;padding:14px;background:color-mix(in srgb,var(--vscode-editorWidget-background) 85%, transparent);backdrop-filter:blur(8px)}
.head{display:flex;justify-content:space-between;gap:8px;align-items:center}
select,input,button,textarea{background:var(--vscode-input-background);color:var(--vscode-input-foreground);border:1px solid var(--vscode-input-border);border-radius:8px;padding:8px}
button{cursor:pointer}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.card{border:1px solid var(--vscode-widget-border);border-radius:12px;padding:12px}
.risk-row{display:grid;grid-template-columns:1fr 2fr auto;gap:8px;align-items:center;margin:6px 0}
.bar{height:8px;background:var(--vscode-editor-selectionBackground);border-radius:999px;overflow:hidden}
.bar>div{height:100%;background:var(--vscode-charts-red)}
pre{white-space:pre-wrap;max-height:180px;overflow:auto}
</style>
<div class="shell">
<div class="head">
  <h2>CodeGraphContext Command Center</h2>
  <div><button onclick="indexWorkspace()">🚀 Index Workspace</button> <button onclick="toggleWatch()">🔄 Live Watch</button></div>
</div>
<div style="display:flex;gap:8px;margin-top:8px;align-items:center">
<label>Repo</label>
<select id="repoSelect" onchange="changeRepo()"><option value="">Merged View</option>${repoOptions}</select>
<button onclick="openConfig()">Engine Config</button>
</div>
<div class="grid">
  <div class="card">
    <h3>Graph Search</h3>
    <input id="searchInput" placeholder="Search code graph (fuzzy)" style="width:100%" />
    <button style="margin-top:8px" onclick="runSearch()">Search</button>
    <pre id="searchOut">No search yet.</pre>
  </div>
  <div class="card">
    <h3>Risk Map (Complexity)</h3>
    ${hotspots || "<div>No complexity data yet.</div>"}
  </div>
</div>
<div class="card" style="margin-top:12px">
<h3>Cypher Quick Console</h3>
<textarea id="cypher" rows="5" style="width:100%">MATCH (f:Function) RETURN f.name AS name LIMIT 15</textarea>
<button style="margin-top:8px" onclick="runCypher()">Run in Cypher View</button>
<pre id="cypherOut">No cypher run yet.</pre>
<div id="status"></div>
</div>
</div>
<script>
const vscode = acquireVsCodeApi();
function indexWorkspace(){vscode.postMessage({type:'index-workspace'});}
function toggleWatch(){vscode.postMessage({type:'toggle-watch'});}
function changeRepo(){vscode.postMessage({type:'change-repo',value:document.getElementById('repoSelect').value});}
function runSearch(){vscode.postMessage({type:'run-search',query:document.getElementById('searchInput').value});}
function openConfig(){vscode.postMessage({type:'save-config'});}
function runCypher(){vscode.postMessage({type:'run-cypher',query:document.getElementById('cypher').value});}
window.addEventListener('message', (e) => {
  if(e.data.type==='search-results'){document.getElementById('searchOut').textContent=JSON.stringify(e.data.rows,null,2);}
  if(e.data.type==='cypher-results'){document.getElementById('cypherOut').textContent=JSON.stringify(e.data.rows,null,2);}
  if(e.data.type==='refresh-notice'){document.getElementById('status').textContent='Auto-refreshed: '+e.data.reason;}
});
</script></body></html>`;
}

function escapeHtml(v: string): string {
  return v.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
