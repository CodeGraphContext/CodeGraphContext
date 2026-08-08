# CGC Call Graph Audit Report

**Generated:** 2026-06-11 13:14 UTC
**CGC environment:** {
  "python": "3.12.3 (main, Mar 23 2026, 19:04:32) [GCC 13.3.0]",
  "projects": 21,
  "cgc_version": "local"
}

## Executive Summary

- **Languages audited:** 21 (FAILURE) / 20 (PROGRESS; elisp skipped)
- **Average FAILURE node accuracy:** 99.9%
- **Average FAILURE edge accuracy:** 99.8%
- **Average FAILURE CALLS accuracy:** 98.3%

### Per-Language Scorecard

| Language | FAILURE node% | FAILURE edge% | FAILURE CALLS% | PROGRESS match HAVE? | Net progress |
|----------|--------------|--------------|----------------|---------------------|--------------|
| sample_project_dart | 100.0% | 98.5% | 80.0% | No | 1 |
| sample_project_c | 97.2% | 99.2% | 90.0% | No | 47 |
| sample_project_php | 100.0% | 99.9% | 96.8% | Yes | 0 |
| sample_project | 100.0% | 99.8% | 98.4% | No | 76 |
| sample_project_rust | 100.0% | 99.9% | 99.0% | No | 10 |
| sample_project_cpp | 100.0% | 100.0% | 100.0% | Yes | 0 |
| sample_project_csharp | 100.0% | 100.0% | 100.0% | No | 1 |
| sample_project_elisp | 100.0% | 100.0% | 100.0% | N/A (no baseline) | — |
| sample_project_elixir | 100.0% | 98.9% | 100.0% | No | 1 |
| sample_project_go | 100.0% | 99.9% | 100.0% | No | 32 |
| sample_project_haskell | 100.0% | 100.0% | 100.0% | No | 3 |
| sample_project_java | 100.0% | 100.0% | 100.0% | No | -1 |
| sample_project_javascript | 100.0% | 100.0% | 100.0% | Yes | 0 |
| sample_project_kotlin | 100.0% | 100.0% | 100.0% | No | 2 |
| sample_project_lua | 100.0% | 100.0% | 100.0% | No | 4 |
| sample_project_misc | 100.0% | 100.0% | 100.0% | Yes | 0 |
| sample_project_perl | 100.0% | 100.0% | 100.0% | No | 1 |
| sample_project_ruby | 100.0% | 100.0% | 100.0% | No | 2 |
| sample_project_scala | 100.0% | 100.0% | 100.0% | Yes | 0 |
| sample_project_swift | 100.0% | 100.0% | 100.0% | No | -5 |
| sample_project_typescript | 100.0% | 100.0% | 100.0% | No | 7 |

## Goal 2 — Golden Self-Consistency Fixes

### sample_project
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_c
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_cpp
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_csharp
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_dart
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_elisp
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_elixir
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_go
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_haskell
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_java
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_javascript
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_kotlin
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_lua
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_misc
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_perl
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_php
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_ruby
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_rust
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_scala
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_swift
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0

### sample_project_typescript
- Removed contaminated nodes: 0
- Removed contaminated/dangling edges: 0


# FAILURE — Current vs Expected Golden (21 languages)

## sample_project
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 99.8% (1 missing, 0 spurious)
- CALLS accuracy: 98.4% (1 missing)
  - MISSING_EDGE: Function:calls:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project/advanced_calls.py:ln_3 --[CALLS]--> Function:square:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project/advanced_calls.py:ln_1
  - MISSING_CALLS: Function:calls:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project/advanced_calls.py:ln_3 --[CALLS]--> Function:square:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project/advanced_calls.py:ln_1

## sample_project_c
- Node accuracy: 97.2% (3 missing, 0 spurious)
- Edge accuracy: 99.2% (1 missing, 0 spurious)
- CALLS accuracy: 90.0% (1 missing)
  - MISSING_NODE: Function:handle_error:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_c/tough_macros.c:ln_15
  - MISSING_NODE: Function:handle_input:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_c/tough_macros.c:ln_13
  - MISSING_NODE: Function:handle_output:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_c/tough_macros.c:ln_14
  - MISSING_EDGE: Function:process_entity:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_c/utils.c:ln_4 --[CALLS]--> Function:my_callback:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_c/main.c:ln_5
  - MISSING_CALLS: Function:process_entity:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_c/utils.c:ln_4 --[CALLS]--> Function:my_callback:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_c/main.c:ln_5

