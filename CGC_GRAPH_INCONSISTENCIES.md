# CGC Graph Building Inconsistencies (100 items)

**Generated:** 2026-06-10
**Method:** Parsed from `CGC_CALL_GRAPH_AUDIT_REPORT.md` (indexer export vs golden), plus `CGC_EXPECTED_GRAPH_SPEC.md` gaps and Python source review.

Use this as a fix backlog. Each ID should become one pattern test + one engine fix.

### Categories
| Category | Meaning |
|----------|---------|
| `indexer_vs_golden_*` | Confirmed: golden has it, live indexer does not |
| `golden_vs_spec` | Golden incomplete vs spec (fix engine first, then re-export golden) |
| `structural` | Edge type or node kind not implemented in engine |
| `source_vs_spec` | Visible in source, likely missing from indexer |
| `resolver` | `calls.py` / pipeline behavior issue |
| `cross_lang` | Language-specific accuracy gap from audit |
| `meta` | Tooling / process / release inconsistency |

| ID | Pri | Lang | Cat | Source | Issue | Expected | Actual |
|---:|-----|------|-----|--------|-------|----------|--------|
| 1 | medium | python | indexer_vs_golden_edge | sample_project | Function:calls:sample_project/advanced_calls.py:ln_3 --[CALLS]--> Function:square:sample_project/adv | In golden | Missing in indexer |
| 2 | medium | python | indexer_vs_golden_edge | sample_project | Function:higher_order:sample_project/advanced_functions.py:ln_7 --[CALLS]--> Parameter:func:sample_p | In golden | Missing in indexer |
| 3 | medium | python | indexer_vs_golden_edge | sample_project | Function:greet:sample_project/class_instantiation.py:ln_5:ctx_B --[CALLS]--> Function:greet:sample_p | In golden | Missing in indexer |
| 4 | medium | c | indexer_vs_golden_node | sample_project_c | EnumMember:COLOR_BLUE:sample_project_c/tough_macros.c | In golden | Missing in indexer |
| 5 | medium | c | indexer_vs_golden_node | sample_project_c | EnumMember:COLOR_GREEN:sample_project_c/tough_macros.c | In golden | Missing in indexer |
| 6 | medium | c | indexer_vs_golden_node | sample_project_c | EnumMember:COLOR_RED:sample_project_c/tough_macros.c | In golden | Missing in indexer |
| 7 | medium | c | indexer_vs_golden_edge | sample_project_c | Class:color_t:sample_project_c/tough_macros.c:ln_69 --[CONTAINS]--> EnumMember:COLOR_BLUE:sample_pro | In golden | Missing in indexer |
| 8 | medium | c | indexer_vs_golden_edge | sample_project_c | Function:process_entity:sample_project_c/utils.c:ln_4 --[CALLS]--> Function:my_callback:sample_proje | In golden | Missing in indexer |
| 9 | medium | cpp | indexer_vs_golden_edge | sample_project_cpp | Function:templateDemo:sample_project_cpp/templates.cpp:ln_10 --[CALLS]--> Function:add:sample_projec | In golden | Missing in indexer |
| 10 | medium | csharp | indexer_vs_golden_edge | sample_project_csharp | Function:MethodFromPartA:sample_project_csharp/ToughCases.cs:ln_14:ctx_MultiPartClass --[CALLS]--> F | In golden | Missing in indexer |
| 11 | medium | csharp | indexer_vs_golden_edge | sample_project_csharp | Class:MultiPartClass:sample_project_csharp/ToughCases_PartB.cs:ln_3 --[PARTIAL_OF]--> Class:MultiPar | In golden | Missing in indexer |
| 12 | medium | dart | indexer_vs_golden_edge | sample_project_dart | Function:main:sample_project_dart/lib/main.dart:ln_3 --[CALLS]--> Function:performAction:sample_proj | In golden | Missing in indexer |
| 13 | medium | dart | indexer_vs_golden_edge | sample_project_dart | File:tough_cases_part.dart:sample_project_dart/lib/tough_cases_part.dart --[PART_OF]--> File:tough_c | In golden | Missing in indexer |
| 14 | medium | elixir | indexer_vs_golden_edge | sample_project_elixir | Function:perform:sample_project_elixir/tough_cases.ex:ln_20:ctx_Tough.Worker --[CALLS]--> Function:i | In golden | Missing in indexer |
| 15 | medium | elixir | indexer_vs_golden_edge | sample_project_elixir | Function:run:sample_project_elixir/main.ex:ln_8:ctx_MyApp.Main --[CALLS]--> Function:start_link:samp | In golden | Missing in indexer |
| 16 | medium | go | indexer_vs_golden_edge | sample_project_go | Struct:Circle:sample_project_go/interfaces.go:ln_27 --[IMPLEMENTS]--> Interface:Shape:sample_project | In golden | Missing in indexer |
| 17 | medium | go | indexer_vs_golden_edge | sample_project_go | Struct:Triangle:sample_project_go/interfaces.go:ln_40 --[IMPLEMENTS]--> Interface:Shape:sample_proje | In golden | Missing in indexer |
| 18 | medium | go | indexer_vs_golden_edge | sample_project_go | Struct:Rectangle:sample_project_go/interfaces.go:ln_33 --[IMPLEMENTS]--> Interface:Shape:sample_proj | In golden | Missing in indexer |
| 19 | medium | haskell | indexer_vs_golden_edge | sample_project_haskell | Class:Product:sample_project_haskell/src/ToughCases.hs:ln_9 --[IMPLEMENTS]--> Class:Descriptive:samp | In golden | Missing in indexer |
| 20 | medium | haskell | indexer_vs_golden_edge | sample_project_haskell | Class:User:sample_project_haskell/src/ToughCases.hs:ln_8 --[IMPLEMENTS]--> Class:Descriptive:sample_ | In golden | Missing in indexer |
| 21 | medium | haskell | indexer_vs_golden_edge | sample_project_haskell | Function:main:sample_project_haskell/Main.hs:ln_7 --[CALLS]--> Class:Person:sample_project_haskell/s | In golden | Missing in indexer |
| 22 | medium | java | indexer_vs_golden_edge | sample_project_java | Function:main:sample_project_java/src/com/example/app/Main.java:ln_13:ctx_Main --[CALLS]--> Function | In golden | Missing in indexer |
| 23 | medium | java | indexer_vs_golden_edge | sample_project_java | Function:run:sample_project_java/src/com/example/app/ToughCases.java:ln_165:ctx_Client --[CALLS]-->  | In golden | Missing in indexer |
| 24 | medium | kotlin | indexer_vs_golden_edge | sample_project_kotlin | Object:Companion:sample_project_kotlin/ToughCases.kt:ln_22 --[COMPANION_OF]--> Class:DatabaseConnect | In golden | Missing in indexer |
| 25 | medium | lua | indexer_vs_golden_edge | sample_project_lua | Function:main:sample_project_lua/main.lua:ln_4 --[CALLS]--> Function:greet:sample_project_lua/utils. | In golden | Missing in indexer |
| 26 | medium | perl | indexer_vs_golden_edge | sample_project_perl | File:main.pl:sample_project_perl/main.pl --[CALLS]--> Function:new:sample_project_perl/lib/MyModule/ | In golden | Missing in indexer |
| 27 | medium | perl | indexer_vs_golden_edge | sample_project_perl | Function:speak:sample_project_perl/tough_cases.pl:ln_22:ctx_Dog --[CALLS]--> Function:speak:sample_p | In golden | Missing in indexer |
| 28 | medium | perl | indexer_vs_golden_edge | sample_project_perl | Class:Dog:sample_project_perl/tough_cases.pl:ln_19 --[INHERITS]--> Class:Animal:sample_project_perl/ | In golden | Missing in indexer |
| 29 | medium | php | indexer_vs_golden_edge | sample_project_php | Function:run:sample_project_php/tough_cases.php:ln_26:ctx_ConflictResolver --[CALLS]--> Function:sha | In golden | Missing in indexer |
| 30 | medium | ruby | indexer_vs_golden_edge | sample_project_ruby | Function:test_callbacks:sample_project_ruby/tough_cases.rb:ln_45 --[CALLS]--> Function:initialize:sa | In golden | Missing in indexer |
| 31 | medium | rust | indexer_vs_golden_node | sample_project_rust | Function:snappy_compress:sample_project_rust/src/tough_cases.rs:ln_44 | In golden | Missing in indexer |
| 32 | medium | rust | indexer_vs_golden_edge | sample_project_rust | File:tough_cases.rs:sample_project_rust/src/tough_cases.rs --[CONTAINS]--> Function:snappy_compress: | In golden | Missing in indexer |
| 33 | medium | rust | indexer_vs_golden_edge | sample_project_rust | Function:call_both:sample_project_rust/src/tough_cases.rs:ln_32 --[CALLS]--> Function:action:sample_ | In golden | Missing in indexer |
| 34 | medium | rust | indexer_vs_golden_edge | sample_project_rust | Function:test_specialization:sample_project_rust/src/tough_cases.rs:ln_103 --[CALLS]--> Function:spe | In golden | Missing in indexer |
| 35 | medium | scala | indexer_vs_golden_edge | sample_project_scala | Function:main:sample_project_scala/Main.scala:ln_2:ctx_Main --[CALLS]--> Function:apply:sample_proje | In golden | Missing in indexer |
| 36 | medium | swift | indexer_vs_golden_edge | sample_project_swift | Function:testProtocols:sample_project_swift/ToughCases.swift:ln_31 --[CALLS]--> Function:doWork:samp | In golden | Missing in indexer |
| 37 | medium | typescript | indexer_vs_golden_edge | sample_project_typescript | Function:loadModuleDynamically:sample_project_typescript/src/tough_cases.ts:ln_29 --[CALLS]--> File: | In golden | Missing in indexer |
| 38 | medium | typescript | indexer_vs_golden_edge | sample_project_typescript | Function:updateAge:sample_project_typescript/src/decorators-metadata.ts:ln_363:ctx_User --[DECORATED | In golden | Missing in indexer |
| 39 | high | python | structural | src/ | DECORATED_BY edge type not implemented | @decorator → DECORATED_BY | 0 matches in src/ |
| 40 | high | python | structural | src/ | METACLASS edge type not implemented | metaclass= → METACLASS | 0 matches in src/ |
| 41 | medium | python | structural | python.py | <module> only when file has module-level calls | One <module> per .py file | _attach_module_context conditional |
| 42 | high | python | golden_vs_spec | goldens/sample_project | Golden has 0 DECORATED_BY edges | Per CGC_EXPECTED_GRAPH_SPEC | Not in edges.jsonl |
| 43 | medium | python | golden_vs_spec | ./advanced_calls.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 44 | medium | python | golden_vs_spec | ./advanced_classes.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 45 | medium | python | golden_vs_spec | ./advanced_functions.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 46 | medium | python | golden_vs_spec | ./advanced_imports.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 47 | medium | python | golden_vs_spec | ./async_features.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 48 | medium | python | golden_vs_spec | ./circular1.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 49 | medium | python | golden_vs_spec | ./circular2.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 50 | medium | python | golden_vs_spec | ./complex_classes.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 51 | medium | python | golden_vs_spec | ./context_managers.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 52 | medium | python | golden_vs_spec | ./control_flow.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 53 | medium | python | golden_vs_spec | ./dynamic_dispatch.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 54 | medium | python | golden_vs_spec | ./dynamic_imports.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 55 | medium | python | golden_vs_spec | ./edge_cases/comments_only.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 56 | medium | python | golden_vs_spec | ./edge_cases/docstring_only.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 57 | medium | python | golden_vs_spec | ./edge_cases/empty.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 58 | medium | python | golden_vs_spec | ./edge_cases/hardcoded_secrets.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 59 | medium | python | golden_vs_spec | ./edge_cases/long_functions.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 60 | medium | python | golden_vs_spec | ./edge_cases/syntax_error.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 61 | medium | python | golden_vs_spec | ./generators.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 62 | medium | python | golden_vs_spec | ./mapping_calls.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 63 | medium | python | golden_vs_spec | ./module_a.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 64 | medium | python | golden_vs_spec | ./module_b.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 65 | medium | python | golden_vs_spec | ./module_c/__init__.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 66 | medium | python | golden_vs_spec | ./module_c/submodule1.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 67 | medium | python | golden_vs_spec | ./module_c/submodule2.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 68 | medium | python | golden_vs_spec | ./namespace_pkg/ns_module.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 69 | medium | python | golden_vs_spec | ./nesting_test.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 70 | medium | python | golden_vs_spec | ./pattern_matching.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 71 | medium | python | golden_vs_spec | ./pkg_tough/__init__.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 72 | medium | python | golden_vs_spec | ./pkg_tough/parent_mod.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 73 | medium | python | golden_vs_spec | ./pkg_tough/subpkg/__init__.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 74 | medium | python | golden_vs_spec | ./pkg_tough/subpkg/child_mod.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 75 | medium | python | golden_vs_spec | ./tough_cases.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 76 | medium | python | golden_vs_spec | ./typing_examples.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 77 | medium | python | golden_vs_spec | ./unicode_test.py | Missing <module> Function node | <module> at L1 | Not in golden |
| 78 | high | all | meta | GOLDEN_PERFECTION_REPORT.md | Circular perfection gate (export vs itself) | Indexer vs source truth | Misleading 21/21 PASS |
| 79 | high | all | meta | audit reports | CALLS avg 84.6% vs perfection 100% | Single metric | Conflicting reports |
| 80 | high | all | meta | MANUAL_AUDIT.md | Hand-edited golden not on disk | 563/796 nodes | 482/621 in metadata.json |
| 81 | high | python | meta | PyPI 0.4.16 | Nested f1→f2→f3 broken on published wheel | Function→Function CALLS | Fixed locally only |
| 82 | medium | all | meta | E2E BUG-005 | delete leaves orphan nodes | 0 after delete | 9 remain |
| 83 | medium | all | meta | E2E BUG-001 | Repo .env overrides global config | Isolated HOME | Config bleed |
| 84 | medium | python | source_vs_spec | control_flow.py | try_except_finally L14 raise ValueError | CALLS→ValueError | Likely missing in indexer |
| 85 | medium | python | source_vs_spec | control_flow.py | conditional_inner_import L25 import numpy | IMPORTS numpy | Likely missing |
| 86 | medium | python | source_vs_spec | control_flow.py | conditional_inner_import L26 np.array | CALLS→array | Likely missing |
| 87 | medium | python | source_vs_spec | control_flow.py | env_based_import L31-L37 conditional json imports | IMPORTS ujson/json | Likely missing |
| 88 | medium | python | source_vs_spec | control_flow.py | env_based_import L38 json.dumps | CALLS→dumps | Likely missing |
| 89 | medium | python | source_vs_spec | dynamic_dispatch.py | dispatch_by_key L12 DISPATCH[name](a,b) | CALLS→add/sub/mul | May be partial |
| 90 | medium | python | source_vs_spec | dynamic_dispatch.py | partial_example L21 add5(10) | CALLS partial→add, add5→add | May be partial |
| 91 | medium | python | source_vs_spec | tough_cases.py | globals()[func_name]() L48-49 | CALLS dynamic | Tier 9 / missing |
| 92 | medium | python | source_vs_spec | tough_cases.py | getattr(self, helper_method) L52 | CALLS→helper_method | May resolve |
| 93 | medium | python | source_vs_spec | tough_cases.py | injected_call via metaclass L37 | CALLS + METACLASS | Partial |
| 94 | medium | python | source_vs_spec | complex_classes.py | wrapper L19 str(func(...)) | CALLS str, func | May be on wrong node |
| 95 | medium | python | source_vs_spec | complex_classes.py | class_method L15 cls().greet(cls()) | CALLS Child ctor, greet | Partial |
| 96 | medium | python | source_vs_spec | function_chains.py | L8 strip().lower().replace chain | Chained CALLS | May be partial |
| 97 | medium | python | source_vs_spec | function_chains.py | L17 make_adder(2)(8) | CALLS make_adder→adder | Closure chain |
| 98 | medium | python | source_vs_spec | cli_and_dunder.py | L12 __main__ run() | <module>→run | If __main__ block |
| 99 | medium | python | source_vs_spec | advanced_classes.py | Meta.__new__ L22 super().__new__ | CALLS super | May exist |
| 100 | medium | python | source_vs_spec | typing_examples.py | dict_func L10 sum(d.values()) | CALLS sum, values | May exist |

## Suggested fix order

1. **IDs 1–3** — Python CALLS gaps confirmed by audit (`advanced_calls`, `advanced_functions`, `class_instantiation`)
2. **IDs 4–38** — Other languages' confirmed indexer-vs-golden gaps (Lua/Swift worst)
3. **Structural** — Implement DECORATED_BY + METACLASS in parser/writer
4. **`<module>`** — One pseudo-function per Python file, then re-export golden
5. **Resolver** — Tier 8/9 fallbacks, dynamic dispatch
6. **Meta** — Retire circular perfection gate; trust `call_graph_audit.py` only

## Regenerate

```bash
.venv/bin/python scripts/call_graph_audit.py   # refresh CGC_CALL_GRAPH_AUDIT_REPORT.md
# then re-run the harvest script or diff manually
```
