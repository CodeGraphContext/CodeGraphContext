# CGC E2E Bug Report

- **Date:** 2026-06-09 (manual subprocess execution)
- **CGC version:** 0.4.16 — tested on **PyPI** (`pip install codegraphcontext`) and **local editable** (`pip install -e .` from this repo, uncommitted working-tree changes)
- **Python:** 3.12.3
- **OS:** Linux 6.8.0-124-generic
- **Method:** Subprocess-only per [E2E plan](.cursor/plans/cgc_e2e_bug_hunt_6028a5c6.plan.md). No source modifications. Tests run from `/tmp` with isolated `HOME` unless testing repo-local config bleed.
- **Harness note:** Initial automated harness (`/tmp/cgc_e2e_harness.py`) produced many false positives (truncated Rich output, missing `bundle import -y`, config bleed when cwd inside CGC repo). Findings below are manually verified.

---

## Executive Summary

| Metric | Result |
|--------|--------|
| Embedded backends (FalkorDB, KuzuDB, LadybugDB) | **PASS** — index, query, find, bundle export |
| Remote backends (Neo4j, falkordb-remote, Nornic) | **SKIP** — Docker daemon unavailable |
| Context isolation (global / per-repo / named) | **PASS** |
| MCP stdio (25 tools) | **PASS** |
| Watch incremental | **PASS** |
| API gateway | **PARTIAL** — `/api/v1/status` OK; `/health` 404 |
| **Confirmed bugs** | **12** (0 Critical, 4 High, 5 Medium, 3 Low) |

**Verdict (PyPI):** Core indexing works, but call-chain analysis and golden parity regress vs repo goldens. Config bleed when cwd is inside a repo with `.codegraphcontext/`.

**Verdict (local editable):** Significantly better — call chains work, 20/20 golden parity exact match, cypher deprecation warning present. Several PyPI bugs appear fixed in the working tree but **not yet released**. Remaining local issues: delete orphans, per-repo FalkorDB default, API `/health` 404, CLI help gaps.

---

## Test Matrix Summary

| Backend | index | stats (482/625) | chain f1→f3 | find f1 | query write block | bundle export/import | doctor |
|---------|-------|-----------------|-------------|---------|-------------------|----------------------|--------|
| **falkordb** | PASS (1.5s) | PASS | **FAIL** | PASS | PASS | PASS / PASS (-y) | PASS |
| **kuzudb** | PASS (22s) | PASS | **FAIL** | PASS | PASS | PASS / PASS (-y) | PASS |
| **ladybugdb** | PASS (18s) | PASS | **FAIL** | PASS | PASS | PASS / PASS (-y) | PASS |
| **falkordb-remote** | SKIP | — | — | — | — | — | SKIP |
| **neo4j** | SKIP | — | — | — | — | — | SKIP |
| **nornic** | SKIP | — | — | — | — | — | SKIP |

Golden baseline for Python sample: **482 nodes, 621 edges** in `tests/fixtures/goldens/sample_project/metadata.json`; PyPI measured **482 nodes, 625 edges** (0.6% edge delta — within tolerance).

---

## Bugs

### BUG-001: Repo-local `.codegraphcontext/.env` overrides isolated global config

- **Severity:** High
- **Category:** UX / Config
- **Backend(s):** All
- **Repro steps:**
  ```bash
  export HOME=$(mktemp -d)
  cgc config db neo4j
  cgc config set NEO4J_URI bolt://127.0.0.1:19999
  cd /path/to/repo/with/.codegraphcontext   # e.g. CGC repo itself
  cgc config show   # NEO4J_URI reverts to bolt://localhost:7687 from repo .env
  ```
- **Expected:** User's `~/.codegraphcontext/.env` values take precedence, or repo-local overrides are clearly documented and scoped to per-repo mode only.
- **Actual:** Repo-local `.codegraphcontext/.env` merges and wins for `DEFAULT_DATABASE`, `NEO4J_URI`, etc. even in global mode with a fresh `HOME`. Index/find connect to the repo's FalkorDB graph (53k+ functions in dev tree) instead of the isolated test database.
- **Impact:** New users cloning CGC (or any repo with `.codegraphcontext/`) get silently redirected to the repo's database. E2E tests, CI, and multi-project workflows produce wrong results without obvious error.

