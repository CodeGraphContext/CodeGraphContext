# Architecture Documentation

This document provides a detailed overview of the architecture of the CodeGraphContext project.

## High-Level Overview

The project is a client-server application designed to analyze and visualize codebases. It consists of:

*   **A Python backend:** This is the core of the application, responsible for parsing and analyzing code, building a graph representation of the codebase, and exposing this data through an API.
*   **A web-based frontend:** A user interface for interacting with the backend, visualizing the code graph, and exploring the codebase.
*   **A command-line interface (CLI):** For managing the backend and performing analysis from the terminal.

## Backend Architecture

The backend is a Python application located in the `src/codegraphcontext` directory.

### Core Components

The `src/codegraphcontext/core` directory contains the fundamental building blocks of the backend:

*   **Database:** The code graph is stored in one of **four graph database backends** (Neo4j, FalkorDB, KuzuDB, and related Lite/local options), selected via configuration (for example the `DEFAULT_DATABASE` key). This allows efficient querying of relationships between code elements (e.g., function calls, class inheritance).
*   **Jobs:** Asynchronous jobs are used for long-running tasks like indexing a new codebase. This prevents the application from becoming unresponsive.
*   **Watcher:** A file system watcher monitors the codebase for changes and triggers re-indexing, keeping the code graph up-to-date.

### Tools

The `src/codegraphcontext/tools` directory contains the logic for code analysis:

*   **Graph Builder:** This component is responsible for parsing the code and building the graph representation that is stored in the database.
*   **Code Finder:** Provides functionality to search for specific code elements within the indexed codebase.
*   **Import Extractor:** This tool analyzes the import statements in the code to understand dependencies between modules.

### Server

The `src/codegraphcontext/server.py` file implements the MCP server. It exposes the functionality of the backend to MCP clients via **MCP (JSON-RPC over stdio)**.

### CLI

The `src/codegraphcontext/cli` directory contains the implementation of the command-line interface. It allows users to:

*   Start the MCP server with `cgc mcp start` (and related MCP commands).
*   Index new projects.
*   Run analysis tools from the command line.

The system also supports **bundles**, a **registry**, and **contexts** for organizing indexed projects, sharing graph snapshots, and scoping tools to the right codebase—see project docs for configuration details.

## Frontend Architecture

The frontend is a modern web application located in the `website/` directory.

*   **Framework:** It is built using React and TypeScript.
*   **Build Tool:** Vite is used for fast development and building the application.
*   **Component-Based:** The UI is organized into reusable components, located in `website/src/components`. This includes UI elements like buttons and dialogs, as well as higher-level components for different sections of the application.
*   **Styling:** Tailwind CSS is used for styling the application.

## Testing

The `tests/` directory contains the test suite for the project.

*   **Integration Tests:** `test_cgc_integration.py` contains tests that verify the interaction between different components of the backend.
*   **Unit Tests:** Other files in this directory contain unit tests for specific modules and functions.
*   **Sample Project:** The `tests/sample_project` directory contains a variety of Python files used as input for testing the code analysis tools.
