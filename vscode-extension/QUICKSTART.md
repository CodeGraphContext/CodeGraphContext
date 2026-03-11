# 🚀 Quick Start Guide - CodeGraphContext VS Code Extension

## Installation

### Step 1: Install cgc CLI
```bash
pip install codegraphcontext
```

### Step 2: Install the Extension

#### Option A: From VSIX (Development)
```bash
cd vscode-extension
npm install
npm run compile
npm run package
code --install-extension codegraphcontext-0.1.0.vsix
```

#### Option B: From Marketplace (Coming Soon)
1. Open VS Code
2. Go to Extensions (`Cmd+Shift+X` or `Ctrl+Shift+X`)
3. Search for "CodeGraphContext"
4. Click Install

## First Steps

### 1. Open a Project
Open any code project in VS Code.

### 2. Index Your Code
- Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
- Type "CGC: Index Current Workspace"
- Press Enter

The extension will index your code in the background. You'll see a status indicator in the status bar.

### 3. Explore the Sidebar
Click the CGC icon in the Activity Bar (left sidebar) to see:
- **Projects**: All indexed projects
- **Functions**: All functions in your code
- **Classes**: All classes in your code
- **Call Graph**: Callers and callees for the current function
- **Dependencies**: Dependencies for the active file

### 4. Use Code Lens
Open any file with functions. You'll see inline information above each function:
```
← 3 callers | → 5 callees | Show Call Graph
def my_function():
    ...
```

Click on any code lens to navigate or visualize.

### 5. Search Code
- Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
- Type "CGC: Search Code"
- Enter a function, class, or file name
- Select from results to navigate

## Common Tasks

### View Call Graph
1. Right-click on a function name
2. Select "CGC: Show Call Graph"
3. Explore the interactive graph visualization

### Find Dead Code
1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type "CGC: Find Dead Code"
3. View unused functions and classes

### Analyze Complexity
1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type "CGC: Analyze Complexity"
3. See functions that exceed the complexity threshold

### Load a Bundle
1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type "CGC: Load Bundle"
3. Enter a bundle name (e.g., "numpy", "pandas")
4. Explore the pre-indexed code

## Configuration

### Open Settings
1. Press `Cmd+,` (Mac) or `Ctrl+,` (Windows/Linux)
2. Search for "cgc"
3. Adjust settings as needed

### Key Settings
- **Auto Index**: Automatically index workspace on startup
- **Code Lens**: Show inline caller/callee information
- **Diagnostics**: Show warnings for dead code and complexity
- **Complexity Threshold**: Set the complexity warning threshold

## Keyboard Shortcuts

You can add custom keyboard shortcuts:
1. Press `Cmd+K Cmd+S` (Mac) or `Ctrl+K Ctrl+S` (Windows/Linux)
2. Search for "cgc"
3. Click the + icon to add a shortcut

Suggested shortcuts:
- `Cmd+Shift+G` (Mac) or `Ctrl+Shift+G` (Windows/Linux): Show Call Graph
- `Cmd+Shift+F` (Mac) or `Ctrl+Shift+F` (Windows/Linux): Search Code

## Tips & Tricks

### 1. Use the Status Bar
Click the "CGC: Ready" status bar item to see project statistics.

### 2. Navigate Quickly
Click on any function or class in the tree views to jump to its definition.

### 3. Explore Dependencies
Open a file and check the Dependencies panel to see what it imports.

### 4. Interactive Graphs
In graph visualizations:
- **Zoom**: Mouse wheel or pinch
- **Pan**: Click and drag empty space
- **Move nodes**: Drag individual nodes
- **Hover**: See detailed information

### 5. Context Menus
Right-click on functions in the editor to access CGC commands.

## Troubleshooting

### "cgc: command not found"
Make sure cgc is installed and in your PATH:
```bash
pip install codegraphcontext
which cgc  # Should show the path to cgc
```

### Extension Not Working
1. Check the Output panel (View → Output)
2. Select "CodeGraphContext" from the dropdown
3. Look for error messages

### Slow Indexing
For large codebases:
1. Disable "Index Source" in settings (faster but no code search)
2. Use `.cgcignore` to exclude unnecessary directories
3. Consider loading a pre-indexed bundle instead

### No Results in Tree Views
1. Make sure you've indexed the workspace
2. Check that cgc is working: `cgc list` in terminal
3. Try re-indexing: "CGC: Re-index Current Workspace"

## Next Steps

- Read the [full README](README.md) for detailed features
- Check the [development guide](DEVELOPMENT.md) to contribute
- Join our [Discord community](https://discord.gg/VCwUdCnn)
- Report issues on [GitHub](https://github.com/CodeGraphContext/CodeGraphContext/issues)

---

**Happy coding with CodeGraphContext!** 🎉
