# CodeGraphContext VS Code Extension - Development Guide

## 🏗️ Architecture

### Overview
The extension is built with TypeScript and integrates with the cgc CLI to provide code analysis features directly in VS Code.

### Core Components

#### 1. **Extension Entry Point** (`src/extension.ts`)
- Activates the extension
- Registers all commands
- Initializes providers
- Sets up file watchers

#### 2. **CGC Manager** (`src/cgcManager.ts`)
- Handles all communication with cgc CLI
- Executes commands and parses output
- Provides typed interfaces for results

#### 3. **Tree View Providers** (`src/providers/`)
- **ProjectsTreeProvider**: Shows indexed projects
- **FunctionsTreeProvider**: Lists functions grouped by file
- **ClassesTreeProvider**: Lists classes grouped by file
- **CallGraphTreeProvider**: Shows callers/callees for current function
- **DependenciesTreeProvider**: Shows dependencies for active file

#### 4. **Code Lens Provider** (`src/providers/codeLensProvider.ts`)
- Shows inline caller/callee counts
- Provides quick navigation links

#### 5. **Diagnostics Provider** (`src/providers/diagnosticsProvider.ts`)
- Detects dead code
- Warns about high complexity
- Integrates with VS Code Problems panel

#### 6. **Graph Visualization** (`src/panels/graphVisualizationPanel.ts`)
- Interactive D3.js force-directed graph
- Zoom, pan, and drag capabilities
- Webview-based rendering

#### 7. **Status Bar Manager** (`src/statusBarManager.ts`)
- Shows indexing status
- Provides quick access to stats

## 🚀 Getting Started

### Prerequisites
- Node.js 20.x or higher
- npm or yarn
- VS Code 1.85.0 or higher
- cgc CLI installed (`pip install codegraphcontext`)

### Installation

```bash
# Navigate to the extension directory
cd vscode-extension

# Install dependencies
npm install

# Compile TypeScript
npm run compile
```

### Development Workflow

1. **Open in VS Code**
   ```bash
   code .
   ```

2. **Start Watch Mode**
   ```bash
   npm run watch
   ```

3. **Launch Extension**
   - Press `F5` or use "Run Extension" from the Debug panel
   - A new VS Code window will open with the extension loaded

4. **Make Changes**
   - Edit TypeScript files
   - The watch task will automatically recompile
   - Reload the extension host window (`Cmd+R` or `Ctrl+R`)

### Testing

```bash
# Run linter
npm run lint

# Run tests (when implemented)
npm test
```

## 📁 Project Structure

```
vscode-extension/
├── src/
│   ├── extension.ts              # Main entry point
│   ├── cgcManager.ts              # CGC CLI integration
│   ├── statusBarManager.ts        # Status bar UI
│   ├── providers/
│   │   ├── projectsTreeProvider.ts
│   │   ├── functionsTreeProvider.ts
│   │   ├── classesTreeProvider.ts
│   │   ├── callGraphTreeProvider.ts
│   │   ├── dependenciesTreeProvider.ts
│   │   ├── codeLensProvider.ts
│   │   └── diagnosticsProvider.ts
│   └── panels/
│       └── graphVisualizationPanel.ts
├── resources/
│   └── icon.svg                   # Extension icon
├── .vscode/
│   ├── launch.json                # Debug configuration
│   └── tasks.json                 # Build tasks
├── package.json                   # Extension manifest
├── tsconfig.json                  # TypeScript config
├── .eslintrc.json                 # ESLint config
├── README.md                      # User documentation
├── CHANGELOG.md                   # Version history
└── DEVELOPMENT.md                 # This file
```

## 🔧 Key Concepts

### Command Registration
Commands are registered in `extension.ts`:
```typescript
context.subscriptions.push(
    vscode.commands.registerCommand('cgc.index', async () => {
        // Command implementation
    })
);
```

### Tree View Data Providers
Implement `vscode.TreeDataProvider<T>`:
```typescript
export class MyTreeProvider implements vscode.TreeDataProvider<MyTreeItem> {
    getTreeItem(element: MyTreeItem): vscode.TreeItem {
        return element;
    }
    
    async getChildren(element?: MyTreeItem): Promise<MyTreeItem[]> {
        // Return children
    }
}
```