## sample_project_cpp
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_csharp
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_dart
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 98.5% (1 missing, 0 spurious)
- CALLS accuracy: 80.0% (1 missing)
  - MISSING_EDGE: Function:main:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_dart/lib/main.dart:ln_3 --[CALLS]--> Function:performAction:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_dart/lib/models.dart:ln_18:ctx_User
  - MISSING_CALLS: Function:main:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_dart/lib/main.dart:ln_3 --[CALLS]--> Function:performAction:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_dart/lib/models.dart:ln_18:ctx_User

## sample_project_elisp
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_elixir
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 98.9% (1 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)
  - MISSING_EDGE: Module:Tough.Worker:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_elixir/tough_cases.ex:ln_17 --[USES]--> Module:Tough.Cases:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_elixir/tough_cases.ex:ln_1

## sample_project_go
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 99.9% (1 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)
  - MISSING_EDGE: Struct:Extended:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_go/tough_cases.go:ln_59 --[EMBEDS]--> Struct:Base:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_go/tough_cases.go:ln_51

## sample_project_haskell
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_java
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_javascript
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_kotlin
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_lua
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_misc
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_perl
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_php
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 99.9% (1 missing, 0 spurious)
- CALLS accuracy: 96.8% (1 missing)
  - MISSING_EDGE: Function:invokeDynamically:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_php/tough_cases.php:ln_62:ctx_DynamicInvoker --[CALLS]--> Function:targetMethod:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_php/tough_cases.php:ln_58:ctx_DynamicInvoker
  - MISSING_CALLS: Function:invokeDynamically:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_php/tough_cases.php:ln_62:ctx_DynamicInvoker --[CALLS]--> Function:targetMethod:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_php/tough_cases.php:ln_58:ctx_DynamicInvoker

## sample_project_ruby
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_rust
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 99.9% (1 missing, 0 spurious)
- CALLS accuracy: 99.0% (1 missing)
  - MISSING_EDGE: Function:call_both:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_rust/src/tough_cases.rs:ln_32 --[CALLS]--> Function:action:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_rust/src/tough_cases.rs:ln_30
  - MISSING_CALLS: Function:call_both:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_rust/src/tough_cases.rs:ln_32 --[CALLS]--> Function:action:<REPO_ROOT>/tests/fixtures/sample_projects/sample_project_rust/src/tough_cases.rs:ln_30

## sample_project_scala
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_swift
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)

## sample_project_typescript
- Node accuracy: 100.0% (0 missing, 0 spurious)
- Edge accuracy: 100.0% (0 missing, 0 spurious)
- CALLS accuracy: 100.0% (0 missing)


# PROGRESS — Current vs Have Baseline (20 languages)

*`sample_project_elisp` excluded — no `nodes_have` / `edges_have` baseline.*

## sample_project
- Matches HAVE baseline: **No**
- Nodes gained: 35 | lost: 0
- Edges gained: 41 | lost: 0
- Net progress score: 76
  - IMPROVEMENT nodes gained: 35

## sample_project_c
- Matches HAVE baseline: **No**
- Nodes gained: 22 | lost: 0
- Edges gained: 25 | lost: 0
- Net progress score: 47
  - IMPROVEMENT nodes gained: 22

## sample_project_cpp
- Matches HAVE baseline: **Yes**
- Nodes gained: 0 | lost: 0
- Edges gained: 0 | lost: 0
- Net progress score: 0

## sample_project_csharp
- Matches HAVE baseline: **No**
- Nodes gained: 0 | lost: 0
- Edges gained: 1 | lost: 0
- Net progress score: 1

## sample_project_dart
- Matches HAVE baseline: **No**
- Nodes gained: 0 | lost: 0
- Edges gained: 1 | lost: 0
- Net progress score: 1

