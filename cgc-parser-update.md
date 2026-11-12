# CodeGraphContext: C and C++ parser changes

**Repo:** `~/git/ra014620/CodeGraphContext`
**Branch:** `feat/c-field-macro-ztest-edges`, on top of `d8f3035f` (uncommitted)
**Tests:** `tests/unit/parsers/test_c_ztest_fields_macros.py`, 7 tests, all passing
**Graph built with it:** `zephyr_fields` on FalkorDB at `alpha.local:6379`. The `zephyr` graph was not changed.

## Why

Stock cgc gives the C graph functions, structs, macros and `CALLS` edges. On Zephyr, three questions an agent needed could only be answered by grep:

1. **"What writes `conn->recv_options.mss_found`?"** cgc did not record struct field accesses at all. This was the TCP MSS bug.
2. **"Who uses `conn_mss()`?"** `conn_mss` is a function-like macro. Its invocations parse as calls, but the `CALLS` pass looks for a `Function` target, so nothing linked a function to the macros it uses.
3. **"What does this test do?"** `ZTEST(suite, name) { ... }` hides the function declarator. Tree-sitter does not expand macros, so it reads an expression statement followed by a free-standing block. The test bodies were not functions, and the calls inside them had no caller.

There was also a side problem. A function with an attribute macro before its name, such as `void __soc_ram_code f(void) { ... }`, misparses in the same way and was missing from the graph.

## Summary of changes

| File | Change |
|---|---|
| `tools/languages/c.py` | New passes: macro-defined functions, field accesses in functions, field accesses in macro bodies. Calls and field accesses inside a macro-defined body are attributed to that function. |
| `tools/languages/cpp.py` | Reuses the C field-access passes (cgc parses every `.h` as C++), and records a macro's body text (`value`). |
| `tools/indexing/persistence/writer.py` | New `write_c_use_links()`: writes `USES_MACRO`, `READS_FIELD`, `WRITES_FIELD` and `TAKES_ADDRESS_OF_FIELD` edges and `Field` nodes. |
| `tools/indexing/pipeline.py` | Calls `write_c_use_links()` after the `CALLS` edges. |
| `tools/indexing/schema.py` | Index on `Field.name`. |
| `tools/indexing/schema_contract.py` | Adds the `Field` label and the four relationship types. |

About 300 lines added, 1 removed.

## Graph model added

```
(:Function)-[:USES_MACRO {lines}]->(:Macro)
(:Function|:Macro)-[:READS_FIELD {lines}]->(:Field {name})
(:Function|:Macro)-[:WRITES_FIELD {lines}]->(:Field {name})
(:Function)-[:TAKES_ADDRESS_OF_FIELD {lines}]->(:Field {name})
```

- `lines` is the sorted list of source lines where the use occurs, so one edge covers every occurrence in that function or macro.
- `Field` nodes are keyed by **name only**. Tree-sitter has no type information, so `a->len` and `b->len` are the same `Field {name: "len"}`. To narrow a query to one struct, filter on the accessing function's path. The `sdx_code_lookup` tool does that with its `file` argument.
- New `Function` properties for macro-defined bodies: `defined_by_macro` (for example `"ZTEST_F"`) and `macro_args` (for example `["fsuite", "test_two"]`). The macro name is also put in `decorators`. These reach the node through the writer's existing `SET n += row`.

## C parser (`c.py`)

### 1. Macro-defined functions: `_find_macro_defined_functions()`

This pass runs first, before the ordinary function pass, because later passes use the body ranges it records.

**Detection is by parse shape, not by a list of macro names.** At file scope, a macro-defined function parses in one of two ways:

- **Two or more arguments**, as in `ZTEST(suite, name) { ... }`: an `expression_statement` holding a `call_expression` whose function is a plain identifier, immediately followed by a sibling `compound_statement`. Plain C never has that pair at file scope.
- **One argument**, as in `START_TEST(name) { ... }`: a `function_definition` whose type is a `type_identifier` (the macro name) and whose declarator is a `parenthesized_declarator` (`(name)`). No real C function has that shape.

