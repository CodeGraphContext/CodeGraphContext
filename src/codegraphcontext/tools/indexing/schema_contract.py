# src/codegraphcontext/tools/indexing/schema_contract.py
"""
Semantic graph contract: labels, relationship types, and merge keys used by indexing.

Backends must produce nodes/relationships consistent with this contract so MCP
and query tools remain stable. This module is documentation + test hooks only.
"""

# Node labels written by the indexing pipeline (excluding dynamic query-only uses)
NODE_LABELS = frozenset({
    "Repository",
    "Directory",
    "File",
    "Function",
    "Class",
    "Trait",
    "Variable",
    "Interface",
    "Macro",
    "Struct",
    "Enum",
    "EnumMember",
    "Union",
    "Record",
    "Property",
    "Annotation",
    "Module",
    "Parameter",
    # Build graph nodes (#888)
    "MavenModule",
    "GradleModule",
    "ExternalLibrary",
    # Datasource architecture graph (#843 scoped)
    "Datasource",
    "DbTable",
    "DbColumn",
    "RedisKeyPattern",
})

RELATIONSHIP_TYPES = frozenset({
    "CONTAINS",
    "CALLS",
    "HEURISTIC_CALLS",
    "IMPORTS",
    "INHERITS",
    "HAS_PARAMETER",
    "INCLUDES",
    "IMPLEMENTS",
    "PARTIAL_OF",
    "PART_OF",
    "DECORATED_BY",
    "METACLASS",
    "COMPANION_OF",
    "EMBEDS",
    # Spring DI semantic edges (#887)
    "INJECTS",
    "EXPOSES_ENDPOINT",
    "PROVIDES_BEAN",
    # Build graph edges (#888)
    "MODULE_DEPENDS_ON",
    "USES_LIBRARY",
    "CHILD_MODULE",
    "FILE_BELONGS_TO",
    # Datasource architecture graph (#843 scoped)
    "READS",
    "WRITES",
    "MAPS_TO",
    "HAS_COLUMN",
    "STORED_IN",
})

# Identity properties used in MERGE for code entities (path = absolute file path).
# occurrence_index disambiguates distinct symbols that share a name and a line in
# one file -- grouped CSS selectors, minified JS bundles -- which the previous
# three-property key silently merged into a single node (#1393). It is 0 for the
# first record of each (name, line_number) key, so identity is unchanged for the
# overwhelming majority of symbols, which never collide.
FUNCTION_MERGE_KEYS = ("name", "path", "line_number", "occurrence_index")
CLASS_MERGE_KEYS = ("name", "path", "line_number", "occurrence_index")
FILE_MERGE_KEYS = ("path",)
REPOSITORY_MERGE_KEYS = ("path",)
DIRECTORY_MERGE_KEYS = ("path",)

# IMPORTS (File -> Module). One edge per imported NAME: the key is the line plus
# the imported name, in every language. JS/TS used to be keyed on the line
# alone, so `import { a, b } from './x'` kept only the last name.
# Every IMPORTS MERGE must use exactly these keys (enforced by
# tests/unit/tools/test_imports_contract.py).
IMPORTS_MERGE_KEYS = ("line_number", "imported_name")

# The properties an IMPORTS edge may carry. Each one is the IMPORTING file's own
# data, read from its source text -- never something derived from another file
# (a resolved target path, a canonical module name), which would go stale when
# that other file is created, renamed or deleted without the importer being
# re-indexed. Enforced by tests/unit/tools/test_imports_contract.py.
IMPORTS_PROPERTIES = frozenset({
    "line_number",       # key
    "imported_name",     # key: the imported binding (`default`, `*`, a name, or the specifier)
    "alias",             # the local name ("" when none)
    "full_import_name",  # non-JS languages: the qualified name as written (`app.services.proxy_service`)
    "lang",              # the language of the import statement (a Vue/Svelte script block's)
})
