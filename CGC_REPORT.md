# CGC Report

_Generated: 2026-06-07 13:50 UTC_


## God Nodes — Highest Fan-In
_These nodes are called from many places. High fan-in increases risk: a change here affects every caller._

| Kind | Name | File | In-degree |
| --- | --- | --- | --- |
| ? | demo | repo/main.py | 0 |


## Most Complex Functions
_Cyclomatic complexity > 10 is a refactoring candidate._

| Function | File | Cyclomatic Complexity |
| --- | --- | --- |
| demo | repo/main.py | ? |


## Cross-Module Connections
_Calls that cross package boundaries — review for unexpected coupling._

| Caller | Caller File | Callee | Callee File | Confidence |
| --- | --- | --- | --- | --- |
| ? |  | ? |  | — |


## Potential Dead Code
_Functions with zero callers (not guaranteed dead — may be entry points or called via reflection)._

| Function | File |
| --- | --- |
| demo | repo/main.py |


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