The scan also descends into `#if`, `#ifdef`, `#else`, `#elif` and `#elifdef` blocks, because tests are often conditionally compiled.

**Naming:** the second identifier argument if there is one (`ZTEST(suite, name)` → `name`, `TEST(Suite, Name)` → `Name`), else the first.

**Two cases look the same but are not macro-defined functions:**

| Case | How it is told apart | Result |
|---|---|---|
| Attribute macro before a real function: `void __soc_ram_code f(void) { ... }` misparses as `f(void)` plus a block | The argument list is exactly `(void)` | Kept as an ordinary function `f`, without `defined_by_macro`. The stock pass lost these. |
| A macro that expands to a struct head: `SCSI_CMD_STRUCT(op) { uint8_t opcode; } __packed;` | **Both** of these hold: something other than a comment follows the closing brace on the same line (`;`, `__packed;`), **and** the body contains only declarations | Skipped. Either test alone is not enough, because some functions, ZTESTs among them, end in a stray `};`. |

Each function found gets:
- the usual fields (`name`, `line_number`, `end_line`, `cyclomatic_complexity` from the body, `docstring`, `source` when `index_source` is on);
- `defined_by_macro` and `macro_args`.

Each body's byte range is stored in `self._macro_fn_ranges`.

**Attribution:** `_get_parent_context()` falls back to `_macro_fn_ranges` when no enclosing `function_definition` is found. Calls and field accesses inside a ZTEST body are therefore attributed to the test, so `CALLS` edges now start from tests.

**What it finds on Zephyr's `.c` files:** 9,350 macro-defined bodies:
- the whole ZTEST family (`ZTEST`, `ZTEST_F`, `ZTEST_USER`, `ZTEST_USER_F`, `ZTEST_P`, `ZTEST_BENCHMARK*`, ...), about 53 more tests than an earlier fixed-name list;
- `MODEM_CMD_DEFINE` (152), `ISR_DIRECT_DECLARE`, `SCSI_CMD_HANDLER` and others;
- 21 real functions behind attribute macros, kept as ordinary functions.

`ZTEST_SUITE(...)` has no body, so it is not paired.

### 2. Field accesses in functions: `_find_field_accesses()`

The new tree-sitter query is:

```
(field_expression field: (field_identifier)) @access
```

This matches `p->x` and `s.x`. Each match is classified by its parent, after skipping enclosing parentheses:

| Parent | Access |
|---|---|
| `assignment_expression`, and the access is the left side (`=`, `+=`, `|=`, ...) | `write` |
| `update_expression` (`++`, `--`, pre or post) | `write` |
| `pointer_expression` whose operator is `&` (`&x->f`, `&(x->f)`) | `address`: the callee may write it |
| anything else | `read` |

Only the outermost field of a chain is the target. In `x->a.b = 1`, `b` is a write and `a` is a read.

Accesses outside a function, such as file-scope initializers, are dropped. Rows are aggregated per (function, function line, field, access), with the list of lines.

### 3. Field accesses in macro bodies: `_find_macro_field_accesses()`

Tree-sitter keeps a `#define` body as raw text, so this pass uses a regex (`MACRO_FIELD`):

```python
(?:->|(?<![\w)\]])\.|(?<=[\w)\]])\.)\s*([A-Za-z_]\w*)\b(\s*=(?!=))?
```

- It matches `->name` and `.name`, but not a number such as `1.5f`: a `.` followed by a digit cannot start the identifier group.
- A single `=` after the name (not `==`) makes the access a **write**. That includes designated initializers (`.n = 1`). Everything else is a **read**.
- There is no `address` kind for macros.
- The line number is the macro's line plus the newlines before the match, so continuation lines are counted correctly.

