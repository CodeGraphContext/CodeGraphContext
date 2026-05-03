# CodeGraphContext VS Code Extension

CodeGraphContext brings graph-native code intelligence into VS Code through CGC MCP.

## Highlights
- Command Center dashboard (index, watch, search, risk map, repo selector).
- Interactive call graph panel with editor synchronization.
- CodeLens, hover mini-map, dead-code diagnostics, and quick-fix action.
- Repositories, bundles, and watch state explorer views.
- Cypher console with direct graph querying.
- Variable impact radius and signature-change impact warnings.
- Engine configuration cockpit for executable/database/token controls.

## Build
- `npm install`
- `npm run compile`
- `npm run test`
- `npm run package:vsix`
# CodeGraphContext (CGC) VS Code Extension

The CGC extension brings powerful code graph intelligence directly into your VS Code workspace.

## Features

- **🚀 Indexing Wizard**: Create a code graph for your project with one click.
- **🔍 Editor Intelligence**: CodeLens and Hover metadata for complexity and call counts.
- **📊 Interactive Call Graph**: Visualize relationships in real-time.
- **🛠️ CGC Explorer**: Manage Repositories, Bundles, and run Cypher queries.
- **🔗 Dead Code Diagnostics**: Find and fix unused code.

## Quick Start

1. Install the extension.
2. Open your project folder.
3. Run `CGC: Run Indexing Wizard` from the Command Palette (`Ctrl+Shift+P`).

## Configuration

Settings available under `CGC`:
- `cgc.executable`: Path to your `cgc` binary.
- `cgc.databaseMode`: Backend choice (`ladybugdb`, `falkordb`).
- `cgc.complexityWarningThreshold`: Set limit for complexity alerts.