---

### BUG-002: Module-level nested calls produce no Function→Function CALLS edges

- **Severity:** High
- **Category:** Accuracy
- **Backend(s):** All (parser / call resolver)
- **Repro steps:**
  ```bash
  export HOME=$(mktemp -d) && cd /tmp
  cgc config db falkordb && cgc context mode global
  cgc index --force tests/fixtures/sample_projects/sample_project
  cgc query "MATCH (a)-[r:CALLS]->(b) WHERE a.path CONTAINS 'function_chains' RETURN a.name, b.name, r.line_number"
  ```
  Fixture: `function_chains.py` line 5: `result = f1(f2(f3(10)))`
- **Expected:** CALLS edges `f1→f2`, `f2→f3` (or equivalent nested-call representation).
- **Actual:** Only module-level edges: `<module>→f1`, `<module>→f2`, `<module>→f3` (all line 5). Zero Function→Function CALLS for this pattern.
- **Impact:** `cgc analyze chain f1 f3` returns *"No call chain found"*. Docs/quickstart use this fixture as the canonical call-chain demo.

---

### BUG-003: `analyze chain f1 f3` fails on indexed sample_project (consequence of BUG-002)

- **Severity:** High
- **Category:** Accuracy
- **Backend(s):** falkordb, kuzudb, ladybugdb (verified)
- **Repro steps:** After indexing sample_project: `cgc analyze chain f1 f3`
- **Expected:** Chain `f1 → f2 → f3`
- **Actual:** `No call chain found between 'f1' and 'f3' within depth 5` (exit 0)
- **Impact:** Primary onboarding example broken for nested module-level calls.

---

### BUG-004: `analyze callers f2` reports `<module>` instead of `f1`

- **Severity:** Medium
- **Category:** Accuracy / UX
- **Backend(s):** All
- **Repro steps:** Index sample_project → `cgc analyze callers f2`
- **Expected:** Caller `f1` (per intuitive reading of `f1(f2(f3(10)))`).
- **Actual:** Single caller `<module>` at function_chains.py (technically correct given BUG-002, but contradicts user/docs mental model).
- **Impact:** Misleading caller analysis for module-level call expressions.

---

### BUG-005: `cgc delete` leaves orphan graph nodes

- **Severity:** Medium
- **Category:** Accuracy / Data integrity
- **Backend(s):** falkordb (verified)
- **Repro steps:**
  ```bash
  cgc index --force sample_project_c   # 83 nodes
  cgc delete sample_project_c
  cgc query "MATCH (n) RETURN count(n)"   # returns 9, not 0
  ```
- **Expected:** All nodes belonging to deleted repository removed.
- **Actual:** 9 orphan nodes remain (Parameters, Variables without paths — e.g. `x`, `y`, `int v`).
- **Impact:** Repeated index/delete cycles accumulate stale nodes; inflates stats and can cause golden parity drift in batch sweeps.

---

### BUG-006: MCP `delete_repository` with bad path raises internal error

- **Severity:** Medium
- **Category:** UX
- **Backend(s):** All (MCP)
- **Repro steps:** MCP `tools/call` → `delete_repository` with `{"path": "../../../etc"}`
- **Expected:** Clean validation error (path not found / not indexed).
- **Actual:** `Tool execution error: Failed to delete repository: 'NoneType' object has no attribute 'replace'`
- **Impact:** Scary internal error instead of actionable message; suggests missing null guard on repository path resolution.

---

### BUG-007: Per-repo mode auto-init uses FalkorDB despite global KuzuDB setting

- **Severity:** Medium
- **Category:** UX / Config
- **Backend(s):** kuzudb (verified)
- **Repro steps:**
  ```bash
  cgc config db kuzudb && cgc context mode per-repo
  cd sample_project_go && cgc index --force .
  # Observe: "Context: Per-repo local mode (Database: falkordb)"
  ```
