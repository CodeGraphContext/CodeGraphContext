# Project Roadmap

CodeGraphContext is developed to continuously expand static code analysis depth, enhance AI agent contextual routing, and improve parser speeds.

---

## Current Milestones

The following capabilities are supported in the active release:
- **Polyglot Parser Suite**: Syntactic support for 19 target languages.
- **Pluggable Storage Drivers**: Operations across FalkorDB (Default), KuzuDB, LadybugDB, and Neo4j.
- **Model Context Protocol (MCP)**: Implements 25 JSON-RPC tools for LLM agent integration.
- **Directory Watchers**: watchdog-based monitors for incremental synchronization.
- **Graph Serialization**: Exporting/importing database contexts as portable `.cgc` bundles.
- **Exploratory Visualizer**: Local server hosting React-based force-directed query rendering.

---

## Short-Term Pipeline (Short Term)

- **AST Metric Enhancements**: Computing additional code metrics (e.g., maintainability indices, cognitive complexity).
- **SCIP Parser Consolidation**: Optimizing SCIP metadata resolution for large compile-time workspaces.
- **Ingestion Concurrency**: Performance tuning thread workloads for workspaces exceeding 1 Million LOC.

---

## Long-Term Vision (Long Term)

- **CI/CD Integration Packages**: Pre-built Github Actions and GitLab CI stages to compile and publish code bundles on commit tags.
- **Remote Registry Expansion**: Adding auto-indexed bundles for common library dependencies across Python, Javascript, and Go.
- **Alternative MCP Transports**: Server Sent Events (SSE) and WebSocket transports to host CGC servers in cloud microservices.
- **Agentic Refactoring Pipelines**: Custom graph traversals allowing agent chains to write refactored code updates back to disk safely.
