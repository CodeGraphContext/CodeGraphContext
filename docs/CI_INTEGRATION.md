# CI Integration

`cgc analyze complexity` can act as a quality gate in CI (#1333): it has
machine-readable output on a clean stdout and an opt-in non-zero exit code.

## GitHub Actions example

```yaml
- name: Enforce complexity threshold
  run: |
    pip install codegraphcontext
    cgc index .
    cgc analyze complexity --threshold 10 --format json --fail-on-violations \
      | tee complexity-report.json
  # --fail-on-violations exits 1 when any function exceeds the threshold → PR blocked

- name: Upload complexity report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: complexity-report
    path: complexity-report.json
```

## Output formats

`--format json` (schema):

```json
{
  "threshold": 10,
  "violations_count": 1,
  "violations": [
    {"function": "process_order", "file": "src/orders.py", "line": 45,
     "complexity": 23, "exceeds_by": 13}
  ]
}
```

`--format csv` emits `function,file,line,complexity,exceeds_by` rows
(violations only), suitable for spreadsheets and dashboards.

Notes:

- Progress/status chatter goes to **stderr**; stdout carries only the document,
  so `cgc analyze complexity --format json | jq .` works.
- In `json`/`csv` (or with `--fail-on-violations`), the full violation set is
  reported — the interactive display page size (`--limit`) does not truncate it.
- Without `--fail-on-violations` the exit code stays 0, so exploratory use and
  existing scripts are unaffected.
- The synthetic `<module>` frame is excluded — it attributes module-level
  calls and is not a function anyone can refactor.
