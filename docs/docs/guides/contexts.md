# Contexts: Managing Multiple Code Graphs

CodeGraphContext (CGC) uses a **context system** to decide _where_ your code graph lives on disk. This lets you keep separate projects in separate databases, share one big database across everything, or let each repo manage its own graph — all without changing how you use `cgc`.

This guide walks through every mode from scratch with copy-pasteable examples.

---

## Quick Orientation

```
~/.codegraphcontext/            <-- global config home
    config.yaml                 <-- mode + named context registry
    .env                        <-- DB credentials, tuning knobs
    global/
        .cgcignore              <-- default ignore patterns
        db/
            falkordb/           <-- global-mode database
    contexts/
        ProjectAB/
            db/
                falkordb/       <-- named-context database
            .cgcignore          <-- per-context ignore patterns
```

When you run `cgc index .` (or any other command), CGC resolves _which database_ to talk to by checking, in order:

1. **`--context <name>` flag** — always wins if provided. The name is any string you choose (e.g. `MyProject`, `client-acme`, `backend-v2`). It doesn't need to be pre-created; indexing with `--context` auto-creates the context for you.
2. **Local `.codegraphcontext/` folder** — if one exists in the current working directory (and it isn't the global `~/.codegraphcontext`), per-repo mode kicks in.
3. **`config.yaml` mode** — the system-wide mode (`global`, `per-repo`, or `named`) plus the default context name.
4. **Fallback** — global mode, default database backend.

---

## The Three Modes

### 1. Global (default)

Every project shares a single database under `~/.codegraphcontext/global/db/<backend>/`.

```bash
# Check your current mode
cgc context list

# Explicitly set global mode (this is the factory default)
cgc context mode global
```

Index anything and it all lands in the same graph:

```bash
cd ~/projects/backend
cgc index .

cd ~/projects/frontend
cgc index .

# Both repos are visible in one graph
cgc list
```

**Best for:** Solo developers working on a handful of related repos who want cross-project call tracing.

---

### 2. Per-Repo

Each repository gets its own `.codegraphcontext/` folder (like `.git/`) with a private database inside.

```bash
cgc context mode per-repo
```

Now when you index:

```bash
cd ~/projects/backend
cgc index .
# Creates ~/projects/backend/.codegraphcontext/db/falkordb/
```

```bash
cd ~/projects/frontend
cgc index .
# Creates ~/projects/frontend/.codegraphcontext/db/falkordb/
```

The two graphs are completely isolated. `cgc list` inside `backend/` only shows the backend repo.

CGC only checks the current working directory for a `.codegraphcontext/` folder — it does not walk up parent directories. This means you always get the context of the directory you're standing in, with no surprises from a parent project.

**Best for:** Large teams or monorepos where you want zero cross-project interference and the graph config checked into version control.

> **Tip:** Add `.codegraphcontext/` to your `.gitignore` if you don't want the DB committed. Keep it out of `.gitignore` if you want teammates to share the same config.

---

### 3. Named Contexts

Named contexts are like Git branches for your databases. You create a logical workspace, give it a name, and point one or more repos at it.

```bash
# Switch to named mode
cgc context mode named

# Create a context (optional — indexing auto-creates it)
cgc context create MyProject

# Index a repo into that context
cgc index ~/projects/api --context MyProject
cgc index ~/projects/web --context MyProject

# Both repos share the "MyProject" graph
cgc list --context MyProject
```

If the context doesn't exist when you pass `--context`, CGC creates it automatically — you don't need a separate `create` step.

Set a default so you can stop typing `--context` every time:

```bash
cgc context default MyProject

# Now bare commands use MyProject
cgc list          # same as: cgc list --context MyProject
cgc stats         # same as: cgc stats --context MyProject
```

**Best for:** Consultants juggling client projects, teams with shared infra repos, or anyone who wants explicit workspace separation without scattering config folders inside repos.

---

## Switching Modes

Two equivalent ways:

```bash
# Via the context subcommand
cgc context mode named

# Via config set (alias)
cgc config set mode named
```

Valid values: `global`, `per-repo`, `named`.

Switching mode does **not** delete any data. Your old databases stay on disk; CGC just changes which one it connects to.

---

## Working With Named Contexts

### Create

```bash
cgc context create mobile-app
cgc context create mobile-app --database kuzudb          # use KùzuDB instead
cgc context create mobile-app --db-path /mnt/fast/cgc    # custom location
```

### List

```bash
cgc context list
```

Output shows the current mode, default context (marked with `*`), all registered contexts with their database backend and linked repos.

### Set Default

```bash
cgc context default mobile-app
```

### Delete

```bash
cgc context delete mobile-app
```

This removes the context from the registry. The actual database files on disk are preserved — delete them manually if you want to reclaim space.

---

## The `--context` Flag

The `--context` (or `-c`) flag is accepted on data-accessing commands and always overrides the mode:

```bash
cgc index .              --context ProjectA
cgc index ./libs/shared  --context ProjectA
cgc list                 --context ProjectA
cgc stats                --context ProjectA
cgc delete ./libs/shared --context ProjectA
cgc clean                --context ProjectA
cgc query "MATCH (f:Function) RETURN f.name LIMIT 5" --context ProjectA
```

Even if you're in `global` mode, passing `--context` forces named-context resolution for that single invocation.

---

## MCP Server & IDE Integration

When your IDE starts the MCP server (`cgc mcp start`), context resolution happens based on the **working directory the server was launched from**:

| Mode | What the MCP server connects to |
|---|---|
| `global` | `~/.codegraphcontext/global/db/<backend>/` |
| `per-repo` | `<cwd>/.codegraphcontext/db/<backend>/` |
| `named` | The default named context's database |

This means your AI assistant (Cursor, Claude Desktop, etc.) automatically sees the right graph without any extra config — just make sure the MCP server starts from the correct project directory.

---

## `.cgcignore` Resolution

Each context level can have its own `.cgcignore`:

| Mode | `.cgcignore` location |
|---|---|
| Global | `~/.codegraphcontext/global/.cgcignore` |
| Per-repo | `<repo>/.codegraphcontext/.cgcignore` |
| Named | `~/.codegraphcontext/contexts/<name>/.cgcignore` |

On first install, CGC creates the global `.cgcignore` with sensible defaults (node_modules, venv, build dirs, etc.). You can edit it at any time.

---

## End-to-End Example: New User Setup

Starting from a fresh install with two projects — a Python API and a React frontend.

```bash
# 1. Install CGC (if not already)
pip install codegraphcontext

# 2. First run — CGC bootstraps config automatically
cgc index ~/projects/my-api
#   -> Creates ~/.codegraphcontext/ with config.yaml, global .cgcignore
#   -> Prints a one-time welcome banner explaining modes
#   -> Indexes my-api into the global database

# 3. Index another project (still in global mode, shares the same DB)
cgc index ~/projects/my-frontend

# 4. See both repos in the same graph
cgc list
#   my-api        ~/projects/my-api
#   my-frontend   ~/projects/my-frontend

# 5. Query across both projects
cgc query "MATCH (f:Function) RETURN f.name, f.path LIMIT 10"
```

### Switching to named contexts

```bash
# 6. Decide you want isolated graphs
cgc context mode named

# 7. Re-index into separate contexts (auto-creates them)
cgc index ~/projects/my-api      --context API
cgc index ~/projects/my-frontend  --context Frontend

# 8. Work within one context
cgc context default API
cgc list                # only shows my-api
cgc analyze callers authenticate_user

# 9. Peek at the other context when needed
cgc list --context Frontend
```

### Setting up the MCP server for your IDE

```bash
# 10. Start MCP from the API project directory
cd ~/projects/my-api
cgc mcp start
# The server resolves context based on CWD and connects to the right DB
```

---

## Configuration File Reference

### `~/.codegraphcontext/config.yaml`

```yaml
version: 1
mode: named                # global | per-repo | named
default_context: API       # used when mode=named and no --context flag
contexts:
  API:
    database: falkordb
    db_path: /home/user/.codegraphcontext/contexts/API/db/falkordb
    repos:
      - /home/user/projects/my-api
    cgcignore_path: /home/user/.codegraphcontext/contexts/API/.cgcignore
  Frontend:
    database: falkordb
    db_path: /home/user/.codegraphcontext/contexts/Frontend/db/falkordb
    repos:
      - /home/user/projects/my-frontend
    cgcignore_path: /home/user/.codegraphcontext/contexts/Frontend/.cgcignore
```

### `~/.codegraphcontext/global/.cgcignore`

```text
node_modules/
venv/
.venv/
dist/
build/
__pycache__/
*.pyc
.git/
.idea/
```

Edit this to add project-wide ignore patterns. For per-context overrides, edit the `.cgcignore` inside the context's directory.

---

## Migration From Older Versions

If you were using CGC before the context system was added:

- **`cgc_config.yaml`** is automatically migrated to **`config.yaml`** on first load. The old file is preserved as a backup.
- **Existing global database** at `~/.codegraphcontext/global/falkordb.db` continues to be used. New installs use the `global/db/falkordb/` layout, but CGC detects the legacy path and keeps using it.
- All changes are additive — `cgc index .` with no flags behaves identically to before.

---

## Quick Reference

| Task | Command |
|---|---|
| Check current mode | `cgc context list` |
| Switch to global mode | `cgc context mode global` |
| Switch to per-repo mode | `cgc context mode per-repo` |
| Switch to named mode | `cgc context mode named` |
| Create a named context | `cgc context create <name>` |
| Delete a named context | `cgc context delete <name>` |
| Set default context | `cgc context default <name>` |
| Index into a specific context | `cgc index . --context <name>` |
| Set mode via config | `cgc config set mode named` |
| View all config | `cgc config show` |
