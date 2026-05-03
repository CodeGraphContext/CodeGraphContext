export function renderSetupHtml(
  executable: string,
  dbMode: string,
  pythonPackagePath: string,
  maxToolResponseTokens: number,
  neo4jUri: string
): string {
  return `<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CGC Setup</title>
        <style>
            body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 20px; line-height: 1.6; }
            .container { max-width: 600px; margin: 0 auto; background: var(--vscode-editor-background); padding: 30px; border-radius: 8px; border: 1px solid var(--vscode-widget-border); box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            h1 { color: var(--vscode-textLink-foreground); font-weight: 300; border-bottom: 1px solid var(--vscode-widget-border); padding-bottom: 10px; }
            .field { margin-bottom: 25px; }
            label { display: block; margin-bottom: 8px; font-weight: bold; font-size: 0.9em; opacity: 0.8; }
            input, select { width: 100%; padding: 10px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 4px; box-sizing: border-box; }
            .actions { display: flex; gap: 10px; margin-top: 30px; }
            button { padding: 10px 20px; cursor: pointer; border: none; border-radius: 4px; font-weight: bold; transition: opacity 0.2s; }
            button.primary { background: var(--vscode-button-background); color: var(--vscode-button-foreground); }
            button.secondary { background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); }
            button:hover { opacity: 0.9; }
            #status { margin-top: 20px; padding: 15px; border-radius: 4px; display: none; }
            .status-testing { background: rgba(255, 255, 0, 0.1); border: 1px solid yellow; color: yellow; display: block !important; }
            .status-success { background: rgba(0, 255, 0, 0.1); border: 1px solid green; color: #4caf50; display: block !important; }
            .status-error { background: rgba(255, 0, 0, 0.1); border: 1px solid red; color: #f44336; display: block !important; }
            .status-warning { background: rgba(255, 165, 0, 0.1); border: 1px solid orange; color: orange; display: block !important; }
            .hint { font-size: 0.8em; opacity: 0.6; margin-top: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>CodeGraphContext Setup</h1>
            <p>Configure and verify your CGC environment to enable editor intelligence.</p>
            <div class="field"><label>CGC Executable Path</label><input type="text" id="executable" value="${executable}"></div>
            <div class="field"><label>Database Mode</label><select id="dbMode"><option value="ladybugdb" ${dbMode === "ladybugdb" ? "selected" : ""}>LadybugDB (Embedded)</option><option value="falkordb" ${dbMode === "falkordb" ? "selected" : ""}>FalkorDB (Redis-based)</option><option value="neo4j" ${dbMode === "neo4j" ? "selected" : ""}>Neo4j</option></select></div>
            <div class="field"><label>Python Package Path / uvx Path</label><input type="text" id="pythonPackagePath" value="${pythonPackagePath}"></div>
            <div class="field"><label>Neo4j URI</label><input type="text" id="neo4jUri" value="${neo4jUri}"></div>
            <div class="field"><label>Max Tool Response Tokens</label><input type="number" id="maxToolResponseTokens" value="${maxToolResponseTokens}" min="0"></div>
            <div id="status"></div>
            <div class="actions"><button class="secondary" onclick="test()">Test Connection</button><button class="primary" onclick="save()">Save & Apply</button></div>
        </div>
        <script>
            const vscode = acquireVsCodeApi();
            const statusDiv = document.getElementById('status');
            function test(){ const executable = document.getElementById('executable').value; const dbMode = document.getElementById('dbMode').value; vscode.postMessage({ command: 'test', executable, dbMode }); }
            function save(){ const executable = document.getElementById('executable').value; const dbMode = document.getElementById('dbMode').value; const pythonPackagePath = document.getElementById('pythonPackagePath').value; const maxToolResponseTokens = Number(document.getElementById('maxToolResponseTokens').value || 0); const neo4jUri = document.getElementById('neo4jUri').value; vscode.postMessage({ command: 'save', executable, dbMode, pythonPackagePath, maxToolResponseTokens, neo4jUri }); }
            window.addEventListener('message', event => { const message = event.data; if (message.command === 'testResult') { statusDiv.className = 'status-' + message.status; statusDiv.innerText = message.message; } else if (message.command === 'saved') { statusDiv.className = 'status-success'; statusDiv.innerText = 'Settings saved and applied successfully!'; }});
        </script>
    </body>
    </html>`;
}