### Webview Panels
Create interactive HTML panels:
```typescript
const panel = vscode.window.createWebviewPanel(
    'myView',
    'My View',
    vscode.ViewColumn.Two,
    { enableScripts: true }
);
panel.webview.html = getHtmlContent();
```

### CGC CLI Integration
Execute cgc commands:
```typescript
const output = await this.executeCgcCommand(['search', 'myFunction']);
const results = this.parseSearchResults(output);
```

## 🎨 UI/UX Guidelines

### Icons
- Use VS Code's built-in Codicons: `$(icon-name)`
- Keep icons consistent with VS Code's design language

### Colors
- Use CSS variables for theming: `var(--vscode-editor-background)`
- Support both light and dark themes

### Progress Indicators
- Use `vscode.window.withProgress()` for long operations
- Update status bar for background tasks

### Error Handling
- Show user-friendly error messages
- Log detailed errors to console for debugging

## 🐛 Debugging

### Extension Host
- Set breakpoints in TypeScript files
- Press `F5` to start debugging
- Use Debug Console for logging

### Webview Debugging
- Open Developer Tools in the extension host window
- Use `console.log()` in webview HTML
- Inspect webview elements

### CGC CLI Debugging
- Check cgc command output in console
- Verify cgc is in PATH
- Test commands manually in terminal

## 📦 Building & Publishing

### Create VSIX Package
```bash
npm run package
```

### Install Locally
```bash
code --install-extension codegraphcontext-0.1.0.vsix
```

### Publish to Marketplace
```bash
# First time: Create publisher account
vsce create-publisher <publisher-name>

# Login
vsce login <publisher-name>

# Publish
npm run publish
```

## 🔄 Release Process

1. Update version in `package.json`
2. Update `CHANGELOG.md`
3. Commit changes
4. Create git tag: `git tag v0.1.0`
5. Push tag: `git push --tags`
6. Build package: `npm run package`
7. Publish: `npm run publish`

## 🤝 Contributing

### Code Style
- Follow TypeScript best practices
- Use ESLint for linting
- Format code consistently
- Add JSDoc comments for public APIs

### Pull Requests
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Commit Messages
Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test changes

## 📚 Resources

- [VS Code Extension API](https://code.visualstudio.com/api)
- [VS Code Extension Samples](https://github.com/microsoft/vscode-extension-samples)
- [Tree View Guide](https://code.visualstudio.com/api/extension-guides/tree-view)
- [Webview Guide](https://code.visualstudio.com/api/extension-guides/webview)
- [D3.js Documentation](https://d3js.org/)

## 🎯 Roadmap

### Short Term (v0.2.0)
- [ ] Add unit tests
- [ ] Improve error handling
- [ ] Optimize performance for large codebases
- [ ] Add more graph layout options

### Medium Term (v0.3.0)
- [ ] Language Server Protocol (LSP) integration
- [ ] Custom Cypher query builder UI
- [ ] Export graph visualizations
- [ ] Advanced filtering options

### Long Term (v1.0.0)
- [ ] Git integration for change analysis
- [ ] Collaborative features
- [ ] Performance profiling
- [ ] AI-powered code suggestions

## ❓ FAQ

**Q: How do I add a new command?**
A: Register it in `extension.ts` and add to `package.json` contributes.commands

**Q: How do I add a new tree view?**
A: Create a provider in `src/providers/`, register in `extension.ts`, and add to `package.json` contributes.views

**Q: How do I debug webview panels?**
A: Open Developer Tools in the extension host window and inspect the webview

**Q: How do I handle cgc CLI errors?**
A: Wrap calls in try-catch and show user-friendly messages with `vscode.window.showErrorMessage()`

## 📞 Support

- GitHub Issues: [Report bugs](https://github.com/CodeGraphContext/CodeGraphContext/issues)
- Discord: [Join community](https://discord.gg/VCwUdCnn)
- Email: shashankshekharsingh1205@gmail.com

---

Happy coding! 🚀