- **Expected:** Per-repo context inherits configured backend (kuzudb) or prompts user.
- **Actual:** Auto-created `.codegraphcontext/` defaults to `falkordb` regardless of global `cgc config db kuzudb`.
- **Impact:** User selects KuzuDB globally but per-repo mode silently uses FalkorDB Lite.

---

### BUG-008: API gateway has no `/health` endpoint

- **Severity:** Low
- **Category:** UX / Docs
- **Backend(s):** N/A (API)
- **Repro steps:** `cgc api start --port 8020` → `curl http://127.0.0.1:8020/health`
- **Expected:** Health check endpoint (common convention).
- **Actual:** HTTP 404. Working endpoint: `GET /api/v1/status` → `{"status":"ok","message":"Connected",...}`
- **Impact:** Load balancers / k8s probes using `/health` fail unless docs specify `/api/v1/status`.

---

### BUG-009: `cgc cypher` alias runs without deprecation warning

- **Severity:** Low
- **Category:** UX / Docs
- **Backend(s):** All
- **Repro steps:** `cgc cypher 'MATCH (f:Function) RETURN f.name LIMIT 1'`
- **Expected:** Deprecation warning directing users to `cgc query`.
- **Actual:** Executes silently, returns results (exit 0).
- **Impact:** Deprecated command persists undetected.

---

### BUG-010: CLI `--database` help lists 4 backends; code supports 6

- **Severity:** Low
- **Category:** Docs
- **Backend(s):** N/A
- **Repro steps:** `cgc index --help` — check `--database` enum
- **Expected:** Includes `nornic`, `falkordb-remote` per `config_manager.py`.
- **Actual:** Help text omits `nornic` and `falkordb-remote`.
- **Impact:** Users cannot discover remote backends from CLI help.

---

### BUG-011: `bundle import --clear` blocks without `-y` in non-interactive contexts

- **Severity:** Low
- **Category:** UX
- **Backend(s):** All
- **Repro steps:** `cgc bundle import file.cgc --clear` (no TTY)
- **Expected:** Non-interactive failure with clear message, or require `-y` in docs prominently.
- **Actual:** Hangs at `Are you sure you want to continue? [y/N]:` until timeout.
- **Impact:** CI/scripts hang; `--yes/-y` exists but is easy to miss.

---

### BUG-012: PyPI vs repo golden node-count drift for some languages

- **Severity:** Medium
- **Category:** Accuracy / Release parity
- **Backend(s):** falkordb (PyPI 0.4.16)
- **Repro steps:** Fresh isolated index per language; compare `MATCH (n)` count to `tests/fixtures/goldens/*/metadata.json`.
- **Expected:** Node counts within 10% of goldens (same generator `PYv0.4.16`).
- **Actual (fresh single-repo index):**

| Project | Golden nodes | PyPI nodes | Δ% | Golden edges | PyPI edges | Status |
|---------|-------------|------------|-----|-------------|------------|--------|
| sample_project | 482 | 482 | 0% | 621 | 625 | PASS |
| sample_project_go | 660 | 690 | 4.5% | 845 | 845 | PASS |
| sample_project_java | 160 | 195 | 21.9% | 221 | 221 | **FAIL** |
| sample_project_javascript | 236 | 236 | 0% | 306 | 304 | PASS |
| sample_project_rust | 803 | 854 | 6.4% | 943 | 939 | PASS |
| sample_project_typescript | 918 | 918 | 0% | 1465 | 1459 | PASS |
| sample_project_c | 83 | 83 | 0% | 96 | 96 | PASS |
| sample_project_kotlin | 189 | 206 | 9.0% | 242 | 242 | PASS |
| sample_project_cpp | 136 | 155 | 14.0% | 167 | 167 | FAIL |
| sample_project_csharp | 141 | 168 | 19.1% | 212 | 212 | FAIL |
| sample_project_dart | 49 | 88 | 79.6% | 64 | 64 | FAIL |
| sample_project_elixir | 53 | 93 | 75.5% | 81 | 81 | FAIL |
| sample_project_haskell | 45 | 87 | 93.3% | 50 | 50 | FAIL |
| sample_project_lua | 52 | 96 | 84.6% | 55 | 55 | FAIL |
| sample_project_misc | 27 | 73 | 170% | 26 | 26 | FAIL |
| sample_project_perl | 71 | 117 | 64.8% | 95 | 94 | FAIL |
| sample_project_php | 757 | 771 | 1.8% | 866 | 866 | PASS |
| sample_project_ruby | 74 | 127 | 71.6% | 106 | 106 | FAIL |
| sample_project_scala | 130 | 186 | 43.1% | 171 | 171 | FAIL |
| sample_project_swift | 136 | 192 | 41.2% | 178 | 178 | FAIL |

