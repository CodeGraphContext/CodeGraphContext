# Troubleshooting & FAQ

Every entry here comes from a real reported issue. Links point at the fix or
the deeper discussion.

## Indexing

### `cgc index .` says "already indexed … Skipping" — how do I re-index?
Use `cgc index . --force`. The skip guard compares the graph's file count
against what discovery expects; a complete graph is skipped to save time.

### It keeps saying "only N of M files indexed. Continuing." on every run
Fixed in 0.6.8 (#1673): every discovered file now gets at least a minimal
File node, so the census converges. If you still see it, the message now
lists the missing files — that list is exactly what to include in a bug
report.

### Indexing finishes but reports nothing (SCIP)
Also 0.6.8: SCIP-driven runs (e.g. `scip-dotnet`) previously skipped the
summary table entirely. Upgrade; the execution summary now prints for both
pipelines.

### A file git ignores is being indexed / isn't being indexed
Since 0.6.9 (#1680), ignore patterns layer as **defaults → .gitignore →
.cgcignore**, last match wins. So `.cgcignore` always has the final say:
re-include a git-ignored path with a `!pattern` line, or exclude extra paths
that git tracks.

### .NET: generated files pollute the graph
`obj/` is in the default ignore list since 0.6.1 (#1585). `bin/` is NOT
ignored by default (some projects keep real scripts there) — add it to your
`.cgcignore` for .NET solutions.

## Databases

### "Could not set lock on file" when running CLI commands
Another CGC process (a Gateway, an MCP server, a watcher) already has the
embedded database open — KùzuDB/LadybugDB are single-process. Use the
running process's interface, or stop it first (#1683). This is not a
configuration problem; `cgc doctor` won't help.

### LadybugDB: "Buffer manager exception: unable to allocate memory" (or a crash)
The buffer pool is too small for the workload — ladybug 0.20.x needs more
pool than 0.19.x for the same graph. Raise `CGC_EMBEDDED_BUFFER_POOL_MB`
(2048 is a good floor); the unset default adapts to available memory.

### Which backend am I actually using?
`cgc config show` prints the resolved backend and its source. FalkorDB is
the default where its native library loads; environments where it cannot
load fall back to KùzuDB — the startup line names the backend in use.

### The visualizer shows nodes but no edges
Fixed in 0.6.9 (#1689) for FalkorDB. If you see this on another backend,
file an issue with the backend name — edge classification is
backend-specific.

## Named contexts

### `cgc context list` shows "Repos Linked: 0" but queries work
Fixed in 0.6.10 (#1317): repo registration used to be skipped when the graph
was already populated, permanently desyncing `config.yaml`. On current
versions, simply run `cgc index . --context <name>` once — even if it
skips, the repo is registered.

## MCP / tools

### `ENABLE_VECTOR_RESOLVE=true` but nothing uses embeddings
Since 0.6.3 (#1597) this states its reason loudly: config-set warns at the
moment you enable it, and the index summary prints an always-visible
"embeddings were NOT generated: …" line when no embedding backend is
installed. `pip install fastembed` (or `sentence-transformers`) and re-index.

### `find_functions_by_argument` returns nothing for a type name
Fixed in 0.6.9 (#1685): it now matches argument *types* (`OrderFilter`) as
well as parameter names. Re-index once so `arg_types` is populated on the
embedded backends.

## Development / testing

### The parser tests pass locally but disagree with CI
Check `tree-sitter-language-pack` against the pyproject pin — a stale venv
silently tests a different grammar and can invert parser results (#1625).
The suite fails loudly on the mismatch since 0.6.1
(`tests/unit/test_environment_pins.py`); recreate the venv with
`pip install -e .[dev]`.

### The setup wizard broke my VS Code settings.json
Fixed in 0.6.9 (#1677): JSONC (comments, trailing commas) is now parsed,
the previous file is backed up as `settings.json.cgc-backup` before any
rewrite, and an unparseable file is left untouched.

## CI integration

### Failing the build on complexity
```
cgc index .
cgc analyze complexity --threshold 10 --format json --fail-on-violations
```
Exit code 1 when any function exceeds the threshold; stdout carries only the
JSON document. Full recipe: `docs/CI_INTEGRATION.md`.

## Still stuck?

Open an issue with: your `cgc --version`, the backend line from startup, the
exact command, and the full output. The Discord invite in the README is the
fastest route for questions that aren't bugs.
