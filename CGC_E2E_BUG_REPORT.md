# CGC E2E Bug Report (Re-run — 2026-06-07, session 2)

- **Date:** 2026-06-07 (manual subprocess execution)
- **CGC version:** 0.4.16
- **Install:** editable (`pip install -e .` from repo working tree)
- **Python:** 3.12.3
- **OS:** Linux 6.8
- **Method:** Subprocess-only per [E2E plan](.cursor/plans/cgc_e2e_bug_hunt_6028a5c6.plan.md). Golden files used as reference; pytest run for regression verification after fixes.
- **Harness:** `scripts/e2e_bug_hunt_runner.py` — **28 probes, 0 FAIL, 3 SKIP**

---

## Executive Summary

| Metric | Result |
|--------|--------|
| Embedded backends | FalkorDB Lite, KuzuDB, LadybugDB — **all PASS** |
| Remote backends | falkordb-remote doctor PASS (no host → exit 1); Neo4j/Nornic SKIP |
| Context isolation | **PASS** |
| MCP tools list | **PASS** (25 tools) |
| Exit-code audit | **PASS** (6/6) |
| **New bugs this session** | **2 found → 2 fixed** (BUG-086, BUG-088) |
| Parser goldens | **20/20 PASS** after golden refresh |

**Verdict:** Two correctness bugs fixed (non-deterministic IMPORTS + bundle export edge loss). E2E harness passes cleanly. Full pytest pending completion of this run.

---

## Test Matrix Summary

| Backend | index | chain f1→f3 | find f1 | find content | query write block | bundle export | doctor |
|---------|-------|-------------|---------|--------------|-------------------|---------------|--------|
| **falkordb** | PASS (1.7s) | PASS* | PASS* | PASS | PASS | PASS | PASS |
| **kuzudb** | PASS (20s) | PASS* | PASS* | PASS | PASS | PASS | PASS |
| **ladybugdb** | PASS (14.6s) | PASS* | PASS | PASS | PASS | PASS | PASS |
| **falkordb-remote** | SKIP | — | — | — | — | — | PASS (exit 1 w/o host) |
| **neo4j** | SKIP | — | — | — | — | — | SKIP (no container) |
| **nornic** | SKIP | — | — | — | — | — | SKIP |

\*CLI probes pass; automated JSON parity checks in harness need improvement (Rich output vs JSON).

---

## Bugs Found & Fixed This Session

### BUG-086: Multiple IMPORTS from same file→module collapsed (non-deterministic) — **FIXED**

- **Severity:** High (accuracy / flaky tests)
- **Category:** Accuracy
- **Backend(s):** All (Cypher MERGE in graph writer)
- **Root cause:** `MERGE (f)-[r:IMPORTS]->(m)` without `line_number` in the relationship key meant a file importing the same module twice (e.g. `require('./objects')` + ESM `import … from './objects'`) kept only one edge — whichever row processed last won.
- **Fix:** `MERGE (f)-[r:IMPORTS {line_number: row.line_number}]->(m)` in `graph_builder.py` and `writer.py` (JS/TS and other languages).
- **Verified:** `sample_project_javascript` golden test stable across 5 consecutive runs; DB query shows both line 9 and line 12 edges for `polyglot_module.js`.

### BUG-088: Bundle export dropped duplicate IMPORTS edges — **FIXED**

- **Severity:** Medium (accuracy / golden drift)
- **Category:** Accuracy
- **Backend(s):** All (bundle export)
- **Root cause:** `_extract_edges()` deduplicated by `(from_id, rel_type, to_id)` only, ignoring `line_number` and other edge properties.
- **Fix:** Include serialized relationship properties in `edge_key` in `cgc_bundle.py`.
- **Verified:** Bundle export now includes all IMPORTS edges; 20/20 language goldens refreshed and pass.

---

## Previously Fixed (re-verified this session)

| Area | Status |
|------|--------|
| `cgc doctor` falkordb-remote without `FALKORDB_HOST` | **PASS** exit 1 |
| Context CtxA/CtxB isolation | **PASS** |
| Ghost context rejected | **PASS** |
| MCP Cypher write guard | Not re-probed (prior PASS) |
| Viz path sandbox | Not re-probed (prior PASS) |
| Exit codes (bad config, watch, bundle, registry) | **PASS** |

---

## Skipped Tests

| Item | Reason |
|------|--------|
| Neo4j full matrix | No Docker container / auth on host |
| Nornic | `NORNIC_URI` not set |
| falkordb-remote index | `FALKORDB_HOST` not set on host |
| `cgc watch` live edit loop | Blocking; out of scope |
| `cgc api start` | Not run this pass |

---

## Cross-Backend Parity (sample_project, FalkorDB index)

Golden baseline: **482 nodes / 619 edges** (`tests/fixtures/goldens/sample_project/metadata.json`).

All three embedded backends index successfully with matching CLI behavior for core commands.

---

## 20-Language Golden Sweep

All 20 `sample_project_*` fixtures pass after golden refresh (edge counts increased modestly where multiple IMPORTS per module are now preserved):

| Fixture | Nodes | Edges (post-fix) |
|---------|-------|------------------|
| sample_project | 482 | 619+ |
| sample_project_javascript | 236 | 306 |
| sample_project_typescript | 918 | 1330+ |
| sample_project_rust | 803 | 915+ |
| *(others)* | unchanged nodes | edges +0–6 where multi-import files exist |

Run: `pytest tests/integration/test_parser_goldens.py -q` → **20 passed**.

---

## Test Artifacts

| Path | Contents |
|------|----------|
| `/tmp/cgc-e2e-venv/` | Test venv (editable install) |
| `/tmp/cgc-e2e-results/hunt_state.json` | E2E harness JSON |
| `/tmp/cgc-e2e-results/run.log` | Harness stdout |
| `scripts/e2e_bug_hunt_runner.py` | Repeatable harness |

---

## Recommendations

1. **Publish** 0.4.16+ to PyPI with IMPORTS + bundle export fixes.
2. **Remove dead code:** first `add_file_to_graph` in `graph_builder.py` (lines ~251–520) is overridden by writer delegation — causes confusion.
3. **Enhance harness:** parse Rich CLI output or add `--json` flags for chain/find parity checks.
4. **Re-run** `scripts/e2e_bug_hunt_runner.py` before each release.

---

## Residual Risk

1. MERGE on relationship properties may behave differently on Neo4j vs FalkorDB — needs remote-backend verification.
2. Path-sandbox TOCTOU (symlink race) — not probed.
3. Long-running MCP job memory — not probed.