## sample_project_elixir
- Matches HAVE baseline: **No**
- Nodes gained: 0 | lost: 0
- Edges gained: 1 | lost: 0
- Net progress score: 1

## sample_project_go
- Matches HAVE baseline: **No**
- Nodes gained: 0 | lost: 0
- Edges gained: 32 | lost: 0
- Net progress score: 32

## sample_project_haskell
- Matches HAVE baseline: **No**
- Nodes gained: 0 | lost: 0
- Edges gained: 3 | lost: 0
- Net progress score: 3

## sample_project_java
- Matches HAVE baseline: **No**
- Nodes gained: 0 | lost: 1
- Edges gained: 1 | lost: 1
- Net progress score: -1
  - REGRESSION nodes lost: 1
  - REGRESSION edges lost: 1

## sample_project_javascript
- Matches HAVE baseline: **Yes**
- Nodes gained: 0 | lost: 0
- Edges gained: 0 | lost: 0
- Net progress score: 0

## sample_project_kotlin
- Matches HAVE baseline: **No**
- Nodes gained: 0 | lost: 0
- Edges gained: 2 | lost: 0
- Net progress score: 2

## sample_project_lua
- Matches HAVE baseline: **No**
- Nodes gained: 1 | lost: 0
- Edges gained: 3 | lost: 0
- Net progress score: 4
  - IMPROVEMENT nodes gained: 1

## sample_project_misc
- Matches HAVE baseline: **Yes**
- Nodes gained: 0 | lost: 0
- Edges gained: 0 | lost: 0
- Net progress score: 0

## sample_project_perl
- Matches HAVE baseline: **No**
- Nodes gained: 0 | lost: 0
- Edges gained: 1 | lost: 0
- Net progress score: 1

## sample_project_php
- Matches HAVE baseline: **Yes**
- Nodes gained: 0 | lost: 0
- Edges gained: 0 | lost: 0
- Net progress score: 0

## sample_project_ruby
- Matches HAVE baseline: **No**
- Nodes gained: 1 | lost: 0
- Edges gained: 1 | lost: 0
- Net progress score: 2
  - IMPROVEMENT nodes gained: 1

## sample_project_rust
- Matches HAVE baseline: **No**
- Nodes gained: 5 | lost: 0
- Edges gained: 5 | lost: 0
- Net progress score: 10
  - IMPROVEMENT nodes gained: 5

## sample_project_scala
- Matches HAVE baseline: **Yes**
- Nodes gained: 0 | lost: 0
- Edges gained: 0 | lost: 0
- Net progress score: 0

## sample_project_swift
- Matches HAVE baseline: **No**
- Nodes gained: 4 | lost: 8
- Edges gained: 9 | lost: 10
- Net progress score: -5
  - REGRESSION nodes lost: 8
  - REGRESSION edges lost: 10
  - IMPROVEMENT nodes gained: 4

## sample_project_typescript
- Matches HAVE baseline: **No**
- Nodes gained: 0 | lost: 0
- Edges gained: 7 | lost: 0
- Net progress score: 7


## Methodology

- **FAILURE columns** report *accuracy %* (100% = current graph matches expected golden; lower = parser gaps).
- **PROGRESS** compares current export vs `nodes_have.jsonl`/`edges_have.jsonl` (structural edges only; CALLS excluded).
- **`sample_project_elisp`:** PROGRESS skipped — no `*_have` regression baseline.
- **Golden self-consistency:** Cross-project contamination removed via boundary-safe path matching; dangling edges pruned.
- **Elisp golden:** Created at `tests/fixtures/goldens/sample_project_elisp/` from fresh export.

## Appendix

- **Expected behavior spec:** [CGC_EXPECTED_GRAPH_SPEC.md](CGC_EXPECTED_GRAPH_SPEC.md)
- **Audit harness:** [scripts/call_graph_audit.py](scripts/call_graph_audit.py)
- **Normalization:** Reuses logic from `tests/integration/test_parser_goldens.py`
- **Current exports:** `audit_output/current/<project>/`
