# Contributing to CodeGraphContext

We welcome contributions! Please follow these steps:

## General Guidelines

*   Ensure your code adheres to the existing style and conventions of the project.
*   Write clear, concise, and well-documented code.
*   All new features or bug fixes should be accompanied by appropriate tests.
*   Keep your pull requests focused on a single feature or bug fix.

## Setting up Your Development Environment

1.  Fork the repository.
2.  Set up your development environment: `pip install -e ".[dev]"`
3.  Create a new branch for your feature or bugfix (e.g., `git checkout -b feature/my-new-feature`).

## Debugging

To enable debug mode for detailed logging, locate the `debug_mode` variable in `src/codegraphcontext/tools/graph_builder.py` and set its value to `1`.

```python
# src/codegraphcontext/tools/graph_builder.py
debug_mode = 1
```

## Running Tests

Please refer to [TESTING.md](TESTING.md) for detailed instructions on running the test suite, adding new tests, and understanding the test architecture.

Quick summary:
```bash
./tests/run_tests.sh fast   # Run unit + integration tests
```

## Submitting Changes

1.  Write your code and add corresponding tests in the `tests/` directory.
2.  Ensure `fast` tests pass locally (`./tests/run_tests.sh fast`).
3.  Commit your changes with a descriptive commit message.
4.  Submit a pull request to the `main` branch.


<!-- "Failed to check job status: 'JobManager' object has no attribute 'JobStatus'" -->