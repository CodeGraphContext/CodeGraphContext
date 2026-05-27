# CGC Report

_Generated: 2026-05-13 20:06 UTC_


## God Nodes — Highest Fan-In
_These nodes are called from many places. High fan-in increases risk: a change here affects every caller._

| Kind | Name | File | In-degree |
| --- | --- | --- | --- |
|  | magnitude | sample_project/advanced_classes2.py | 2 |
|  | helper | sample_project/module_b.py | 2 |
|  | double | sample_project/comprehensions_generators.py | 2 |
|  | make_adder | sample_project/function_chains.py | 2 |


## Most Complex Functions
_Cyclomatic complexity > 10 is a refactoring candidate._

| Function | File | Cyclomatic Complexity |
| --- | --- | --- |
| long_loop_example | edge_cases/long_functions.py | 11 |
| extended_try_except | edge_cases/long_functions.py | 8 |
| verbose_conditions | edge_cases/long_functions.py | 7 |
| matcher | sample_project/pattern_matching.py | 5 |
| try_except_finally | sample_project/control_flow.py | 4 |
| handle | sample_project/advanced_classes2.py | 3 |
| env_based_import | sample_project/control_flow.py | 3 |
| use_file | sample_project/context_managers.py | 2 |
| import_optional | sample_project/dynamic_imports.py | 2 |
| importlib_runtime | sample_project/dynamic_imports.py | 2 |
| dispatch_by_string | sample_project/dynamic_dispatch.py | 2 |
| higher_order | sample_project/advanced_functions.py | 2 |
| gen_numbers | sample_project/generators.py | 2 |
| agen_numbers | sample_project/generators.py | 2 |
| async_with_example | sample_project/generators.py | 2 |


## Potential Dead Code
_Functions with zero callers (not guaranteed dead — may be entry points or called via reflection)._

| Function | File |
| --- | --- |
| syntax_error | buggy_project/bad_syntax.py |
| very_long_name_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | buggy_project/long_name.py |
| space_test | path with space/test.py |
| calls | sample_project/advanced_calls.py |
| method | sample_project/advanced_calls.py |
| __init__ | sample_project/advanced_classes.py |
| __str__ | sample_project/advanced_classes.py |
| bar | sample_project/advanced_classes.py |
| change_value | sample_project/advanced_classes.py |
| do | sample_project/advanced_classes.py |
| do | sample_project/advanced_classes.py |
| foo | sample_project/advanced_classes.py |
| foo | sample_project/advanced_classes.py |
| <module> | sample_project/advanced_classes2.py |
| higher_order | sample_project/advanced_functions.py |
| inner | sample_project/advanced_functions.py |
| return_function | sample_project/advanced_functions.py |
| with_args_kwargs | sample_project/advanced_functions.py |
| with_defaults | sample_project/advanced_functions.py |
| outer_import | sample_project/advanced_imports.py |


## Suggested Cypher Queries
_Copy these into `execute_cypher_query` to explore further._

### Callers of a specific function
```cypher
MATCH (caller)-[:CALLS]->(fn:Function {name: 'yourFunctionName'})
RETURN caller.name, caller.path LIMIT 20
```

### Class hierarchy for a specific class
```cypher
MATCH path = (c:Class {name: 'YourClass'})-[:INHERITS*]->(parent)
RETURN [n IN nodes(path) | n.name] AS hierarchy
```

### Most-injected Spring beans
```cypher
MATCH ()-[:INJECTS]->(bean:Class)
RETURN bean.name, count(*) AS injection_count
ORDER BY injection_count DESC LIMIT 10
```

### All external library dependencies
```cypher
MATCH (m:MavenModule)-[:USES_LIBRARY]->(lib:ExternalLibrary)
RETURN m.artifact_id, lib.group_id, lib.artifact_id, lib.version
ORDER BY lib.artifact_id
```

### CALLS edges with low confidence (potential mis-resolutions)
```cypher
MATCH (a)-[c:CALLS]->(b)
WHERE c.confidence_label = 'AMBIGUOUS'
RETURN a.name, b.name, c.resolution_tier, a.path LIMIT 20
```
