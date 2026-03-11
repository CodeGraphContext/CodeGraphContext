# 🧪 Testing & Installation Guide

## 📋 Prerequisites

Before testing the extension, ensure you have:

1. **Node.js** (v20.x or higher)
   ```bash
   node --version
   ```

2. **VS Code** (v1.85.0 or higher)
   ```bash
   code --version
   ```

3. **cgc CLI** installed
   ```bash
   pip install codegraphcontext
   cgc --version
   ```

4. **A test project** to index (optional but recommended)

## 🚀 Installation Steps

### Step 1: Navigate to Extension Directory
```bash
cd /home/shashank/Desktop/CodeGraphContext/vscode-extension
```

### Step 2: Install Dependencies
```bash
npm install
```

Expected output: `added 404 packages` (already done ✅)

### Step 3: Compile TypeScript
```bash
npm run compile
```

Expected output: No errors (already done ✅)

### Step 4: Package the Extension
```bash
npm run package
```

This creates a `.vsix` file that can be installed in VS Code.

### Step 5: Install in VS Code

#### Option A: Command Line
```bash
code --install-extension codegraphcontext-0.1.0.vsix
```

#### Option B: VS Code UI
1. Open VS Code
2. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
3. Type "Extensions: Install from VSIX"
4. Select the `codegraphcontext-0.1.0.vsix` file

### Step 6: Reload VS Code
```bash
# Close and reopen VS Code, or
# Press Cmd+Shift+P and type "Reload Window"
```

## 🧪 Testing the Extension

### Test 1: Verify Installation

1. **Check Extension is Active**
   - Open VS Code
   - Press `Cmd+Shift+X` (Mac) or `Ctrl+Shift+X` (Windows/Linux)
   - Search for "CodeGraphContext"
   - Should show as installed

2. **Check Activity Bar Icon**
   - Look for the CGC icon in the left sidebar
   - Click it to open the CGC explorer

### Test 2: Index a Workspace

1. **Open a Test Project**
   ```bash
   # Use the CodeGraphContext project itself as a test
   code /home/shashank/Desktop/CodeGraphContext
   ```

2. **Index the Workspace**
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "CGC: Index Current Workspace"
   - Press Enter
   - Wait for indexing to complete (status bar will show progress)

3. **Verify Indexing**
   - Check the Projects panel in the CGC sidebar
   - Should show the indexed project with file/function counts

### Test 3: Tree Views

1. **Projects View**
   - Click the CGC icon in the activity bar
   - Expand the "Projects" section
   - Should show the indexed project

2. **Functions View**
   - Expand the "Functions" section
   - Should show functions grouped by file
   - Click on a function to navigate to it

3. **Classes View**
   - Expand the "Classes" section
   - Should show classes grouped by file
   - Click on a class to navigate to it

### Test 4: Search Functionality

1. **Search for a Function**
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "CGC: Search Code"
   - Enter a function name (e.g., "index_helper")
   - Select from results to navigate

### Test 5: Call Graph Visualization

1. **Show Call Graph**
   - Open a Python file with functions
   - Right-click on a function name
   - Select "CGC: Show Call Graph"
   - An interactive graph should appear in a new panel

2. **Test Graph Interactions**
   - Zoom: Use mouse wheel
   - Pan: Click and drag empty space
   - Move nodes: Drag individual nodes
   - Hover: Hover over nodes to see tooltips
   - Controls: Click "Reset Zoom" and "Center" buttons

### Test 6: Code Lens

1. **Enable Code Lens** (if not already enabled)
   - Press `Cmd+,` (Mac) or `Ctrl+,` (Windows/Linux)
   - Search for "cgc.enableCodeLens"
   - Ensure it's checked

2. **View Code Lens**
   - Open a Python file with functions
   - Look above function definitions
   - Should see: `← X callers | → Y callees | Show Call Graph`

3. **Click Code Lens**
   - Click on "X callers" to see callers
   - Click on "Y callees" to see callees
   - Click on "Show Call Graph" to visualize

### Test 7: Diagnostics

1. **Enable Diagnostics** (if not already enabled)
   - Press `Cmd+,` (Mac) or `Ctrl+,` (Windows/Linux)
   - Search for "cgc.enableDiagnostics"
   - Ensure it's checked

2. **View Diagnostics**
   - Open the Problems panel: `Cmd+Shift+M` (Mac) or `Ctrl+Shift+M` (Windows/Linux)
   - Should see warnings for dead code and high complexity

### Test 8: Dependencies

1. **View Dependencies**
   - Open any Python file
   - Check the "Dependencies" panel in the CGC sidebar
   - Should show imports and dependencies for the active file

2. **Navigate to Dependency**
   - Click on a dependency
   - Should navigate to the imported module

### Test 9: Analysis Commands

1. **Find Dead Code**
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "CGC: Find Dead Code"
   - Should show unused functions/classes

