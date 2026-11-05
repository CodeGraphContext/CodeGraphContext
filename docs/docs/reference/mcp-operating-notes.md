# MCP operating notes and coverage limits

## Verify the environment

The source package, PyPI package, GitHub release object and hosted documentation
can have different version labels. Pin an installed package/commit and record
`tools/list`, Python, parser-pack and actual native-engine versions when
reporting a bug. Run `cgc doctor` and retain server diagnostics. A requested
backend name is not evidence that fallback did not occur.

| Area | Acceptance needed |
| --- | --- |
| Kuzu / Ladybug | Real engine tests, adequate pool, property/query parity and clean reopen. Run their native test matrices in separate processes; loading both extensions in one process can collide. |
| FalkorDB Lite / remote | Confirm the actual engine and service lifecycle; fallback results do not establish independent parity. |
| Neo4j / other remote engines | Live service, driver/auth/TLS and backend-specific feature tests. |
| Desktop clients | Test the actual installed client; SDK/HTTP/build tests do not certify Claude/Cursor/Cline/VS Code host behavior. |
| Windows/macOS/ARM | Native grammar/backend wheels, path/symlink behavior and watcher tests on that platform. |
| SCIP | Language-specific indexer/compiler setup and result parity with the tree-sitter path. |
| Datasources | Populated schema fixtures plus live connectivity and TLS tests; empty query success is narrower. |

## First-use grammars and offline work

Installing the Python package does not guarantee all native grammars are
already cached. The installed tree-sitter-language-pack can download grammars
on first use. For supported installed versions, prepare required languages
while networking is available:

```python
from tree_sitter_language_pack import prefetch
prefetch(["python", "java"])
```

Set `XDG_CACHE_HOME` to a stable cache **base** before running this command and
before starting CGC, especially in tests that use fresh home directories. Copy
the entire versioned `tree-sitter-language-pack` cache tree to an offline host
with the same platform and package version. Do not point `XDG_CACHE_HOME` at
`libs/`, mix platform archives, or substitute unchecked third-party libraries.
Test parser initialization offline before relying on it in a presentation.
A proxy/downloader failure is a setup failure; retain its error rather than
recording it as a semantic parser defect.

## Memory, response limits and ownership

`CGC_EMBEDDED_BUFFER_POOL_MB` controls native buffer-pool allocation, not total
process RSS. Recursive traversals and scoped statistics can allocate much more
than symbol searches. In the October 2026 audit, 128 MiB failed small recursive
queries; 1024 MiB passed caller/callee checks. A 5,000-function Ladybug workload
needed 2048 MiB in that environment. These are measured examples, not universal
minimums or a backend ranking. Record source shape, pool, engine and RSS on
failure. Prefer bounded depth and scoped queries; output limits do not limit
native intermediate memory.

Use one owner for an embedded store. Do not run independent CLI/gateway owners
against the same native database path. Stop watching, finish jobs, drain
sessions, and close cleanly before transferring ownership. Native corruption
needs preserved database/WAL evidence and engine diagnostics; do not make
automatic deletion/reindex the only recovery path. A passing retry does not
explain an earlier intermittent failure.

Job cancellation, Python task cancellation, database transaction cancellation
and process termination are different mechanisms. End-to-end cooperative
cancellation and query timeout guarantees are not established for every path.
Graceful shutdown can wait for indexing to finish; it is not forced cancellation.

## Paths, secrets and graph identity

The top-level root guard must also apply to discovered/resolved source files
and watch events. Intended in-root links and explicitly configured roots are
separate from an all-paths override. Canonical paths reduce link-retarget
windows; they do not create an atomic filesystem sandbox against every race.

`INDEX_SOURCE` defaults to `true` and controls persisted source fields.
`REDACT_SECRETS` defaults to `false`; it is a separate opt-in setting, not a
general privacy guarantee. Review graph bundles,
reports and source-bearing tool responses before sharing them. A redaction
setting does not authorize reading an otherwise disallowed file.

Node IDs can include source path, line and occurrence identity. They are not
stable semantic IDs across arbitrary file moves or insertions. Resolve names
within an explicit repository and inspect ambiguous matches. Portable bundle
imports may relocate paths; verify repository registration and source lookups
after import, and keep `clear_existing` disabled unless replacement is intended.

## Diagnosing and demonstrating behavior

For a useful reproduction, include the source fixture, expected graph/path,
actual returned rows, package commit, grammar version, actual engine, pool and
transport. Keep negative results, retries and setup failures separately labeled.
Use a known caller/path and an unused sentinel to check that a success was not
caused by an empty collection or echoed request argument.

The October 2026 engineering audit found existing focused parser/build fixes
in PRs #1806-#1827 and #1830/#1831, plus call-chain fix #1781. Those are
version-specific candidates, not proof that every branch is merged or every
language construct is covered. Verify each PR's current state and the combined
regression suite before release.

A demonstration should show discovery, job completion, a grounded search/path,
a watched edit and a real report artifact. Label selected excerpts and edited
playback pacing. Separate tool correctness, assistant task accuracy, character
counts, tokenizer counts and presentation polish.
