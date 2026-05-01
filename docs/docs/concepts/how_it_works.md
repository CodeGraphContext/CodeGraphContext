# How it works

Understanding the pipeline helps you choose backends, parsers, and how you invoke CGC from the CLI or MCP.

## 1. Parsing

### Tree-sitter (default)

**Tree-sitter** parses source into an AST. CGC ships **19 language parsers** so entities such as functions, classes, and modules are extracted consistently across your polyglot repos.

### SCIP (optional)

**SCIP** indexing is **opt-in**. When enabled, CGC can use SCIP-oriented inputs as an **alternative** (or complementary path, depending on configuration) to pure Tree-sitter extraction—useful when you already have SCIP indexes or want SCIP-aligned symbols.

## 2. Graph construction

The indexer walks parse output (and optional SCIP data) and materializes **nodes** and **relationships** defined by the project’s graph contract (see [The graph model](the_graph.md)).

- **Nodes** — Repository structure, files, and code elements (for example `Function`, `Class`, `Module`, `Parameter`, …).
- **Edges** — Structural and semantic links such as `CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS`, `IMPLEMENTS`, and others.

Cross-file resolution (imports, call targets, inheritance) happens in this stage so the database stores a queryable graph, not isolated per-file trees.

## 3. Storage (four backends)

Nodes and edges are written through the **database abstraction layer** to **one** active backend:

| Backend | Role |
| :------ | :--- |
| **FalkorDB Lite** | Default on **Unix** with **Python 3.12+**; embedded-friendly, minimal ops. |
| **FalkorDB Remote** | Connect to a **remote** FalkorDB instance when the graph should live on a shared server. |
| **KuzuDB** | Embedded **fallback**, especially common on **Windows** when FalkorDB Lite is not the chosen path. |
| **Neo4j** | **Enterprise / production** deployments with Neo4j operations and tooling. |

The same logical schema is targeted for all backends so tools and queries stay portable.

## 4. Querying

### MCP

Your IDE or agent issues **tool calls** (CGC exposes **20 MCP tools**) for graph-backed answers—callers, callees, imports, context bundles, and more—without hand-writing Cypher in the chat.

### CLI

Use graph-oriented CLI commands as named in current releases:

- **`cgc query`** — run Cypher or graph queries through CGC (there is **no** `cgc cypher` command).
- **`cgc find`** — code/symbol discovery-style search (there is **no** `cgc search` command).

Example Cypher shape (actual labels vary by language; see [The graph model](the_graph.md)):

```cypher
MATCH (caller:Function)-[:CALLS]->(callee:Function {name: 'authenticate_user'})
RETURN caller.name, caller.path
```

## 5. Contexts and bundles

CGC’s **contexts** system packages graph slices and metadata for AI consumption. The **bundle registry** is **shipped** with the product so reusable or shared context bundles integrate cleanly with indexing and MCP workflows.

---

In short: **parse** (Tree-sitter by default, SCIP optional) → **build graph** → **persist** (FalkorDB Lite, FalkorDB Remote, KuzuDB, or Neo4j) → **serve** via MCP tools and the `cgc` CLI.
