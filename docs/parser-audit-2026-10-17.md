# Parser audit — 17 October 2026

Installed and audited CodeGraphContext 0.6.13 at baseline `1b595a61663d60862ac20aca2422ea187671c01c`. The audit produced **24 consolidated issues and 24 independent fix PRs**: one tracker per affected language, with TypeScript and TSX grouped together, plus individual Gradle, Maven and MyBatis trackers.

Environment: Python 3.12.14, tree-sitter 0.25.2, tree-sitter-language-pack 1.20.0. All 27 registered grammars were loaded and exercised.

## Coverage

- Registry equality assertion checks every supported TreeSitterParser entry.
- **205 explicit semantic fixtures**, exercising declarations, nested ownership, parameters, imports/aliases, destructuring, generic and higher-order calls, abstract/protocol declarations, and negative controls as applicable to each parser.
- Each fixture runs as LF, CRLF, Unicode comment padding, dependency/source mode, and normal parsing again after state reuse.
- One declaration pre-scan consistency execution per fixture. HTML/CSS do not have this declaration contract; HCL's no-op pre-scan is intentional, so these three are exempt from the symbol-equality assertion.
- Empty, whitespace-only, comments-only and malformed input for every registry entry.
- Repeated calls on the same line with different **and identical** arguments, plus nested argument boundaries, across all 24 call-capable entries.
- **29 build/mapper fixtures** cover static Gradle notation and negative controls, Maven properties/reactor identity, and MyBatis dynamic SQL/include expansion and phantom-table controls.

This yields **1,338 language/input/state/pre-scan executions**, plus 29 build/mapper cases. These counts include input variants and do not represent 1,367 distinct syntax constructs. Expectations are written independently; parser output is retained as evidence rather than copied into the semantic oracle.

## Results and fix index

Every row below passed its audit checks on the combined proposed fixes. Each affected group also has focused regression tests in its own PR.

