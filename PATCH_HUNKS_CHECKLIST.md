# Patch Hunk Checklist

One checkbox per current diff hunk.

## src/codegraphcontext/cli/cli_helpers.py
- [x] Hunk 1: `@@ -2,6 +2,9 @@ import asyncio`
- [x] Hunk 2: `@@ -753,3 +756,127 @@ def list_watching_helper():`
## src/codegraphcontext/cli/main.py
- [x] Hunk 1: `@@ -42,6 +42,10 @@ from .cli_helpers import (`
- [x] Hunk 2: `@@ -1199,6 +1203,60 @@ def watching(`
- [x] Hunk 3: `@@ -2388,4 +2446,4 @@ def main(`
## src/codegraphcontext/server.py
- [x] Hunk 1: `@@ -12,7 +12,7 @@ from datetime import datetime`
- [x] Hunk 2: `@@ -96,7 +96,9 @@ class MCPServer:`
- [x] Hunk 3: `@@ -247,6 +249,49 @@ class MCPServer:`
- [x] Hunk 4: `@@ -258,13 +303,12 @@ class MCPServer:`
- [x] Hunk 5: `@@ -319,7 +363,7 @@ class MCPServer:`
- [x] Hunk 6: `@@ -331,7 +375,7 @@ class MCPServer:`
## src/codegraphcontext/tools/code_finder.py
- [x] Hunk 1: `@@ -15,12 +15,121 @@ class CodeFinder:`
- [x] Hunk 2: `@@ -54,8 +163,15 @@ class CodeFinder:`
- [x] Hunk 3: `@@ -75,7 +191,14 @@ class CodeFinder:`
- [x] Hunk 4: `@@ -100,6 +223,8 @@ class CodeFinder:`
- [x] Hunk 5: `@@ -122,6 +247,35 @@ class CodeFinder:`
- [x] Hunk 6: `@@ -183,8 +337,8 @@ class CodeFinder:`
## src/codegraphcontext/tools/graph_builder.py
- [x] Hunk 1: `@@ -182,6 +182,30 @@ class GraphBuilder:`
- [x] Hunk 2: `@@ -204,7 +228,7 @@ class GraphBuilder:`
