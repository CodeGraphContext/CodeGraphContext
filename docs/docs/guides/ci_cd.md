# CI/CD & Advanced Usage

Integrate CodeGraphContext into your automation pipelines.

## CI/CD Pipeline Integration

You can use CGC to block PRs that introduce "Dead Code" or excessive complexity.

**Example GitHub Action:**

```yaml
name: Code Quality
on: [pull_request]
jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install CGC
        run: pip install codegraphcontext
      - name: Index Code
        run: cgc index .
      - name: Check Complexity
        # Fail if any function is complexity > 20
        run: cgc analyze complexity --threshold 20 --fail-on-found
```

## Large Scale Indexing

For repos with > 100,000 LOC:
1.  **Use Neo4j:** FalkorDB may run out of RAM.
2.  **Increase Memory:** `NEO4J_dbms_memory_heap_max_size=4G`.
3.  **Exclude Tests:** Add `tests/` to `.cgcignore`.