Example from the tests: `#define conn_mss(_conn) ((_conn)->recv_options.mss_found ? ... : 536)` gives `conn_mss` READS `recv_options` and `mss_found`.

### 4. Output

`parse()` now also returns `field_accesses`, a list of rows of one of these two shapes:

```python
{"function": "parse", "function_line": 5, "field": "mss_found", "access": "write", "lines": [7]}
{"macro": "conn_mss", "macro_line": 2, "field": "mss_found", "access": "read", "lines": [2]}
```

## C++ parser (`cpp.py`)

cgc maps `.h` to the C++ parser, so Zephyr's headers, with their `static inline` functions and macros, went through `CppTreeSitterParser`. Without this change, header code had no field edges. For example, `conn_mss` in `tcp_private.h` → `mss_found` was missing.

- The parser imports `CTreeSitterParser` and calls its `_find_field_accesses()` and `_find_macro_field_accesses()` on its own parse tree. The `field_expression` / `field_identifier` node types are the same in the C++ grammar, and context comes from the C++ parser's own `_get_parent_context()`.
- `_find_macros()` now stores each macro's body text as `value`, which the macro field pass reads.
- `parse()` returns `field_accesses`.

The macro-defined-function pass is **not** applied to the C++ parser. ZTEST bodies in headers, which are rare, are not detected.

## Writer: `write_c_use_links()` (`writer.py`)

This runs once per index, over all files with `lang` `c` or `cpp`, after the `CALLS` edges.

**`USES_MACRO`:** a call whose name matches a macro definition, made from inside a function (file-scope uses are skipped), resolves to:
1. a definition in the same file; else
2. a definition in a file the caller `#include`s, matched by file **basename**; else
3. every definition, if there are at most 3; with more than 3 the call is skipped as ambiguous.

Only function-like macro *calls* are seen. An object-like macro used as a bare identifier produces no call, so it gets no edge.

**Field edges:** first `MERGE (:Field {name})` for every distinct field name. Then batched `UNWIND ... MATCH ... MERGE ... SET r.lines` queries, 2,000 rows per batch, from the `Function` (matched by name, path and line) or `Macro` (name, path and line) to the `Field`.

**Backend:** Kuzu is skipped with a log line, because its schema has no `Field` table. FalkorDB and Neo4j are supported.

**Log line:** `[C-USES] N macro-use, N function field and N macro field links in S s.`

## Pipeline, schema and contract

- `pipeline.py`: a new job status, "Writing C macro-use and field-access edges...", and the `write_c_use_links(all_file_data)` call.
- `schema.py`: `CREATE INDEX IF NOT EXISTS FOR (fd:Field) ON (fd.name)`.
- `schema_contract.py`: `Field` in `NODE_LABELS`; `USES_MACRO`, `READS_FIELD`, `WRITES_FIELD` and `TAKES_ADDRESS_OF_FIELD` in `RELATIONSHIP_TYPES`.

## Tests

`tests/unit/parsers/test_c_ztest_fields_macros.py` parses one synthetic C file containing a `conn_mss`-style macro, a `SET_N` writing macro, `ZTEST`, `ZTEST_F` inside `#ifdef`, `ZTEST_SUITE`, `ZTEST_BENCHMARK`, `START_TEST`, an attribute-macro function, two struct-head macros and a ZTEST ending in `};`.

