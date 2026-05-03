# Indexing Source Code

Indexing is the process of parsing your source code and materializing it into the code graph. CodeGraphContext (CGC) supports various indexing strategies to suit different workflows.

## 1. Local Repository Indexing

The most common use case is indexing the project you are currently working on.

```bash
cd /path/to/project
cgc index
```

### Partial Scans
If you only want to index a specific subdirectory or file:

```bash
cgc index ./src/core
```

### Incremental Updates
CGC is smart enough to skip files that haven't changed since the last index. Simply run `cgc index` again to sync your changes.

---

## 2. Dependency Indexing

To get a complete picture of your application, you may want to index its dependencies.

### Python Packages
CGC can automatically find and index installed Python packages:

```bash
cgc index-package requests
```

### Generic Folders
You can also index any arbitrary folder and mark it as a dependency:

```bash
cgc index --path /path/to/lib --dependency
```

---

## 3. Real-time Monitoring (`watch`)

For projects under active development, use the `watch` command. CGC will monitor your filesystem for changes (create, update, delete) and keep the graph in sync in the background.

```bash
cgc watch
```

*   **Background Jobs**: The watch command runs as a background process.
*   **Status**: Check the status of your watchers with `cgc list-watchers`.

---

## 4. Advanced Indexing Options

| Option | Description |
| :--- | :--- |
| `--deep` | Performs a deep scan, following imports and resolving external symbols. |
| `--scip` | (Experimental) Uses SCIP index data if available for higher precision. |
| `--exclude` | Glob patterns to ignore (e.g., `**/tests/**`). |

### The `.cgcignore` File
Similar to `.gitignore`, you can create a `.cgcignore` file in your repository root to permanently exclude files or directories from the index.

```text
# Example .cgcignore
node_modules/
dist/
*.pyc
```

---

## Performance Tips

*   **Memory**: Large repositories may require significant memory during the initial parse phase.
*   **Storage**: Ensure you have enough disk space for the graph database (usually 2-5x the size of the source code).