| Parser | Audit executions | Consolidated issue | Fix PR |
|---|---:|---|---|
| Python | 58 | [#1783](https://github.com/CodeGraphContext/CodeGraphContext/issues/1783) | [#1808](https://github.com/CodeGraphContext/CodeGraphContext/pull/1808) |
| JavaScript | 64 | [#1784](https://github.com/CodeGraphContext/CodeGraphContext/issues/1784) | [#1809](https://github.com/CodeGraphContext/CodeGraphContext/pull/1809) |
| TypeScript / TSX | 164 | [#1785](https://github.com/CodeGraphContext/CodeGraphContext/issues/1785) | [#1810](https://github.com/CodeGraphContext/CodeGraphContext/pull/1810) |
| Go | 52 | [#1786](https://github.com/CodeGraphContext/CodeGraphContext/issues/1786) | [#1823](https://github.com/CodeGraphContext/CodeGraphContext/pull/1823) |
| Rust | 52 | [#1787](https://github.com/CodeGraphContext/CodeGraphContext/issues/1787) | [#1813](https://github.com/CodeGraphContext/CodeGraphContext/pull/1813) |
| C++ | 64 | [#1788](https://github.com/CodeGraphContext/CodeGraphContext/issues/1788) | [#1814](https://github.com/CodeGraphContext/CodeGraphContext/pull/1814) |
| Java | 58 | [#1789](https://github.com/CodeGraphContext/CodeGraphContext/issues/1789) | [#1811](https://github.com/CodeGraphContext/CodeGraphContext/pull/1811) |
| C# | 52 | [#1790](https://github.com/CodeGraphContext/CodeGraphContext/issues/1790) | [#1812](https://github.com/CodeGraphContext/CodeGraphContext/pull/1812) |
| Ruby | 46 | [#1791](https://github.com/CodeGraphContext/CodeGraphContext/issues/1791) | [#1824](https://github.com/CodeGraphContext/CodeGraphContext/pull/1824) |
| PHP | 52 | [#1792](https://github.com/CodeGraphContext/CodeGraphContext/issues/1792) | [#1821](https://github.com/CodeGraphContext/CodeGraphContext/pull/1821) |
| Kotlin | 52 | [#1793](https://github.com/CodeGraphContext/CodeGraphContext/issues/1793) | [#1817](https://github.com/CodeGraphContext/CodeGraphContext/pull/1817) |
| Scala | 46 | [#1794](https://github.com/CodeGraphContext/CodeGraphContext/issues/1794) | [#1822](https://github.com/CodeGraphContext/CodeGraphContext/pull/1822) |
| Swift | 46 | [#1795](https://github.com/CodeGraphContext/CodeGraphContext/issues/1795) | [#1818](https://github.com/CodeGraphContext/CodeGraphContext/pull/1818) |
| Haskell | 46 | [#1796](https://github.com/CodeGraphContext/CodeGraphContext/issues/1796) | [#1819](https://github.com/CodeGraphContext/CodeGraphContext/pull/1819) |
| Dart | 46 | [#1797](https://github.com/CodeGraphContext/CodeGraphContext/issues/1797) | [#1815](https://github.com/CodeGraphContext/CodeGraphContext/pull/1815) |
| Elixir | 46 | [#1798](https://github.com/CodeGraphContext/CodeGraphContext/issues/1798) | [#1820](https://github.com/CodeGraphContext/CodeGraphContext/pull/1820) |
| Emacs Lisp | 40 | [#1799](https://github.com/CodeGraphContext/CodeGraphContext/issues/1799) | [#1816](https://github.com/CodeGraphContext/CodeGraphContext/pull/1816) |
| HTML | 28 | [#1800](https://github.com/CodeGraphContext/CodeGraphContext/issues/1800) | [#1807](https://github.com/CodeGraphContext/CodeGraphContext/pull/1807) |
| CSS | 28 | [#1801](https://github.com/CodeGraphContext/CodeGraphContext/issues/1801) | [#1806](https://github.com/CodeGraphContext/CodeGraphContext/pull/1806) |
| Gradle | 11 | [#1802](https://github.com/CodeGraphContext/CodeGraphContext/issues/1802) | [#1825](https://github.com/CodeGraphContext/CodeGraphContext/pull/1825) |
| Maven | 9 | [#1803](https://github.com/CodeGraphContext/CodeGraphContext/issues/1803) | [#1826](https://github.com/CodeGraphContext/CodeGraphContext/pull/1826) |
| MyBatis | 9 | [#1804](https://github.com/CodeGraphContext/CodeGraphContext/issues/1804) | [#1827](https://github.com/CodeGraphContext/CodeGraphContext/pull/1827) |
| Perl | 46 | [#1828](https://github.com/CodeGraphContext/CodeGraphContext/issues/1828) | [#1830](https://github.com/CodeGraphContext/CodeGraphContext/pull/1830) |
| Solidity | 46 | [#1829](https://github.com/CodeGraphContext/CodeGraphContext/issues/1829) | [#1831](https://github.com/CodeGraphContext/CodeGraphContext/pull/1831) |
| C | 46 | No confirmed new defect in this matrix | — |
| Lua | 46 | No confirmed new defect in this matrix | — |
| Vue | 46 | No confirmed new defect in this matrix | — |
| Svelte | 46 | No confirmed new defect in this matrix | — |
| HCL | 22 | No confirmed new defect in this matrix | — |

The issues retain valid-source reproducers, expected/actual results, and acceptance criteria. C# records were already available in the dedicated records bucket; the C# finding concerns local-function ownership.

## Validation

- Existing baseline parser/language/call-resolution suite: **384 passed before fixes**.
- Final combined unit and integration run, excluding the separately validated parser golden module: **2,608 passed, 8 skipped**.
- Final semantic language audit: **1,338 passed, zero failures**.
- Final Gradle/Maven/MyBatis audit: **29 passed, zero failures**.
- **All 24 independent main-based fix checkouts passed** their focused tests. The 23 branches with existing sample-project graph fixtures also passed their native indexing/export golden check. This includes duplicate use of a shared project for build extractors and HTML/CSS, rather than 23 distinct language fixtures.
- Additional unchanged C, Lua and HCL graph fixtures: **3 passed**. Vue/Svelte are exercised by the semantic matrix and existing mixed-project graph fixture.
- A native Solidity FalkorDB indexing/export smoke test, for which this baseline has no language golden fixture, retained both same-line helper call edges with distinct argument lists and the nested inner call.
- Nine graph snapshots were refreshed only after reviewing the semantic changes: JavaScript, TypeScript, Rust, C++, Dart, Swift, Elixir, Scala and Go. Changes cover newly extracted declarations, corrected owner identities/parameter names and corresponding structural edges. Added default occurrence_index=0 fields are serialization defaults.
- Ruff passed for both audit scripts and every new focused audit test file. The source diff passed whitespace checks.

The existing golden harness excludes CALLS/HEURISTIC_CALLS edges. It validates graph nodes, common properties and structural edges; explicit parser/call-resolution regressions and the Solidity native smoke cover the reported call behavior separately.

The broad test run initially encountered three MCP transport failures due to missing SOCKS support in the test environment. Installing socksio and using localhost proxy bypass resolved those failures; they were not filed as parser defects. The grammar cache download restriction was also treated as an environment issue.

Latest GitHub CI revisions were queued when checked. Local success above is not a claim that every hosted workflow has completed.

## Reproduce

Install a checkout with this audit PR and the relevant fix PR(s) applied:

```bash
python -m pip install -e '.[dev,parsing]'
python scripts/audit_language_parsers.py --output parser-audit.json
python scripts/audit_build_parsers.py
python -m pytest tests/unit/parsers tests/unit/languages \
  tests/unit/tools/test_cross_lang_call_resolution_patterns.py \
  tests/unit/tools/test_python_call_resolution_patterns.py -q
python -m pytest tests/unit tests/integration -q \
  --ignore=tests/integration/test_parser_goldens.py
```

The audit scripts exit nonzero when semantic expectations fail. Language JSON retains source, checks, actual records, dependency flags, versions, grammar recovery flags and exceptions. Use `--language <registry-name>` to narrow the language audit. Build/mapper JSON retains file inputs and expected/actual dependencies or tables.

The audit branch itself contains the harness and report, not all 24 fixes. Its standalone investigative workflow retains failing evidence with continue-on-error while the fix PRs remain unmerged; the existing regression step remains gating. Each fix PR provides its exact focused test command and closes its corresponding consolidated issue.

## Scope limits

This is a systematic test matrix, not a proof of complete language-specification coverage or perfect static runtime dispatch. It targets the supported parser/extractor contracts and reported graph behavior using the installed grammar version. The eight skipped tests in the broader suite remain skipped; hosted macOS, external database/service and full CI-matrix completion are not established by the local counts. Gradle/Maven/MyBatis extraction remains static analysis rather than execution of build scripts or dynamic SQL against a database.

All confirmed findings from this audit have a proposed fix and regression coverage. The PRs are open for review and have not been merged.