| Test | Checks |
|---|---|
| `test_macro_defined_bodies_become_functions` | Exactly `test_one`, `test_two`, `bench_one`, `test_single` and `test_stray_semicolon` are found. The name is the 2nd argument for `ZTEST_BENCHMARK`. The one-argument `START_TEST` is found. `ramcode_reset` is kept as an ordinary function at the right line. Struct heads are excluded. Line ranges, `macro_args`, `decorators` and `source` are correct. |
| `test_calls_inside_ztest_are_attributed_to_the_test` | `check()` inside `test_one` has `test_one` as its caller. |
| `test_field_access_kinds` | `=` and `+=` are writes; `(x)++` through parentheses is a write; an argument is a read; `&conn->recv_options` is an address; writes inside ZTEST and ZTEST_F bodies are attributed to the test. |
| `test_macro_body_field_accesses` | `conn_mss` reads `mss_found` and `recv_options`; `SET_N` writes `n`. |
| `test_numbers_are_not_fields` | `1.5f * x.y + s->z` yields only `y` and `z`. |
| `test_writer_links_macro_uses_and_fields` | `USES_MACRO` resolves through the include, not to another file's `conn_mss`. A macro with 4 definitions is skipped. A file-scope use is skipped. The field edge batches are correct. |
| `test_headers_parsed_as_cpp_get_field_accesses` | The C++ parser on header text yields the macro read, the function write and the address-of. |

Run them with:

```bash
cd ~/git/ra014620/CodeGraphContext && python3 -m pytest -q tests/unit/parsers/test_c_ztest_fields_macros.py
```

## Result on Zephyr (`zephyr_fields`)

Zephyr 4.5.0-rc2 (`c136c73d7be`) was indexed three times while these changes were made:

| Index | What changed | Notes |
|---|---|---|
| 1 | Field and macro-use edges for `.c` only; a fixed list of ZTEST macros | 129,005 functions, 226k reads, 104k writes, 37k address-of, 212k macro uses, 36,772 fields; 56 min |
| 2 | Headers (C++ parser) get field edges | 233k reads, 110k writes, 38,025 fields; `conn_mss` → `mss_found` present |
| 3 | Shape-based macro-function detection replaces the list | About 129,900 functions; attribute-macro functions such as `ramcode_reset_i_cache` present; 56.6 min |

The agent tool `sdx_code_lookup` (in the h6f OpenCode variant) builds on these edges:
- `field` mode lists the writers, address-takers and readers of a field;
- `writes` mode and the `writes:` suffix on outline lines show which fields each function in a file or directory writes;
- `relation: callers` on a macro lists its users.

On the TCP MSS task, one `field: mss_found` lookup listed the three writers, and the coder went straight to the cause. On the RTIO task, the `WRITES_FIELD` edges in `include/zephyr/rtio/` and `subsys/rtio/`, excluding the `prep_*` helpers, are exactly upstream's set of runtime writers.

## Known limitations

- **Fields by name only.** Without types, every `len`, `buf` or `flags` across the tree is one node. Queries must filter by path or by the accessing function.
- **Macro bodies by regex.** The regex can misread unusual token pastes or stringification (`##`, `#`). It does not detect `address` in macros, and it treats any `.x =` as a write, including a designated initializer for a different struct.
- **Designated initializers inside functions** (`struct s v = { .x = 1 }`) are not `field_expression` nodes, so they are not recorded as writes. Only macro bodies get them, through the regex.
- **Macros that name the function elsewhere**, such as Linux's `SYSCALL_DEFINE3(read, ...)`, get the wrong name. Getting it right needs the macro's `#define`, which is usually in another file.
- **Macro-defined functions are detected in `.c` files only.** The C++ parser does not run that pass. On Zephyr this costs almost nothing. Running the C pass over all 5,697 tracked headers found no macro-defined bodies and one attribute-macro function (`z_sched_spinlock_lock`, `kernel/include/kspinlock.h:71`), so extending it to headers is not worth it here.
- **Headers are parsed with the C++ grammar.** cgc maps `.h` to C++ for every repo. On Zephyr's headers the C grammar finds 6,858 functions and the C++ grammar 6,825, so 33 (0.5%) are lost. Parsing `.h` as C would need a per-repo setting or a content check, because mixed C/C++ projects have C++ headers. Not changed.
- **`USES_MACRO` resolution** matches includes by basename and gives up above 3 candidate definitions. Object-like macros get no edge.
- **Kuzu** gets none of this.
- **Not committed or proposed upstream** yet.
