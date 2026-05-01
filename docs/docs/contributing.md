# Contributing to CodeGraphContext

Thank you for your interest in contributing to CodeGraphContext (CGC). We welcome contributions from the community to help make CGC the most powerful code intelligence engine available.

## Development Principles

*   **Consistency**: Adhere to the existing code style (PEP 8 for Python).
*   **Quality**: Write clean, maintainable, and well-documented code.
*   **Testing**: Every new feature or bug fix must include corresponding tests.
*   **Focus**: Keep pull requests focused on a single logical change.

## Setting Up for Development

1.  **Fork and Clone**:
    ```bash
    git clone https://github.com/YOUR_USERNAME/CodeGraphContext.git
    cd CodeGraphContext
    ```
2.  **Environment Setup**:
    We recommend using a virtual environment and `pip`:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux/macOS
    pip install -e ".[dev]"
    ```

## Development Workflow

### 1. Enable Debug Logging
For detailed insights during development, use the `CGC_LOG_LEVEL` environment variable:

```bash
export CGC_LOG_LEVEL=DEBUG
cgc index
```

### 2. Running the Test Suite
We use `pytest` for testing. Ensure all tests pass before submitting a pull request.

```bash
# Run all tests
pytest

# Run tests for a specific module
pytest tests/test_core.py

# Skip re-indexing for faster iterations
CGC_SKIP_REINDEX=true pytest
```

### 3. Linting and Formatting
Please run `ruff` (if available) or similar tools to ensure code quality.

---

## Submitting a Pull Request

1.  **Create a Branch**: Use a descriptive name like `feat/new-backend` or `fix/mcp-timeout`.
2.  **Commit**: Use clear, concise commit messages.
3.  **Submit**: Open a pull request against the `main` branch. Provide a detailed description of your changes and link any relevant issues.

## Reporting Issues

If you find a bug or have a feature request, please open an issue on the [GitHub repository](https://github.com/CodeGraphContext/CodeGraphContext/issues). Include detailed steps to reproduce bugs and provide environment information (OS, Python version, CGC version).
