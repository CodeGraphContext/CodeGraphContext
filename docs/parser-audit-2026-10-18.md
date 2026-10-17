# Parser audit — 18 October 2026

Baseline: `1b595a61663d60862ac20aca2422ea187671c01c`, CodeGraphContext 0.6.13, Python 3.12, tree-sitter 0.25.2, language-pack 1.20.0.

## Coverage and reproduction

- All 27 `TreeSitterParser` registry entries; a registry equality assertion prevents silent omissions when support grows.
- 133 explicit semantic fixtures, each run with LF, CRLF, a Unicode comment prefix, dependency/source mode, and normal parsing again to exercise parser state reuse.
- Empty, whitespace-only, comments-only and malformed input for every entry.
- One pre-scan consistency check per semantic fixture. HCL explicitly has no symbol pre-scan contract; HTML/CSS are also exempt from that check.
- 29 Gradle, Maven and MyBatis fixtures, including negative controls for phantom dependencies/tables.
- 906 language/input/state/pre-scan executions plus 29 build/mapper executions. These are cases, not 935 distinct syntax constructs.
- The existing 384 parser, language and call-resolution tests passed before fixes. A grammar download failure was an environment problem and was not filed as a language defect.

```bash
python -m pip install -e '.[dev,parsing]'
python scripts/audit_language_parsers.py --output parser-audit.json
python scripts/audit_build_parsers.py
python -m pytest tests/unit/parsers tests/unit/languages \
  tests/unit/tools/test_cross_lang_call_resolution_patterns.py \
  tests/unit/tools/test_python_call_resolution_patterns.py -q
```

The audit commands deliberately exit nonzero when expected semantics are missing. JSON contains source, versions, assertions, actual records, grammar recovery flags and exceptions. Do not regenerate expected assertions from parser output. Use focused regression tests in each fix PR; the standalone audit is an investigative tool rather than an all-green CI gate while these issues remain open.

## Findings

One tracker per affected language; TypeScript and its TSX dialect share a tracker. Build/mapper extractors have individual trackers.

| Parser | Consolidated issue |
|---|---|
| python | [#1783](https://github.com/CodeGraphContext/CodeGraphContext/issues/1783) |
| javascript | [#1784](https://github.com/CodeGraphContext/CodeGraphContext/issues/1784) |
| TypeScript / TSX | [#1785](https://github.com/CodeGraphContext/CodeGraphContext/issues/1785) |
| go | [#1786](https://github.com/CodeGraphContext/CodeGraphContext/issues/1786) |
| rust | [#1787](https://github.com/CodeGraphContext/CodeGraphContext/issues/1787) |
| cpp | [#1788](https://github.com/CodeGraphContext/CodeGraphContext/issues/1788) |
| java | [#1789](https://github.com/CodeGraphContext/CodeGraphContext/issues/1789) |
| c_sharp | [#1790](https://github.com/CodeGraphContext/CodeGraphContext/issues/1790) |
| ruby | [#1791](https://github.com/CodeGraphContext/CodeGraphContext/issues/1791) |
| php | [#1792](https://github.com/CodeGraphContext/CodeGraphContext/issues/1792) |
| kotlin | [#1793](https://github.com/CodeGraphContext/CodeGraphContext/issues/1793) |
| scala | [#1794](https://github.com/CodeGraphContext/CodeGraphContext/issues/1794) |
| swift | [#1795](https://github.com/CodeGraphContext/CodeGraphContext/issues/1795) |
| haskell | [#1796](https://github.com/CodeGraphContext/CodeGraphContext/issues/1796) |
| dart | [#1797](https://github.com/CodeGraphContext/CodeGraphContext/issues/1797) |
| elixir | [#1798](https://github.com/CodeGraphContext/CodeGraphContext/issues/1798) |
| elisp | [#1799](https://github.com/CodeGraphContext/CodeGraphContext/issues/1799) |
| html | [#1800](https://github.com/CodeGraphContext/CodeGraphContext/issues/1800) |
| css | [#1801](https://github.com/CodeGraphContext/CodeGraphContext/issues/1801) |
| gradle | [#1802](https://github.com/CodeGraphContext/CodeGraphContext/issues/1802) |
| maven | [#1803](https://github.com/CodeGraphContext/CodeGraphContext/issues/1803) |
| mybatis | [#1804](https://github.com/CodeGraphContext/CodeGraphContext/issues/1804) |

C, Lua, Perl, Vue, Svelte, Solidity and HCL had no confirmed new defect in this matrix. This records tested coverage; it does not claim complete language specifications or all runtime dispatch can be inferred statically. Existing full-pipeline/backend tests remain separate from the semantic parser oracle.
