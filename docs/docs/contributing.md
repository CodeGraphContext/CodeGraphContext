# Contributing to CodeGraphContext

Thank you for your interest in contributing to CodeGraphContext (CGC). We welcome contributions from the community to improve the performance, language support, and tooling capabilities of the engine.

---

## Development Principles

- **Code Quality**: Adhere to PEP 8 standards for Python codebase.
- **Robust Testing**: Every bug fix, driver implementation, or parser extension must be accompanied by unit or integration tests.
- **Focused Commits**: Keep pull requests focused on a single change set.
- **Maintain Documentation**: Update references and guides if code changes alter command arguments or configurations.

---

## Setting Up the Development Workspace

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/CodeGraphContext/CodeGraphContext.git
   cd CodeGraphContext
   ```

2. **Initialize Virtual Environment**:
   Initialize an isolated python environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

---

## Development Workflows

### Debug Logging
Enable verbose debug logs during execution by setting the environment variable:
```bash
export CGC_LOG_LEVEL=DEBUG
cgc index
```

### Running the Test Suite
The testing pipeline utilizes `pytest`. Ensure all checks pass locally before pushing changes:

```bash
# Run all unit and integration tests
pytest

# Test a specific driver module
pytest tests/integration/test_kuzudb.py

# Run tests bypassing re-indexing cache
CGC_SKIP_REINDEX=true pytest
```

*Note: Integration tests for remote databases like Neo4j require a running local database instance (refer to docker-compose.yml).*

### Formatting & Linting
We enforce formatting and static checks via `ruff`. Run linting checks before committing:

```bash
ruff check .
ruff format .
```

---

## Pull Request Guidelines

1. **Feature Branches**: Branch from `main` using descriptive naming (e.g., `feat/ladybug-concurrency` or `fix/mcp-json-rpc`).
2. **Commit Styling**: Write clear, descriptive commit logs.
3. **Submission**: Open a pull request against the `main` branch. Detail the modification, verify unit test runs, and link to open issue tickets if applicable.
