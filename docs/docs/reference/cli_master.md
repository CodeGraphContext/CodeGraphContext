# Comprehensive CLI Reference

This page lists **every single command** available in CodeGraphContext.

## Indexing & Management

| Command | Description | Full Details |
| :--- | :--- | :--- |
| **`cgc index`** | Adds a directory to the code graph. | [details](cli_indexing.md#cgc-index) |
| **`cgc list`** | Lists all indexed repositories. | [details](cli_indexing.md#cgc-list) |
| **`cgc delete`** | Removes a repository from the graph. | [details](cli_indexing.md#cgc-delete) |
| **`cgc watch`** | Monitors a directory for real-time updates. | [details](cli_indexing.md#cgc-watch) |
| **`cgc clean`** | Removes orphaned nodes from the DB. | - |
| **`cgc stats`** | Show node count statistics. | - |

## Code Analysis

| Command | Description | Full Details |
| :--- | :--- | :--- |
| **`cgc analyze callers`** | Show what functions call X. | [details](cli_analysis.md#analyze-callers) |
| **`cgc analyze calls`** | Show what functions X calls (callees). | [details](cli_analysis.md#analyze-calls) |
| **`cgc analyze chain`** | Show path between function A and B. | [details](cli_analysis.md#analyze-chain) |
| **`cgc analyze deps`** | Show imports/dependencies for a module. | [details](cli_analysis.md#analyze-deps) |
| **`cgc analyze tree`** | Show class inheritance hierarchy. | [details](cli_analysis.md#analyze-tree) |
| **`cgc analyze complexity`** | Find complex functions (Cyclomatic). | [details](cli_analysis.md#analyze-complexity) |
| **`cgc analyze dead-code`** | Find unused functions. | [details](cli_analysis.md#analyze-dead-code) |
| **`cgc analyze overrides`** | Find method overrides in subclasses. | [details](cli_analysis.md#analyze-overrides) |
| **`cgc analyze variable`** | Find variable usage across files. | [details](cli_analysis.md#analyze-variable) |

## Discovery & Search

| Command | Description | Full Details |
| :--- | :--- | :--- |
| **`cgc find name`** | Find element by exact name. | [details](cli_analysis.md#find-name) |
| **`cgc find pattern`** | Fuzzy search (substring). | [details](cli_analysis.md#find-pattern) |
| **`cgc find type`** | List all Class/Function nodes. | [details](cli_analysis.md#find-type) |
| **`cgc find variable`** | Find variables by name. | [details](cli_analysis.md#analyze-variable) |
| **`cgc find content`** | Full-text search in source code. | [details](cli_analysis.md#find-content) |
| **`cgc find decorator`** | Find functions with `@decorator`. | [details](cli_analysis.md#find-decorator) |
| **`cgc find argument`** | Find functions with specific arg. | [details](cli_analysis.md#find-argument) |

## System & Configuration

| Command | Description | Full Details |
| :--- | :--- | :--- |
| **`cgc doctor`** | Run system health check. | [details](cli_system.md#cgc-doctor) |
| **`cgc mcp setup`** | Configure AI clients. | [details](cli_system.md#cgc-mcp-setup) |
| **`cgc neo4j setup`** | Configure Neo4j database. | [details](cli_system.md#cgc-neo4j-setup) |
| **`cgc config`** | View or modify settings. | [details](configuration.md) |
| **`cgc bundle export`** | Save graph to `.cgc` file. | [details](cli_indexing.md#cgc-bundle-commands) |
| **`cgc bundle load`** | Load graph from file/registry. | [details](cli_indexing.md#cgc-bundle-commands) |
| **`cgc registry`** | Browse cloud bundles. | [details](cli_indexing.md#cgc-registry) |
