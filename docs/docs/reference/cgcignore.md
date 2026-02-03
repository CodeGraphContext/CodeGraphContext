# .cgcignore Guide

The `.cgcignore` file tells CodeGraphContext which files or folders to skip during indexing. It functions exactly like `.gitignore`.

## Why use it?
*   **Performance:** Skipping large directories (like `node_modules` or `vendor`) makes indexing significantly faster.
*   **Relevance:** Excluding tests, build artifacts, or generated code keeps your knowledge graph focused on source code.
*   **Security:** Ensure sensitive configuration files aren't indexed (though everything remains local).

## File Specification

*   **Filename:** `.cgcignore`
*   **Location:** Root of your project (where you run `cgc index`).
*   **Syntax:** Standard glob patterns (same as git).

## Example

Create a file named `.cgcignore` in your project root with the following content:

```text
# Dependency directories
node_modules/
venv/
.venv/
__pycache__/

# Build artifacts
dist/
build/
target/
*.egg-info/

# Tests (Optional - if you only want source code)
tests/
spec/
**/*_test.py
**/*.test.js

# Sensitive files
.env
config.js
secrets.json

# Documentation
docs/
*.md
```