2. **Analyze Complexity**
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "CGC: Analyze Complexity"
   - Should show complex functions

3. **Show Statistics**
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "CGC: Show Statistics"
   - Should show project statistics in a webview

### Test 10: Status Bar

1. **Check Status Bar**
   - Look at the bottom left of VS Code
   - Should see "$(database) CGC: Ready"

2. **Click Status Bar**
   - Click on the CGC status bar item
   - Should show project statistics

## 🐛 Troubleshooting

### Extension Not Loading

**Symptoms**: Extension doesn't appear in the activity bar

**Solutions**:
1. Check if extension is installed: `code --list-extensions | grep codegraphcontext`
2. Reload VS Code window: `Cmd+Shift+P` → "Reload Window"
3. Check Output panel: View → Output → Select "CodeGraphContext"

### "cgc: command not found"

**Symptoms**: Commands fail with "cgc not found"

**Solutions**:
1. Verify cgc is installed: `which cgc`
2. Install cgc: `pip install codegraphcontext`
3. Set custom path in settings: `cgc.cgcPath`

### No Results in Tree Views

**Symptoms**: Tree views are empty

**Solutions**:
1. Index the workspace: "CGC: Index Current Workspace"
2. Check cgc is working: `cgc list` in terminal
3. Re-index: "CGC: Re-index Current Workspace"

### Graph Visualization Not Working

**Symptoms**: Graph panel is blank or shows errors

**Solutions**:
1. Check browser console in webview (Help → Toggle Developer Tools)
2. Verify D3.js is loading (check network tab)
3. Try a different function with fewer connections

### Code Lens Not Showing

**Symptoms**: No inline information above functions

**Solutions**:
1. Enable in settings: `cgc.enableCodeLens`
2. Reload window: `Cmd+Shift+P` → "Reload Window"
3. Check file is indexed: Look in Functions panel

### Diagnostics Not Working

**Symptoms**: No warnings in Problems panel

**Solutions**:
1. Enable in settings: `cgc.enableDiagnostics`
2. Save the file to trigger diagnostics
3. Check complexity threshold: `cgc.complexityThreshold`

## 📊 Performance Testing

### Small Project (< 100 files)
- Indexing: < 10 seconds
- Search: < 1 second
- Call graph: < 2 seconds

### Medium Project (100-1000 files)
- Indexing: 10-60 seconds
- Search: 1-3 seconds
- Call graph: 2-5 seconds

### Large Project (> 1000 files)
- Indexing: 1-5 minutes
- Search: 3-10 seconds
- Call graph: 5-15 seconds

## ✅ Test Checklist

Use this checklist to verify all features:

- [ ] Extension installs successfully
- [ ] CGC icon appears in activity bar
- [ ] Workspace indexes without errors
- [ ] Projects panel shows indexed projects
- [ ] Functions panel shows functions
- [ ] Classes panel shows classes
- [ ] Search finds code elements
- [ ] Navigation works from tree views
- [ ] Call graph visualizes correctly
- [ ] Graph is interactive (zoom, pan, drag)
- [ ] Code lens shows above functions
- [ ] Code lens links work
- [ ] Diagnostics show in Problems panel
- [ ] Dependencies panel shows imports
- [ ] Dead code detection works
- [ ] Complexity analysis works
- [ ] Statistics display correctly
- [ ] Status bar shows correct status
- [ ] Settings can be modified
- [ ] All commands work from palette

## 🎯 Next Steps After Testing

1. **Report Issues**
   - Document any bugs found
   - Create GitHub issues
   - Include error logs and screenshots

2. **Gather Feedback**
   - Test with different projects
   - Note performance issues
   - Identify missing features

3. **Optimize**
   - Profile slow operations
   - Implement caching
   - Improve error handling

4. **Publish**
   - Create publisher account
   - Publish to marketplace
   - Announce release

## 📝 Test Results Template

```markdown
## Test Results - [Date]

**Tester**: [Name]
**VS Code Version**: [Version]
**Extension Version**: 0.1.0
**OS**: [OS and version]

### Installation
- [ ] Installed successfully
- [ ] Extension appears in list
- [ ] Icon shows in activity bar

### Core Features
- [ ] Indexing works
- [ ] Search works
- [ ] Navigation works
- [ ] Call graph works
- [ ] Dependencies work

### UI/UX
- [ ] Tree views populate
- [ ] Code lens appears
- [ ] Diagnostics show
- [ ] Status bar updates

### Performance
- Indexing time: [X seconds]
- Search time: [X seconds]
- Graph render time: [X seconds]

### Issues Found
1. [Issue description]
2. [Issue description]

### Notes
[Any additional observations]
```

---

**Happy Testing!** 🧪

If you encounter any issues, please report them on [GitHub](https://github.com/CodeGraphContext/CodeGraphContext/issues).
