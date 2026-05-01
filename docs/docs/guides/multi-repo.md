# Multi-Repository Workflows

In modern development, you often work across multiple microservices or repositories simultaneously. CodeGraphContext (CGC) is designed to handle these multi-project environments gracefully.

## 1. Context Switching

CGC uses the concept of **Contexts** to manage different indexed projects. Each project typically has its own `.codegraphcontext` folder.

### Discovering Contexts
If you open your IDE at a root level containing multiple projects, you can scan for existing indexes:

```bash
cgc context discover
```

### Switching Active Context
To switch the current session to a specific project:

```bash
cgc context switch /path/to/project_b
```

Once switched, all subsequent CLI queries and MCP tool calls will target the project at that path.

---

## 2. Cross-Repository Indexing

You can index multiple repositories into a single unified graph database (best when using Neo4j or a remote FalkorDB instance).

### Strategy: Unified Backend
1.  Set up a central Neo4j instance.
2.  Configure all projects to use this backend.
3.  Run `cgc index` in each project.

CGC will automatically link cross-repository calls if the module names match the import statements, providing a truly global view of your architecture.

---

## 3. Persistent Contexts for MCP

When using MCP, CGC remembers the last used context for each workspace. This ensures that when you restart your IDE, your AI assistant is automatically connected to the correct code graph for the project you are working on.

### Manual Override in MCP
If you need to force the AI to look at a different context, you can tell it:
> "Switch to the code graph context at `/path/to/other/repo`"

The AI will use the `switch_context` tool to update the server's state.

---

## Managing Many Indexes

To see all repositories currently indexed in your system:

```bash
cgc stats --all
```

To remove an index for a project you are no longer working on:

```bash
cgc delete-repo /path/to/old/project
```