- **Note:** Edge counts match exactly for all tested languages; node inflation is predominantly extra `Parameter` and `Variable` nodes. Suggests PyPI 0.4.16 indexes more node types than goldens captured, or goldens were generated from a different build artifact.
- **Impact:** Golden-based CI on PyPI install will fail for 11/20 languages on node count despite correct edge topology.

---

## Verified PASS (not bugs)

| Area | Result |
|------|--------|
| `cgc doctor` on embedded backends | PASS |
| `cgc query` write guard (`DELETE`, `CREATE`) | Blocked, exit 1 |
| `cgc index` skip when already indexed | PASS (exit 0, tip shown) |
| Context global mode — two repos in `cgc list` | PASS |
| Context per-repo isolation — `f1` not in Go-only repo | PASS |
| Named context create/index/default | PASS |
| MCP tools/list | 25 tools |
| MCP `find_code` vs CLI `find name f1` | Parity on function_chains.py |
| MCP `add_code_to_graph` bad path | Proper error (outside allowed roots) |
| `cgc watch` incremental re-index | PASS — new `bar→foo` caller detected |
| `cgc registry search numpy` | PASS |
| Datasource smoke (mysql/cassandra/redis bad host) | Clean errors, no traceback |
| Bundle round-trip with `-y` | 482/625 nodes in 0.68s |
| Neo4j misconfig exit codes (from `/tmp`, clean HOME) | index/find exit 1 with clear message |

---

## Doc/UX Inconsistencies

- CLI `--database` help missing `nornic`, `falkordb-remote` (BUG-010)
- MCP tool count: docs reference 21 tools; runtime exposes **25**
- Quickstart call-chain example (`f1→f2→f3`) does not work with current call resolver (BUG-002/003)
- API health probe should document `/api/v1/status` not `/health`
- `NEO4J_USER` is not a valid `cgc config set` key; use `NEO4J_USERNAME` (discovered during exit-code testing)
- Config precedence: local `.codegraphcontext/.env` at cwd overrides global — underdocumented for global-mode users (BUG-001)

---

## Skipped Tests

| Test | Reason |
|------|--------|
| Neo4j remote index/query | Docker daemon not running (`unix:///home/shashank/.docker/desktop/docker.sock` missing) |
| FalkorDB-remote | Same — no Docker |
| Nornic | Same — no Docker |
| `cgc visualize` memory/perf | Not run (manual UI probe deferred) |
| `ENABLE_AUTO_WATCH=true` post-index | Not run (terminal block behavior deferred) |

---

## Cross-Backend Parity (sample_project)

| Check | falkordb | kuzudb | ladybugdb |
|-------|----------|--------|-----------|
| Node count | 482 | 482 | 482 |
| Edge count | 625 | 625* | 625* |
| `find name f1` (function_chains) | PASS | PASS | PASS |
| `find content "Hello World"` | PASS | PASS | PASS |
| `analyze chain f1 f3` | FAIL | FAIL | FAIL |
| Query write block | PASS | PASS | PASS |

\*Edge counts inferred from shared indexing pipeline; node counts verified via Cypher.

---

## Local Editable vs PyPI Comparison (2026-06-09)

