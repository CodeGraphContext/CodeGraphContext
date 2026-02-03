# 🧪 CodeGraphContext Testing Strategy

This document serves as the single source of truth for testing **CodeGraphContext**. It consolidates usage instructions, architectural philosophy, and future roadmap items.

---

## 🚀 Quick Start: Running Tests

We provide a helper script `tests/run_tests.sh` to simplify test execution.

| Suite | Command | Use Case |
| :--- | :--- | :--- |
| **All Tests** | `./tests/run_tests.sh all` | Full CI/CD verification (includes E2E). |
| **Fast Tests** | `./tests/run_tests.sh fast` | **Recommended for local dev.** Runs Unit + Integration. |
| **Unit Tests** | `./tests/run_tests.sh unit` | Focus on individual components (parsers, database logic). |
| **User Journeys** | `./tests/run_tests.sh e2e` | Validate full end-to-end user workflows. |

---

## 🏗️ Test Architecture

The test suite follows the **Testing Pyramid** principle, ensuring a balanced mix of speed and confidence.

### 1. `tests/unit/` (Bottom Layer)
*   **Speed:** Very Fast (< 100ms)
*   **Scope:** Isolated classes and functions.
*   **Mocking:** Heavy mocking of external dependencies (Neo4j, FileSystem).
*   **Content:**
    *   `core/`: `DatabaseManager`, `JobManager`, `FileWatcher`.
    *   `parsers/`: Output verification for `TreeSitterParser` (Python, JS, etc.).
    *   `tools/`: `GraphBuilder` logic, `CodeFinder` query generation.

### 2. `tests/integration/` (Middle Layer)
*   **Speed:** Fast (~1s)
*   **Scope:** Interaction between 2+ components.
*   **Mocking:** Partial (e.g., mock the database connection but run the real `GraphBuilder` logic).
*   **Content:**
    *   `cli/`: Typer command execution, argument parsing, error handling.
    *   `mcp/`: Server routing, tool call validation, JSON protocol adherence.

### 3. `tests/e2e/` (Top Layer)
*   **Speed:** Slow (> 10s)
*   **Scope:** Full system as seen by the user.
*   **Mocking:** Minimal/None (uses real file interactions, simulated sub-processes).
*   **Content:**
    *   `test_user_journeys.py`: "User initializes repo", "User queries function callers", "User exports bundle".

### 4. `tests/perf/` (Side Quest)
*   **Scope:** Benchmarks for large codebase indexing and complex query latency.

---

## ✅ What We Test

### 1. User Workflows & Journeys
We simulate real-world usage to ensure the product solves user problems.
*   **First-time Setup:** Initialization -> Indexing -> Verifying output.
*   **Daily Dev:** Watching for file changes -> Auto-updating graph.
*   **Code Search:** Finding functions by name, argument, or decorator.

### 2. CLI Functionality
Every command in `cgc --help` is tested.
*   `index`: Argument validation, force flags.
*   `find/analyze`: Query construction and output formatting.
*   `mcp`: Server startup and tool exposure.

### 3. Language Support (Parsers)
We verify that our Tree-sitter parsers correctly extract:
*   **Structure:** Classes, Functions, Modules.
*   **Relationships:** Calls, Inheritance, Imports, Dependencies.
*   **Languages Covered:** Python, JavaScript/TypeScript, Java, C++, Go, Rust, Ruby, PHP, and more.

---

## 🛠️ How to Add Tests

### Adding a New Language Parser
1.  Create `tests/unit/parsers/test_<lang>_parser.py`.
2.  Use the `get_tree_sitter_manager()` singleton.
3.  Feed it a sample code string.
4.  Assert the structure of the returned definition dict.

### Adding a New CLI Command
1.  Create/Edit `tests/integration/cli/test_cli_commands.py`.
2.  Mock the underlying service (e.g., `GraphBuilder` or `CodeFinder`).
3.  Use `CliRunner` from `typer.testing` to invoke the command.
4.  Assert `result.exit_code == 0` and check `result.stdout`.

### Adding a Regression Test
1.  Identify the bug workflow.
2.  Create a test case in `tests/e2e/test_user_journeys.py` that reproduces it.
3.  Fix the bug and verify the test passes.

---

## 🔮 Future Roadmap (Ideas)

These ideas are consolidated from the legacy `IDEAL_TEST_PLAN.md`.

### 1. Advanced Performance Benchmarks
*   **Idea**: Test indexing on > 100k LoC repositories (e.g., use an archived version of React or Django as a fixture).
*   **Metric**: Indexing time per 1000 lines, Memory usage peak.

### 2. Mutation Testing
*   **Idea**: Use a tool like `mutmut` to introduce random bugs in the code and verify the test suite catches them.

### 3. Snapshot Testing for Parsers
*   **Idea**: Instead of asserting specific keys, verify the entire JSON output of a parser against a stored "snapshot". This makes updating parser tests much faster when schema changes.

### 4. Testcontainers Integration
*   **Idea**: In E2E tests, spin up a real Docker container for Neo4j/FalkorDB to guarantee 100% accurate database behavior, removing all mocks.

### 5. Multi-Repo Analysis Workflows
*   **Idea**: E2E tests simulating a user querying calls *across* two different repositories (microservices scenario).
