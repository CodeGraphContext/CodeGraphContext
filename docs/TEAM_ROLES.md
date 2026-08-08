# CodeGraphContext Team Boundaries & Issue Routing Guide

This document defines the strict boundaries for assigning GitHub issues, PRs, and Roadmap milestones to our 7 specialized teams. Maintainers must follow these rules to ensure system stability and efficient parallel development.

---

## 🏗️ 1. AdminArchs (Senior Maintainers & Core Architecture)
**The Rule:** If a task introduces risk to the entire system, fundamentally changes how the engine works, or involves production deployment infrastructure, it belongs here. New contributors should **not** be assigned these tasks.
*   **System-Wide Architecture:** Changing database interfaces (e.g., `GraphQueryInterface`), shifting from synchronous to true asynchronous operations, or implementing persistent job states.
*   **Concurrency & Performance:** Parallelized indexing (Worker Pools), connection pooling, and multi-client transport layers (WebSockets/SSE).
*   **DevOps & Deployment:** Docker Compose, Kubernetes Helm charts, and CI/CD pipeline structures (GitHub Actions).
*   **Security:** Production API auth, security audits, and rate limiting.

## 🐍 2. PythonDevs (Core Engine Developers)
**The Rule:** If it involves writing Python code to parse, query, or manage local data—but *doesn't* require a massive architectural rewrite—it belongs here.
*   **CLI & Tools:** Adding new sub-commands to the Typer CLI, refactoring existing `cli/` files into smaller modules.
*   **CodeFinder & Queries:** Writing new Cypher queries to extract data, or refactoring existing query files.
*   **Database Adapters:** Maintaining the existing Neo4j, KuzuDB, and FalkorDB drivers (without changing the fundamental async architecture).
*   **AST Toolkits:** Implementing language-specific AST patterns (e.g., Python decorator resolution, Java annotations).

## 🧠 3. AIDevs (AI & Machine Learning Integration)
**The Rule:** If it involves LLMs, embeddings, or prompt engineering, it goes here.
*   **Local LLMs:** Integrating Ollama or local model inference.
*   **Graph RAG:** Generating vector embeddings, storing them in vector indices, and writing hybrid search pipelines.
*   **Semantic Features:** AI-guided function summarization and natural language querying (`cgc ask`).

## 🌐 4. WebDevs (Frontend & UI/UX)
**The Rule:** If it lives in the browser and uses React, TypeScript, or visualizations, it goes here.
*   **Visualizations:** React-force-graph rendering, WebGL optimizations, D3/Mermaid integration.
*   **UI Components:** Refactoring large `tsx` monoliths into smaller UI components (e.g., glassmorphic modals, sidebars).
*   **Web Interfaces:** The main CodeGraphContext website and the PR Reviewer visual web dashboard.

## 🔌 5. ExtensionDevs (IDE & Browser Integrations)
**The Rule:** If it's a plugin that connects an external IDE or browser to our core engine, it goes here.
*   **VS Code:** CodeLens markers, Webview panels, definition providers, and status bar indicators.
*   **Browser Extensions:** Chrome/Firefox extensions (Manifest V3) for injecting graph contexts into GitHub or web LLMs.

## 📚 6. DocsExperts (Technical Writing & DevRel)
**The Rule:** If it involves communicating how the tool works to the outside world, it goes here.
*   **Documentation:** Auto-generating MkDocs API references, maintaining installation guides.
*   **Content:** Writing technical blog posts (e.g., "Graph RAG for Code") and creating demo videos.
*   **Internationalization:** Translating the README into Spanish, Hindi, Portuguese, etc.

## 🧪 7. Testers (QA & Benchmarking)
**The Rule:** If it involves ensuring the code actually works under stress and across different environments, it goes here.
*   **Benchmarking:** Running the ingestion benchmark suite to track performance regressions (LOC/sec, DB latency).
*   **Parity Checks:** Expanding the DB parity test suite to ensure FalkorDB, Kuzu, and Neo4j return identical results.
*   **Test Suite Health:** Isolating tests, mocking DBs, and removing test flakiness.

---
### ⚠️ Key Exception for Maintainers:
**"Single-file refactors vs. Systemic Shifts"**
If an issue asks to refactor `CodeGraphViewer.tsx` into smaller files, assign it to **WebDevs**. If an issue asks to refactor `cli/main.py` into smaller files, assign it to **PythonDevs**. 
*However*, if an issue asks to "Shift the database ingestion to use parallelized multiprocessing worker queues"—that is a systemic shift and MUST be assigned to **AdminArchs**.
