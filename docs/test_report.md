# CodeGraphContext v0.3.8 — E2E Test Report (Post-Merge PR #796 UNWIND Batching)

**Date**: 2026-04-05  
**Version**: 0.3.8  
**Test Type**: Full CLI E2E — every command tested manually  
**Sample Repos**: `sample_project` (Python), `sample_project_c` (C), `sample_project_cpp` (C++)  
**Methodology**: Fresh venv + clean `~/.codegraphcontext/` per backend

---

## Summary

| Backend   | Index | List | Stats | Find | Analyze | Query | Delete | Clean | Bundle Export | Bundle Import | Watch | Context | Visualize | Config |
|-----------|-------|------|-------|------|---------|-------|--------|-------|---------------|---------------|-------|---------|-----------|--------|
| FalkorDB  | PASS  | PASS | PASS  | PASS | PASS    | PASS  | PASS   | PASS  | PASS          | PASS          | PASS  | PASS    | PASS      | PASS   |
| KuzuDB    | PASS  | PASS | PASS  | PASS | PASS    | PASS  | PASS   | PASS  | PASS          | PASS          | PASS  | PASS    | —         | PASS   |
| Neo4j     | PASS  | PASS | PASS  | PASS | PASS    | PASS  | PASS   | PASS  | PASS          | PASS          | PASS  | PASS    | —         | PASS   |

**Result: 42/42 PASS (0 FAIL, 0 SKIP)**

---

## Bugs Found & Fixed During This Round

The new PR #796 UNWIND-batching graph_builder introduced five KuzuDB-specific
incompatibilities. All were fixed in this session:

### Bug K1: `SET n += row` unsupported in KuzuDB
- **Symptom**: `Parser exception: Invalid input … SET n +=`
- **Root Cause**: KuzuDB does not support the `SET n += map_var` syntax for
  merging UNWIND row properties into a node.
- **Fix**: Extended `database_kuzu.py::_translate_query` (step 1.5a) to detect
  `SET var += unwind_var` and expand it to explicit `SET var.prop = row.prop`
  clauses, filtered by the KuzuDB schema map.

### Bug K2: UNWIND MERGE missing `uid` primary key
- **Symptom**: `Binder exception: Create node n expects primary key uid as input`
- **Root Cause**: The existing uid-injection code only handled `$parameter`
  references in MERGE properties. UNWIND row references (`row.name`) were not
  recognized.
- **Fix**: Added step 1.5b in the translator: pre-computes `uid` values for
  each batch item (from row fields + `$param` values) and injects
  `uid: row.uid` into the MERGE clause.

### Bug K3: `COALESCE(init, called)` — NODE casting error
- **Symptom**: `Casting between NODE and NODE is not implemented`
- **Root Cause**: The CALLS queries used `COALESCE(Function_node, Class_node)`
  to resolve `__init__` constructors. KuzuDB cannot cast between different node
  label types.
- **Fix**: Removed COALESCE-based `__init__` resolution from all six CALLS query
  templates (fn→cls, cls→cls, file→cls). CALLS now target the Class directly.
  This is semantically equivalent and works on all backends.

### Bug K4: UNWIND batch struct type/order inconsistency
- **Symptom**: `Cannot convert Python object to Kuzu value: STRUCT(…) is incompatible with STRUCT(…)`
- **Root Cause**: KuzuDB requires every dict in an UNWIND list-of-maps to have
  identical keys **in the same order** with identical types. Parser output dicts
  vary in key presence, key order, and value types (e.g., `STRING[]` vs `ANY[]`
  for empty lists, `STRING` vs `STRING[]` for `_sanitize_props` JSON fallback).
- **Fix**: Added comprehensive batch normalization in `graph_builder.py`:
  1. Union of all keys across batch items
  2. Dominant-type detection per key (list, str, int, bool)
  3. Type coercion (empty lists → `[""]`, None → typed default, JSON strings → lists)
  4. Sorted key order (`batch[:] = [{k: b[k] for k in sorted_keys} …]`)

### Bug K5: `NOT n:Label` and `ON CREATE/MATCH SET` unsupported
- **Symptom**: Parser errors on `cgc clean` and Ruby module MERGE queries
- **Fix**: Extended the KuzuDB translator:
  - `NOT n:Label` → `NOT label(n) = 'Label'`
  - `ON CREATE SET` / `ON MATCH SET` → `SET` (global, not just UNWIND)

### Bug K6: Bundle import — labels as string, dict IDs, PK-in-SET
- **Symptom**: Three consecutive failures on `cgc bundle import` for KuzuDB
- **Root Cause**: (a) KuzuDB exports `_label` (string) not `_labels` (list),
  (b) KuzuDB internal IDs are dicts (`{table, offset}`) not hashable,
  (c) KuzuDB prohibits SET on primary-key columns, and
  (d) `CREATE (n:Label)` requires PK in KuzuDB.
- **Fix**: Updated `cgc_bundle.py::_import_node_batch`:
  - Handle both `_label`/`_labels` formats
  - Convert dict IDs to tuples for mapping
  - Use `MERGE (n:Label {pk: $val}) SET n += $remaining` (PK excluded from SET)
  - Compute `uid` for composite-key types if missing

### Additional Fixes (all backends)

- **Parameter sanitization**: Added `_sanitize_value` in `KuzuSessionWrapper` to
  recursively convert tuples and sets to lists throughout all query parameters.
- **UNWIND node+relationship split**: Split the UNWIND MERGE-node + MERGE-rel
  query into two separate queries to avoid "Casting between NODE and NODE" in
  KuzuDB. Also benefits query plan simplicity on other backends.
- **`SET n = $props` translation**: Extended the KuzuDB translator to handle
  `SET n = $props` (assignment) in addition to `SET n += $props` (merge).

---

## Indexing Performance

| Backend   | sample_project (Python, 36 files) | sample_project_c (C, 12 files) | sample_project_cpp (C++, 19 files) |
|-----------|-----------------------------------|-------------------------------|-----------------------------------|
| FalkorDB  | 1.28s                             | 0.69s                          | 1.79s                              |
| KuzuDB    | 2.57s                             | 1.38s                          | 2.88s                              |
| Neo4j     | 14.25s (re-index)                 | 1.65s (re-index)               | 10.23s (re-index)                  |

Notes:
- FalkorDB Lite (embedded) is consistently the fastest
- KuzuDB (embedded) is ~2× FalkorDB due to schema strictness overhead
- Neo4j (remote) includes network round-trip per query; larger projects amplify this

---

## Recommendations

1. **KuzuDB UNWIND limitations are significant** — future graph_builder changes
   that use advanced Cypher patterns should always be tested on KuzuDB. The
   translator handles the gap but each new pattern may need new rules.
2. **Bundle import/export format** should be standardized across backends
   (always use `_labels` as a list, always use simple IDs).
3. **Neo4j transaction memory** — large `--clear` operations on big databases
   may hit `dbms.memory.transaction.total.max`. The batched deletion already
   helps but users with large repos should increase this limit.
