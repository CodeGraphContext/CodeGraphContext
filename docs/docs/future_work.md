# Ongoing Concerns and Future Work

This page outlines some of the current limitations of CodeGraphContext and areas for future development.

## Semantic Search

The tool is smart enough to find and analyze a function through millions of code files, but the tool is not yet smart enough to understand that a user searching for “calculate_sum” is also intending to look at the “calculate_addition” function. This level of semantic similarity needs to be researched, developed, tested and eventually implemented by our tool.

## Backend abstraction protocol

Today, multiple graph engines are supported, but query and write paths should converge on a **clear backend abstraction**. A natural next step is to extract a **`GraphQueryInterface`** (and closely related write/schema contracts) so tools, indexing, and MCP handlers depend on protocols rather than engine-specific details. That reduces duplication, makes new backends cheaper to add, and centralizes behavior such as pagination, timeouts, and error normalization.

## Advanced language query toolkits

**Sixteen** language-specific query stubs exist for richer per-language tooling; they need **full implementations**: tree-sitter queries, node/relationship mapping aligned with the canonical relationship set (`CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS`, `HAS_PARAMETER`, `INCLUDES`, `IMPLEMENTS`), tests against sample projects, and documentation so MCP tools expose consistent capabilities across languages.

## Streaming for large results

Graph and text results can grow large for big repositories. **Streaming responses** (chunked result sets, cursor-based iteration, or progressive JSON) would keep memory bounded and improve responsiveness for clients that list symbols, dump neighborhoods, or run broad traversals. This ties into both the abstraction layer above and MCP message size limits.

## SSE/HTTP MCP transport for multi-client

The primary transport today is **stdio JSON-RPC** for a single host process. **Server-Sent Events (SSE) and/or HTTP**-based MCP transports would allow multiple clients, easier debugging with standard tools, and deployment behind reverse proxies—without replacing stdio for embedded editor use cases.

## Bundle schema versioning for forward compatibility

**Bundles**, the **registry**, and shared **contexts** benefit from explicit **schema versioning** on serialized graph bundles and metadata. Version fields, migration hooks, and compatibility guarantees would let older clients degrade gracefully and newer releases evolve storage without breaking existing user data.