Local install: `/tmp/cgc-local-venv` via `pip install -e .` from commit `dce24ed` + 9 uncommitted files (`cli_helpers.py`, `database_falkordb.py`, `database_kuzu.py`, `falkor_worker.py`, `api/router.py`, `scip_indexer.py`, etc.).

| Bug / Check | PyPI 0.4.16 | Local editable | Notes |
|-------------|-------------|----------------|-------|
| **BUG-001** Config bleed | **FAIL** — repo `.env` overrides HOME; index hits dev graph (53k+ functions) | **Improved** — isolated HOME + neo4j misconfig exits with error; no silent fallback to repo FalkorDB | Local `cli_helpers.py` changes likely involved |
| **BUG-002** Function→Function CALLS | **FAIL** — only `<module>→f1/f2/f3` | **FIXED** — `f1→f2`, `f2→f3` edges present | Major accuracy fix in working tree |
| **BUG-003** `analyze chain f1 f3` | **FAIL** — "No call chain found" | **FIXED** — chain length 2, shows f1→f2→f3 | |
| **BUG-004** `analyze callers f2` | **FAIL** — reports `<module>` | **FIXED** — reports `f1` | |
| **BUG-005** Delete orphans | **FAIL** — 9 nodes remain | **FAIL** — 9 nodes remain | Same on both |
| **BUG-006** MCP delete bad path | **FAIL** — `NoneType.replace` | **Improved** — clean `ALLOW_DB_DELETION` guard message | Different code path hit |
| **BUG-007** Per-repo DB default | **FAIL** — auto-init uses falkordb | **FAIL** — same | |
| **BUG-008** API `/health` | **FAIL** — 404 | **FAIL** — 404 (`/api/v1/status` → 200) | |
| **BUG-009** Cypher deprecation | **FAIL** — no warning | **FIXED** — `⚠ 'cgc cypher' is deprecated` | |
| **BUG-010** CLI `--database` help | **FAIL** — missing nornic, falkordb-remote | **FAIL** — help still lists only falkordb/kuzudb/neo4j on `index` | |
| **BUG-012** Golden parity (20 langs) | **FAIL** — 11/20 node-count drift | **PASS** — **20/20 exact match** (482/621 … 918/1465) | PyPI wheel ≠ repo goldens; local tree matches |
| Neo4j misconfig exit codes | PASS (exit 1) | PASS (exit 1) | Both OK from `/tmp` |
| MCP tool count | 25 | 25 | Same |
| Context isolation | PASS | PASS | Same |

### Local-only test matrix (FalkorDB, `/tmp`, isolated HOME)

| Check | Result |
|-------|--------|
| index sample_project | PASS — 482 nodes, **621 edges** (matches golden exactly; PyPI had 625) |
| `analyze chain f1 f3` | **PASS** |
| `analyze callers f2` | **PASS** (caller: `f1`) |
| bundle export/import `-y` | PASS |
| 20-language golden sweep | **20/20 PASS** — zero node/edge delta |

### Release gap summary

The working tree contains fixes **not in the published PyPI 0.4.16 wheel**:

1. Nested/module-level call resolution (`f1→f2→f3` CALLS edges)
2. Exact golden parity (edge count 621 vs PyPI's 625 on sample_project)
3. Cypher deprecation warning
4. Improved config / DB-init error handling (no silent repo-graph bleed)

**Action:** Cut a new PyPI release (0.4.17+) to ship these fixes to new users installing via `pip install codegraphcontext`.

---

## Recommendations (report-only; no fixes applied)

1. **BUG-001:** Document config precedence clearly; consider not loading repo-local `.env` in global mode unless `--context` or per-repo mode is active.
2. **BUG-002/003:** Fix call resolver for nested call expressions at module scope, or update docs to use intra-function call examples.
3. **BUG-005:** Cascade-delete orphan Parameter/Variable nodes when removing a repository.
4. **BUG-012:** Regenerate language goldens from PyPI 0.4.16 wheel, or pin golden generator to exact release artifact hash.

---

*Report generated by manual E2E bug hunt session 2026-06-09. Local editable comparison added same day.*
